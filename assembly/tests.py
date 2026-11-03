import datetime
import io
from fractions import Fraction
from types import SimpleNamespace

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from members.models import Member
from sms.models import SmsLog, SmsSettings

from . import counting, services
from .models import (
    INDIVIDUALS,
    INSTITUTIONS,
    PRODUCERS,
    AgendaItem,
    Assembly,
    AssemblySettings,
    BallotCast,
    Option,
    Participant,
    Vote,
)
from .services import AssemblyError

QUIET = io.StringIO()
W = {PRODUCERS: 60, INSTITUTIONS: 20, INDIVIDUALS: 20}


class CountingTests(TestCase):
    """The arithmetic of section 1.2, independent of the database."""

    def test_example_of_the_governance_document(self):
        # Half of the producers, all institutions and networks, no individuals: 30 + 20 + 0 = 50, not enough.
        present = {PRODUCERS: 4, INSTITUTIONS: 2, INDIVIDUALS: 2}
        yes = {PRODUCERS: 2, INSTITUTIONS: 2, INDIVIDUALS: 0}
        score = counting.weighted_share(W, yes, present)
        self.assertEqual(score, Fraction(1, 2))
        self.assertFalse(counting.meets(score, 1, 2, strict=True))

    def test_weight_of_an_absent_group_is_shared_in_proportion(self):
        present = {PRODUCERS: 3, INSTITUTIONS: 1, INDIVIDUALS: 0}
        weights = counting.effective_weights(W, present)
        self.assertEqual(weights[PRODUCERS], Fraction(3, 4))
        self.assertEqual(weights[INSTITUTIONS], Fraction(1, 4))
        self.assertEqual(weights[INDIVIDUALS], 0)
        self.assertEqual(counting.weighted_share(W, {INSTITUTIONS: 1}, present), Fraction(1, 4))

    def test_two_thirds_is_exact(self):
        present = {PRODUCERS: 3, INSTITUTIONS: 0, INDIVIDUALS: 0}
        score = counting.weighted_share(W, {PRODUCERS: 2}, present)
        self.assertTrue(counting.meets(score, 2, 3, strict=False))
        self.assertFalse(counting.meets(score - Fraction(1, 10**9), 2, 3, strict=False))

    def test_tie_for_the_last_seat_elects_nobody_at_that_score(self):
        settings = AssemblySettings(weight_producers=60, weight_institutions=20, weight_individuals=20)
        options = [SimpleNamespace(pk=i, code="", label=f"C{i}", label_en="") for i in (1, 2, 3)]
        item = SimpleNamespace(
            kind=AgendaItem.Kind.ELECTION, seats=2, majority="ordinary", Kind=AgendaItem.Kind,
            Majority=AgendaItem.Majority, ballot_options=lambda: options,
            assembly=SimpleNamespace(call="first", Call=Assembly.Call),
        )
        present = {PRODUCERS: 2}
        r = counting.count(settings, item, present, present, {1: {PRODUCERS: 2}, 2: {PRODUCERS: 1}, 3: {PRODUCERS: 1}})
        self.assertTrue(r["tie"])
        self.assertEqual(r["elected"], [1])


