"""
What happens in an assembly: the roll of members with voting rights,
proxies, attendance, opening and closing votes, casting ballots, counting
and publishing results. Views call these; e-mails go through notifications.
"""

from collections import defaultdict

from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from members.models import Member

from . import counting
from .models import (
    GROUP_LABELS,
    GROUPS,
    TYPE_GROUP,
    AgendaItem,
    AgendaItem,
    Assembly,
    AssemblyLog,
    AssemblySettings,
    BallotCast,
    Option,
    PaperTally,
    Participant,
    Vote,
)

S = Assembly.Status


class AssemblyError(Exception):
    pass


def log(assembly, text, user=None):
    AssemblyLog.objects.create(assembly=assembly, text=text[:500], user=user if user and user.pk else None)


# ---- eligibility and roll ----


def has_vote_right(member):
    """Only full members vote (section 1.2); suspended and cancelled members lose the right (1.7, 1.8)."""
    return member.status == Member.OFFICIAL


def eligible_members():
    return Member.objects.filter(status=Member.OFFICIAL)


def build_roll(assembly, user=None):
    """
    Add every full member to the roll and drop those who lost the right
    (unless they hold or gave a proxy). Allowed until the session starts.
    Returns (added, removed).
    """
    if assembly.roll_is_frozen:
        raise AssemblyError("دفتر حاضران پس از شروع جلسه ثابت است.")
    added = removed = 0
    with transaction.atomic():
        on_roll = {p.member_id: p for p in assembly.participants.select_related("member")}
        for member in eligible_members():
            group = TYPE_GROUP.get(member.member_type)
            p = on_roll.pop(member.pk, None)
            if p is None:
                Participant.objects.create(assembly=assembly, member=member, group=group)
                added += 1
            elif p.group != group:
                p.group = group
                p.save(update_fields=["group"])
        for p in on_roll.values():  # no longer a full member
            Participant.objects.filter(proxy_holder=p).update(proxy_holder=None, proxy_reference="")
            p.delete()
            removed += 1
    if added or removed:
        log(assembly, f"دفتر حاضران به‌روز شد: {added} عضو افزوده و {removed} عضو برداشته شد.", user)
    return added, removed


def roll_counts(assembly):
    """({group: members on the roll}, {group: members present, in person, online or by proxy})."""
    eligible, present = defaultdict(int), defaultdict(int)
    for p in assembly.participants.select_related("proxy_holder"):
        eligible[p.group] += 1
        if p.is_present:
            present[p.group] += 1
    return dict(eligible), dict(present)


def quorum_now(assembly, settings=None):
    settings = settings or AssemblySettings.load()
    eligible, present = roll_counts(assembly)
    score, met = counting.quorum(settings, assembly, eligible, present)
    return {"score": counting.pct(score), "met": met, "eligible": eligible, "present": present}


# ---- proxies (section 2: written proxy, same group, at most one, registered before the start) ----


def register_proxy(assembly, principal, holder, reference="", user=None, settings=None):
    settings = settings or AssemblySettings.load()
    if assembly.roll_is_frozen:
        raise AssemblyError("وکالت‌نامه باید پیش از شروع جلسه ثبت شود.")
    if principal.pk == holder.pk:
        raise AssemblyError("عضو نمی‌تواند وکیل خودش باشد.")
    if principal.assembly_id != assembly.pk or holder.assembly_id != assembly.pk:
        raise AssemblyError("هر دو عضو باید در دفتر حاضران همین مجمع باشند.")
    if principal.group != holder.group:
        raise AssemblyError("وکیل باید عضو رسمی همان گروه رأی باشد.")
    if holder.proxy_holder_id:
        raise AssemblyError("این عضو خود رأی‌اش را به وکالت داده و نمی‌تواند وکیل باشد.")
    if principal.proxies_held.exists():
        raise AssemblyError("این عضو وکالت عضو دیگری را دارد و نمی‌تواند رأی خود را به وکالت بدهد.")
    if holder.proxies_held.exclude(pk=principal.pk).count() >= settings.max_proxies_per_holder:
        raise AssemblyError("این عضو بیشترین تعداد وکالت مجاز را پذیرفته است.")
    principal.proxy_holder = holder
    principal.proxy_reference = reference
    principal.save(update_fields=["proxy_holder", "proxy_reference"])
    log(assembly, f"وکالت ثبت شد: «{principal.member}» به «{holder.member}» ({reference or 'بی‌شماره'}).", user)