@override_settings(WAGTAILADMIN_BASE_URL="https://example.org")
class AssemblyTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", stdout=QUIET)
        Member.objects.update(status=Member.TRIAL)  # seed members are not part of these scenarios
        cls.members = {}
        for key, mtype in [("p1", "producer"), ("p2", "producer"), ("p3", "producer"), ("p4", "producer"),
                           ("i1", "institution"), ("n1", "network"), ("s1", "individual"), ("s2", "individual")]:
            m = Member.objects.create(name=f"عضو {key}", name_en=f"Member {key}", slug=key, member_type=mtype,
                                      status=Member.OFFICIAL, public_phone="09121234567")
            user = User.objects.create_user(key, f"{key}@example.org", "pw-12345")
            m.managers.add(user)
            cls.members[key] = m
        cls.trial = Member.objects.create(name="آزمایشی", slug="trial", member_type="producer", status=Member.TRIAL)
        cls.secretary = User.objects.create_user("sec", "sec@example.org", "pw", is_staff=True)
        cls.secretary.groups.add(Group.objects.get(name="دبیر مجمع"))
        cls.board = User.objects.create_user("board", "board@example.org", "pw", is_staff=True)
        cls.board.groups.add(Group.objects.get(name="هیئت مدیره"))

    def setUp(self):
        now = timezone.now()
        self.assembly = Assembly.objects.create(title="مجمع عادی سالانه", title_en="Annual General Assembly",
                                                starts_at=now + datetime.timedelta(days=20), mode=Assembly.Mode.HYBRID,
                                                meeting_url="https://meet.example.org/ga")
        self.motion = AgendaItem.objects.create(assembly=self.assembly, sort_order=1, title="تصویب ترازنامه",
                                                title_en="Approve the accounts")
        services.ensure_resolution_options(self.motion)
        self.election = AgendaItem.objects.create(assembly=self.assembly, sort_order=2, title="انتخاب هیئت مدیره",
                                                  kind=AgendaItem.Kind.ELECTION, seats=2)
        for name in ("الف", "ب", "ج"):
            Option.objects.create(item=self.election, label=name)

    def seat(self, key):
        return self.assembly.participants.get(member=self.members[key])

    def option(self, code, item=None):
        return (item or self.motion).options.get(code=code)

    def start(self):
        services.send_invitations(self.assembly, self.secretary)
        self.assembly.refresh_from_db()
        services.start_session(self.assembly, self.secretary)
        self.assembly.refresh_from_db()

    def login(self, key):
        self.client.force_login(User.objects.get(username=key))

    def vote_url(self, key, item):
        return reverse("panel:assembly_vote", kwargs={"member_id": self.members[key].pk, "pk": self.assembly.pk,
                                                       "item_id": item.pk})


class RollTests(AssemblyTestCase):
    def test_only_full_members_are_on_the_roll(self):
        services.build_roll(self.assembly)
        on_roll = set(self.assembly.participants.values_list("member__slug", flat=True))
        self.assertEqual(on_roll, set(self.members))
        self.assertEqual(self.seat("n1").group, INSTITUTIONS)  # institutions and networks are one group

    def test_suspended_member_is_dropped_when_the_roll_is_refreshed(self):
        services.build_roll(self.assembly)
        Member.objects.filter(pk=self.members["p4"].pk).update(status=Member.SUSPENDED)
        services.build_roll(self.assembly)
        self.assertFalse(self.assembly.participants.filter(member=self.members["p4"]).exists())

    def test_invitation_emails_and_sms(self):
        config = SmsSettings.load()
        config.enabled = True
        config.save()
        sent = services.send_invitations(self.assembly, self.secretary)
        self.assertEqual(sent, 8)
        self.assertEqual(len(mail.outbox), 8)
        self.assertIn("مجمع عادی سالانه", mail.outbox[0].subject)
        self.assertIn("تصویب ترازنامه", mail.outbox[0].body)
        self.assertTrue(SmsLog.objects.filter(event="assembly_invitation").exists())

    def test_late_invitation_is_flagged(self):
        self.assembly.starts_at = timezone.now() + datetime.timedelta(days=3)
        self.assertTrue(services.notice_warning(self.assembly))
        self.assembly.starts_at = timezone.now() + datetime.timedelta(days=30)
        self.assertFalse(services.notice_warning(self.assembly))

    def test_reminder_is_sent_once(self):
        services.send_invitations(self.assembly)
        Assembly.objects.filter(pk=self.assembly.pk).update(starts_at=timezone.now() + datetime.timedelta(hours=20))
        mail.outbox = []
        call_command("assembly_daily", stdout=QUIET)
        self.assertEqual(len(mail.outbox), 8)
        call_command("assembly_daily", stdout=QUIET)
        self.assertEqual(len(mail.outbox), 8)


class ProxyTests(AssemblyTestCase):
    def setUp(self):
        super().setUp()
        services.build_roll(self.assembly)

    def test_proxy_rules(self):
        services.register_proxy(self.assembly, self.seat("p1"), self.seat("p2"), "و-۱۲")
        with self.assertRaises(AssemblyError):  # other group
            services.register_proxy(self.assembly, self.seat("s1"), self.seat("p3"))
        with self.assertRaises(AssemblyError):  # at most one proxy per holder
            services.register_proxy(self.assembly, self.seat("p3"), self.seat("p2"))
        with self.assertRaises(AssemblyError):  # a holder cannot give their own vote away
            services.register_proxy(self.assembly, self.seat("p2"), self.seat("p4"))

    def test_proxies_are_fixed_once_the_session_starts(self):
        self.start()
        with self.assertRaises(AssemblyError):
            services.register_proxy(self.assembly, self.seat("p1"), self.seat("p2"))

    def test_holder_votes_twice_and_principal_counts_as_present(self):
        services.register_proxy(self.assembly, self.seat("p1"), self.seat("p2"))
        self.start()
        services.open_voting(self.motion)
        self.login("p2")
        yes = self.option("yes").pk
        self.client.post(self.vote_url("p2", self.motion), {"seat": self.seat("p2").pk, "option": yes})
        self.client.post(self.vote_url("p2", self.motion), {"seat": self.seat("p1").pk, "option": yes})
        self.assertEqual(BallotCast.objects.filter(item=self.motion).count(), 2)
        self.assertTrue(BallotCast.objects.get(participant=self.seat("p1")).by_proxy)
        eligible, present = services.roll_counts(self.assembly)
        self.assertEqual(present[PRODUCERS], 2)
        # The principal cannot vote for themselves.
        self.login("p1")
        r = self.client.post(self.vote_url("p1", self.motion), {"seat": self.seat("p1").pk, "option": yes})
        self.assertEqual(r.status_code, 404)