def remove_proxy(assembly, principal, user=None):
    if assembly.roll_is_frozen:
        raise AssemblyError("پس از شروع جلسه وکالت تغییر نمی‌کند.")
    if principal.proxy_holder_id:
        holder = principal.proxy_holder
        principal.proxy_holder = None
        principal.proxy_reference = ""
        principal.save(update_fields=["proxy_holder", "proxy_reference"])
        log(assembly, f"وکالت «{principal.member}» به «{holder.member}» برداشته شد.", user)


# ---- session ----


def send_invitations(assembly, user=None):
    from . import notifications

    if assembly.status not in (S.DRAFT, S.INVITED):
        raise AssemblyError("دعوت‌نامه فقط پیش از شروع جلسه فرستاده می‌شود.")
    if not assembly.items.exists():
        raise AssemblyError("پیش از دعوت، دستور جلسه را بنویسید.")
    build_roll(assembly, user)
    assembly.status = S.INVITED
    assembly.invited_at = assembly.invited_at or timezone.now()
    assembly.save(update_fields=["status", "invited_at"])
    sent = notifications.invitation(assembly)
    log(assembly, f"دعوت‌نامه برای {sent} عضو فرستاده شد.", user)
    return sent


def notice_warning(assembly, settings=None, now=None):
    """A note if the invitation is later than the notice period of section 2.1, or the second call too soon."""
    settings = settings or AssemblySettings.load()
    now = now or timezone.now()
    days = (settings.notice_days_extraordinary if assembly.kind == Assembly.Kind.EXTRAORDINARY
            else settings.notice_days_ordinary)
    notes = []
    sent = assembly.invited_at or now
    if (assembly.starts_at - sent).days < days:
        notes.append(f"دعوت‌نامه باید دست‌کم {days} روز پیش از مجمع {assembly.get_kind_display()} فرستاده شود.")
    if assembly.call == Assembly.Call.SECOND and assembly.first_call_id:
        gap = (assembly.starts_at - assembly.first_call.starts_at).days
        if gap < settings.second_call_min_days:
            notes.append(f"مجمع نوبت دوم باید دست‌کم {settings.second_call_min_days} روز پس از نوبت اول باشد.")
    return notes


def start_session(assembly, user=None):
    if assembly.status != S.INVITED:
        raise AssemblyError("جلسه پس از ارسال دعوت‌نامه آغاز می‌شود.")
    assembly.status = S.IN_SESSION
    assembly.started_at = timezone.now()
    assembly.save(update_fields=["status", "started_at"])
    q = quorum_now(assembly)
    log(assembly, f"جلسه آغاز شد. حضور تا این لحظه: {q['score']}٪ امتیاز وزنی.", user)


def end_session(assembly, user=None):
    if assembly.status != S.IN_SESSION:
        raise AssemblyError("جلسه در حال برگزاری نیست.")
    for item in assembly.items.filter(counted_at__isnull=True).exclude(kind=AgendaItem.Kind.DISCUSSION):
        if item.opens_at and item.opens_at <= timezone.now():
            close_voting(item, user)
    assembly.status = S.ENDED
    assembly.ended_at = timezone.now()
    assembly.save(update_fields=["status", "ended_at"])
    log(assembly, "جلسه پایان یافت.", user)


def cancel(assembly, user=None):
    if assembly.status in (S.ENDED, S.CANCELLED):
        raise AssemblyError("این مجمع پایان یافته یا لغو شده است.")
    assembly.status = S.CANCELLED
    assembly.save(update_fields=["status"])
    log(assembly, "مجمع لغو شد.", user)


def set_presence(participant, presence, user=None):
    """Mark a member present (online or in person) or absent. Not after they have voted."""
    assembly = participant.assembly
    if assembly.status not in (S.INVITED, S.IN_SESSION):
        raise AssemblyError("حضور فقط پیش از جلسه یا هنگام جلسه ثبت می‌شود.")
    if participant.presence == presence:
        return
    if participant.ballots.exists() or Participant.objects.filter(proxy_holder=participant, ballots__isnull=False).exists():
        raise AssemblyError("این عضو رأی داده و حضورش تغییر نمی‌کند.")
    if presence and participant.proxy_holder_id:
        raise AssemblyError("این عضو رأی خود را به وکالت داده است؛ وکیل او به جایش رأی می‌دهد.")
    participant.presence = presence
    participant.present_at = timezone.now() if presence else None
    participant.save(update_fields=["presence", "present_at"])
    label = dict(Participant.PRESENCE_CHOICES)[presence]
    log(assembly, f"«{participant.member}»: {label}.", user)