class VotingTests(AssemblyTestCase):
    def test_full_online_flow_with_weighted_result(self):
        self.start()
        services.open_voting(self.motion)
        yes, no = self.option("yes").pk, self.option("no").pk
        # Producers: 3 present, 2 in favour. Institutions: both in favour. Individuals: absent.
        for key, choice in [("p1", yes), ("p2", yes), ("p3", no), ("i1", yes), ("n1", yes)]:
            self.login(key)
            r = self.client.post(self.vote_url(key, self.motion), {"seat": self.seat(key).pk, "option": choice})
            self.assertEqual(r.status_code, 302)
        # A second ballot is refused.
        self.login("p1")
        self.client.post(self.vote_url("p1", self.motion), {"seat": self.seat("p1").pk, "option": no})
        self.assertEqual(BallotCast.objects.filter(item=self.motion).count(), 5)

        result = services.close_voting(self.motion, self.secretary)
        # Individuals absent: weights become 75 / 25. Yes = 0.75 * 2/3 + 0.25 * 1 = 0.75.
        self.assertEqual(result["weights"][PRODUCERS], 75.0)
        self.assertEqual(next(o for o in result["options"] if o["code"] == "yes")["score"], 75.0)
        self.assertTrue(result["passed"])
        # Quorum: 3/4 producers, 2/2 institutions, 0/2 individuals: 45 + 20 + 0 = 65% > 50%.
        self.assertEqual(result["quorum"], 65.0)
        self.assertTrue(result["quorum_met"])
        # Open (non-secret) vote: names are kept.
        self.assertEqual(Vote.objects.filter(item=self.motion, participant__isnull=False).count(), 5)

    def test_without_quorum_nothing_passes(self):
        self.start()
        services.open_voting(self.motion)
        self.login("p1")
        self.client.post(self.vote_url("p1", self.motion), {"seat": self.seat("p1").pk, "option": self.option("yes").pk})
        result = services.close_voting(self.motion)
        self.assertFalse(result["quorum_met"])
        self.assertFalse(result["passed"])

    def test_election_is_secret_and_limited_to_the_seats(self):
        self.assertTrue(self.election.secret)
        self.start()
        services.open_voting(self.election)
        a, b, c = self.election.ballot_options()
        self.login("p1")
        self.client.post(self.vote_url("p1", self.election), {"seat": self.seat("p1").pk, "option": [a.pk, b.pk, c.pk]})
        self.assertFalse(BallotCast.objects.filter(item=self.election).exists())
        self.client.post(self.vote_url("p1", self.election), {"seat": self.seat("p1").pk, "option": [a.pk, b.pk]})
        self.assertEqual(BallotCast.objects.filter(item=self.election).count(), 1)
        self.assertEqual(Vote.objects.filter(item=self.election).count(), 2)
        self.assertFalse(Vote.objects.filter(item=self.election, participant__isnull=False).exists())

    def test_suspended_member_cannot_vote(self):
        self.start()
        services.open_voting(self.motion)
        Member.objects.filter(pk=self.members["p1"].pk).update(status=Member.SUSPENDED)
        with self.assertRaises(AssemblyError):
            services.cast_ballot(self.motion, self.seat("p1"), None, [self.option("yes").pk])

    def test_no_voting_before_the_session_or_after_closing(self):
        services.send_invitations(self.assembly)
        with self.assertRaises(AssemblyError):
            services.open_voting(self.motion)
        self.assembly.refresh_from_db()
        services.start_session(self.assembly)
        services.open_voting(self.motion, closes_at=timezone.now() + datetime.timedelta(minutes=5))
        AgendaItem.objects.filter(pk=self.motion.pk).update(closes_at=timezone.now() - datetime.timedelta(seconds=1))
        self.motion.refresh_from_db()
        with self.assertRaises(AssemblyError):
            services.cast_ballot(self.motion, self.seat("p1"), None, [self.option("yes").pk])
        services.finalize_due(self.assembly)
        self.motion.refresh_from_db()
        self.assertTrue(self.motion.is_counted)

    def test_paper_ballots_of_members_in_the_room(self):
        services.build_roll(self.assembly)
        services.send_invitations(self.assembly)
        self.assembly.refresh_from_db()
        for key in ("p1", "p2", "p3"):
            services.set_presence(self.seat(key), Participant.IN_PERSON)
        services.start_session(self.assembly)
        services.open_voting(self.motion)
        with self.assertRaises(AssemblyError):  # someone in the room votes on paper
            services.cast_ballot(self.motion, self.seat("p1"), None, [self.option("yes").pk])
        with self.assertRaises(AssemblyError):  # more paper ballots than producers in the room
            services.save_paper_tally(self.motion, {(self.option("yes").pk, PRODUCERS): 4})
        services.save_paper_tally(self.motion, {(self.option("yes").pk, PRODUCERS): 2,
                                                (self.option("no").pk, PRODUCERS): 1})
        services.cast_ballot(self.motion, self.seat("i1"), None, [self.option("yes").pk])
        result = services.close_voting(self.motion)
        yes = next(o for o in result["options"] if o["code"] == "yes")
        self.assertEqual(yes["votes"], 3)
        self.assertTrue(result["passed"])

    def test_special_majority(self):
        self.motion.majority = AgendaItem.Majority.SPECIAL
        self.motion.save()
        self.start()
        services.open_voting(self.motion)
        yes, no = self.option("yes").pk, self.option("no").pk
        for key, choice in [("p1", yes), ("p2", yes), ("p3", no), ("i1", yes), ("n1", no)]:
            services.cast_ballot(self.motion, self.seat(key), None, [choice])
        result = services.close_voting(self.motion)
        # 0.75 x 2/3 + 0.25 x 1/2 = 62.5%: enough for an ordinary resolution, not for two thirds.
        self.assertTrue(result["quorum_met"])
        self.assertEqual(next(o for o in result["options"] if o["code"] == "yes")["score"], 62.5)
        self.assertFalse(result["passed"])