def check_in_online(participant, user):
    """The member says they are at the online session (from the member panel)."""
    assembly = participant.assembly
    if not (assembly.in_session and assembly.online_voting):
        raise AssemblyError("اعلام حضور برخط فقط هنگام جلسه برخط یا ترکیبی ممکن است.")
    if participant.presence:
        return
    set_presence(participant, Participant.ONLINE, user)


# ---- voting ----


def open_voting(item, user=None, closes_at=None):
    if not item.has_vote:
        raise AssemblyError("این بند رأی‌گیری ندارد.")
    if not item.assembly.in_session:
        raise AssemblyError("رأی‌گیری فقط هنگام جلسه باز می‌شود.")
    if item.is_counted:
        raise AssemblyError("رأی‌گیری این بند پیش‌تر بسته و شمرده شده است.")
    if not item.ballot_options():
        raise AssemblyError("این بند گزینه‌ای برای رأی ندارد؛ نامزدها را وارد کنید.")
    now = timezone.now()
    item.opens_at = now
    item.closes_at = closes_at if closes_at and closes_at > now else None
    item.save(update_fields=["opens_at", "closes_at"])
    log(item.assembly, f"رأی‌گیری «{item.title}» باز شد.", user)


def voting_rights(member, assembly):
    """The roll seats this member votes for: its own (unless given by proxy) and the proxies it holds."""
    own = assembly.participants.filter(member=member).select_related("member").first()
    if own is None:
        return []
    seats = [] if own.proxy_holder_id else [own]
    seats += list(own.proxies_held.select_related("member"))
    return seats


def cast_ballot(item, participant, user, option_ids, by_proxy=False):
    """
    Record one ballot online. option_ids: one id for a resolution, up to
    `seats` ids for an election (none = blank ballot). Cannot be changed.
    """
    assembly = item.assembly
    if item.voting_state() != "open":
        raise AssemblyError("رأی‌گیری این بند باز نیست.")
    if not assembly.online_voting:
        raise AssemblyError("این مجمع حضوری است و رأی‌گیری در جلسه انجام می‌شود.")
    holder = participant.proxy_holder if participant.proxy_holder_id else participant
    if by_proxy != (holder.pk != participant.pk):
        raise AssemblyError("این رأی را باید وکیل ثبت کند.")
    for p in {participant, holder}:
        if not has_vote_right(Member.objects.get(pk=p.member_id)):
            raise AssemblyError("حق رأی این عضو اکنون فعال نیست (تعلیق یا لغو عضویت).")
    if holder.presence == Participant.IN_PERSON:
        raise AssemblyError("حضور شما در محل جلسه ثبت شده است؛ رأی را در جلسه بدهید.")

    options = {o.pk: o for o in item.ballot_options()}
    chosen = [options[i] for i in dict.fromkeys(option_ids) if i in options]
    if len(chosen) != len(set(option_ids)):
        raise AssemblyError("گزینه نامعتبر است.")
    if item.kind == AgendaItem.Kind.RESOLUTION and len(chosen) != 1:
        raise AssemblyError("یک گزینه را انتخاب کنید.")
    if item.kind == AgendaItem.Kind.ELECTION and len(chosen) > item.seats:
        raise AssemblyError(f"حداکثر {item.seats} نامزد را می‌توانید انتخاب کنید.")

    with transaction.atomic():
        if not holder.presence:  # voting online means taking part in the online session
            holder.presence = Participant.ONLINE
            holder.present_at = timezone.now()
            holder.save(update_fields=["presence", "present_at"])
        try:
            with transaction.atomic():
                BallotCast.objects.create(item=item, participant=participant, cast_by=user, by_proxy=by_proxy)
        except IntegrityError:
            raise AssemblyError("رأی این عضو برای این بند پیش‌تر ثبت شده است.")
        Vote.objects.bulk_create([
            Vote(item=item, option=o, group=participant.group, participant=None if item.secret else participant)
            for o in chosen
        ])


def tallies_for(item):
    """{option_id: {group: n}} from online votes and paper tallies."""
    tallies = defaultdict(lambda: defaultdict(int))
    for row in item.votes.values("option_id", "group").order_by().annotate(n=Count("id")):
        tallies[row["option_id"]][row["group"]] += row["n"]
    for t in item.paper_tallies.all():
        tallies[t.option_id][t.group] += t.count
    return tallies