class PanelTests(AssemblyTestCase):
    def test_panel_pages_in_both_languages(self):
        self.start()
        services.open_voting(self.motion)
        self.login("p1")
        for lang in ("fa", "en"):
            url = f"/{lang}/panel/{self.members['p1'].pk}/assembly/"
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            r = self.client.get(f"{url}{self.assembly.pk}/")
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "https://meet.example.org/ga")
            self.assertContains(r, 'name="option"')
        r = self.client.get(f"/fa/panel/")
        self.assertContains(r, "مجمع عمومی در حال برگزاری است")

    def test_check_in_and_results_after_publication(self):
        self.start()
        self.login("p1")
        self.client.post(reverse("panel:assembly_check_in", kwargs={"member_id": self.members["p1"].pk,
                                                                    "pk": self.assembly.pk}))
        self.assertEqual(self.seat("p1").presence, Participant.ONLINE)
        services.open_voting(self.motion)
        services.cast_ballot(self.motion, self.seat("p1"), None, [self.option("yes").pk])
        services.end_session(self.assembly)
        self.assembly.refresh_from_db()
        url = reverse("panel:assembly", kwargs={"member_id": self.members["p1"].pk, "pk": self.assembly.pk})
        self.assertNotContains(self.client.get(url), "result-table")
        mail.outbox = []
        services.publish_results(self.assembly)
        self.assertEqual(len(mail.outbox), 8)
        self.assertContains(self.client.get(url), "result-table")

    def test_member_off_the_roll_sees_the_agenda_without_ballot(self):
        self.trial.managers.add(User.objects.get(username="s1"))
        self.start()
        services.open_voting(self.motion)
        self.login("s1")
        r = self.client.get(f"/fa/panel/{self.trial.pk}/assembly/{self.assembly.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'name="option"')
        self.assertNotContains(r, "meet.example.org")

    def test_draft_assembly_is_hidden(self):
        self.login("p1")
        r = self.client.get(f"/fa/panel/{self.members['p1'].pk}/assembly/{self.assembly.pk}/")
        self.assertEqual(r.status_code, 404)


class AdminTests(AssemblyTestCase):
    def test_secretary_runs_the_assembly_from_the_control_page(self):
        self.client.force_login(self.secretary)
        url = reverse("assembly_control:control", args=[self.assembly.pk])
        self.assertEqual(self.client.get(reverse("assembly_control:index")).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"action": "invite"})
        self.client.post(url, {"action": "proxy", "principal": self.seat("s1").pk, "holder": self.seat("s2").pk})
        self.assertEqual(self.seat("s1").proxy_holder, self.seat("s2"))
        self.client.post(url, {"action": "presence", "participant": self.seat("p1").pk, "presence": "in_person"})
        self.client.post(url, {"action": "start"})
        self.client.post(url, {"action": "open", "item": self.motion.pk, "minutes": "10", "notify": "1"})
        self.motion.refresh_from_db()
        self.assertEqual(self.motion.voting_state(), "open")
        yes = self.option("yes")
        self.client.post(url, {"action": "paper", "item": self.motion.pk, f"t-{yes.pk}-{PRODUCERS}": "1"})
        self.client.post(url, {"action": "close", "item": self.motion.pk})
        self.motion.refresh_from_db()
        self.assertTrue(self.motion.is_counted)
        r = self.client.get(url)
        self.assertContains(r, "شمرده شد")
        self.client.post(url, {"action": "end"})
        self.client.post(url, {"action": "publish"})
        self.assembly.refresh_from_db()
        self.assertTrue(self.assembly.results_published)
        self.assertTrue(self.assembly.log.exists())

    def test_board_can_follow_but_not_act(self):
        self.client.force_login(self.board)
        url = reverse("assembly_control:control", args=[self.assembly.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"action": "invite"})  # refused (the admin redirects with a message)
        self.assembly.refresh_from_db()
        self.assertEqual(self.assembly.status, Assembly.Status.DRAFT)

    def test_member_has_no_admin_access(self):
        self.client.force_login(User.objects.get(username="p1"))
        r = self.client.get(reverse("assembly_control:index"))
        self.assertNotEqual(r.status_code, 200)

    def test_edit_views_and_settings_render(self):
        self.client.force_login(User.objects.create_superuser("root", "root@example.org", "pw"))
        self.assertEqual(self.client.get(reverse("assemblies:add")).status_code, 200)
        self.assertEqual(self.client.get(reverse("assemblies:edit", args=[self.assembly.pk])).status_code, 200)
        r = self.client.get(reverse("assembly_items:add") + f"?assembly={self.assembly.pk}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(reverse("assembly_items:edit", args=[self.election.pk])).status_code, 200)
        r = self.client.get(reverse("wagtailsettings:edit", args=["assembly", "assemblysettings"]), follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "وزن رأی تولیدکنندگان")
        self.assertEqual(self.client.get(reverse("wagtailadmin_home")).status_code, 200)