def paper_voters(assembly):
    """{group: seats that vote on paper}: present in the room, themselves or through their proxy holder."""
    counts = defaultdict(int)
    for p in assembly.participants.select_related("proxy_holder"):
        if p.is_present and p.votes_on_paper:
            counts[p.group] += 1
    return counts


def save_paper_tally(item, data, user=None):
    """data: {(option_id, group): n}. Checked against the number of paper voters of each group."""
    if item.is_counted:
        raise AssemblyError("این بند شمرده شده و تغییر نمی‌کند.")
    limit = paper_voters(item.assembly)
    options = {o.pk for o in item.ballot_options()}
    per_group = defaultdict(int)
    for (option_id, group), n in data.items():
        if option_id not in options or group not in GROUPS:
            raise AssemblyError("گزینه یا گروه نامعتبر است.")
        per_group[group] = max(per_group[group], n) if item.kind == AgendaItem.Kind.ELECTION else per_group[group] + n
    for group, n in per_group.items():
        if n > limit.get(group, 0):
            raise AssemblyError(f"شمار آرای کاغذی گروه «{GROUP_LABELS[group][0]}» "
                                f"بیشتر از اعضای حاضر در محل ({limit.get(group, 0)}) است.")
    with transaction.atomic():
        for (option_id, group), n in data.items():
            PaperTally.objects.update_or_create(item=item, option_id=option_id, group=group, defaults={"count": n})
    log(item.assembly, f"آرای کاغذی «{item.title}» ثبت شد.", user)


def close_voting(item, user=None):
    """Close the vote and store the weighted result."""
    if item.is_counted:
        return item.result
    settings = AssemblySettings.load()
    eligible, present = roll_counts(item.assembly)
    now = timezone.now()
    with transaction.atomic():
        item.result = counting.count(settings, item, eligible, present, tallies_for(item))
        item.result["ballots"] = item.ballots.count()
        item.counted_at = now
        if not item.closes_at or item.closes_at > now:
            item.closes_at = now
        if not item.opens_at:
            item.opens_at = now
        item.save(update_fields=["result", "counted_at", "closes_at", "opens_at"])
    verdict = "تصویب شد" if item.result["passed"] else "تصویب نشد"
    if item.kind == AgendaItem.Kind.ELECTION:
        verdict = "منتخبان مشخص شدند" if item.result["passed"] else "منتخبی مشخص نشد"
    log(item.assembly, f"رأی‌گیری «{item.title}» بسته و شمرده شد: {verdict}.", user)
    return item.result


def finalize_due(assembly):
    """Count the items whose voting time has ended (called whenever the assembly is shown)."""
    now = timezone.now()
    for item in assembly.items.filter(counted_at__isnull=True, closes_at__lte=now).exclude(
            kind=AgendaItem.Kind.DISCUSSION):
        if item.opens_at and item.opens_at <= now:
            close_voting(item)


def publish_results(assembly, user=None, notify=True):
    from . import notifications

    if assembly.items.filter(counted_at__isnull=True).exclude(kind=AgendaItem.Kind.DISCUSSION).exists() \
            and assembly.status != S.ENDED:
        raise AssemblyError("پیش از انتشار، همه رأی‌گیری‌ها را ببندید یا جلسه را پایان دهید.")
    assembly.results_published_at = timezone.now()
    assembly.save(update_fields=["results_published_at"])
    sent = notifications.results(assembly) if notify else 0
    log(assembly, f"نتایج برای اعضا منتشر شد ({sent} ایمیل).", user)


def ensure_resolution_options(item):
    """Resolutions always have exactly the three options in favour / against / abstain."""
    if item.kind != AgendaItem.Kind.RESOLUTION:
        return
    existing = {o.code: o for o in item.options.all() if o.code}
    for order, code in enumerate((Option.YES, Option.NO, Option.ABSTAIN)):
        if code not in existing:
            fa, en = Option.CODE_LABELS[code]
            Option.objects.create(item=item, code=code, label=fa, label_en=en, sort_order=order)


def option_label(row):
    from core.models import is_english

    if row.get("code"):
        fa, en = Option.CODE_LABELS[row["code"]]
        return en if is_english() else fa
    return (row.get("label_en") or row["label"]) if is_english() else row["label"]
