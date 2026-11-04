"""
The General Assembly and its online weighted voting, following sections 1.2
and 2 of the governance document (سند ارکان، نسخه ۲):

  * the assembly is made of the full (official) members with voting rights;
    trial, suspended and cancelled members do not vote;
  * votes are weighted by group: producers 60, support institutions and
    networks together 20, individual supporters 20; inside a group every
    member's vote is equal; the share of a group in favour is multiplied by
    the group's weight and the results are added; a group with no member
    present has its weight shared among the others in proportion;
  * quorum: members holding more than half of the weighted score (a second
    call, at least 7 days later, needs one third);
  * ordinary resolutions pass with more than half of the weighted score of
    those present, statute changes, legal form, mission and dissolution need
    two thirds;
  * a full member may give a written proxy to another full member of the same
    group, registered with the assembly secretary before the session starts;
    each member holds at most one proxy;
  * the assembly may meet in person, online or both; elections are by secret
    ballot, online through a secure electronic system; the session's records
    are kept.

Weights, thresholds and notice periods are edited in the admin panel
(Settings → مجمع عمومی), so an amendment of the document needs no code change.
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import (
    FieldPanel,
    FieldRowPanel,
    InlinePanel,
    MultiFieldPanel,
    ObjectList,
    TabbedInterface,
)
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.fields import RichTextField
from wagtail.models import Orderable

from core.models import BilingualMixin, is_english

SECRETARY_GROUP = "دبیر مجمع"  # created by seed_content (home/management/commands/seed_data.py)

# ---- voting groups (section 1.2) ----

PRODUCERS = "producers"
INSTITUTIONS = "institutions"
INDIVIDUALS = "individuals"
GROUPS = [PRODUCERS, INSTITUTIONS, INDIVIDUALS]
GROUP_LABELS = {
    PRODUCERS: ("تولیدکنندگان", "Producers"),
    INSTITUTIONS: ("نهادهای حمایتی و شبکه‌ها", "Support institutions and networks"),
    INDIVIDUALS: ("افراد حامی", "Individual supporters"),
}
GROUP_CHOICES = [(g, GROUP_LABELS[g][0]) for g in GROUPS]

# Member.member_type -> voting group. Institutions and networks are one group.
TYPE_GROUP = {
    "producer": PRODUCERS,
    "institution": INSTITUTIONS,
    "network": INSTITUTIONS,
    "individual": INDIVIDUALS,
}


def group_label(group):
    fa, en = GROUP_LABELS.get(group, (group, group))
    return en if is_english() else fa


def _en(labels_en, value, display):
    return labels_en.get(value, display) if is_english() else display


@register_setting(icon="group")
class AssemblySettings(BaseGenericSetting):
    enabled = models.BooleanField(
        "رأی‌گیری برخط فعال است", default=True,
        help_text="اگر خاموش باشد، بخش «مجمع عمومی» در پنل اعضا نمایش داده نمی‌شود",
    )

    # ---- weights (section 1.2) ----
    weight_producers = models.PositiveSmallIntegerField("وزن رأی تولیدکنندگان", default=60)
    weight_institutions = models.PositiveSmallIntegerField("وزن رأی نهادهای حمایتی و شبکه‌ها (مشترک)", default=20)
    weight_individuals = models.PositiveSmallIntegerField("وزن رأی افراد حامی", default=20)

    # ---- quorum and majority (section 2), as fractions ----
    quorum_first_num = models.PositiveSmallIntegerField("صورت کسر", default=1)
    quorum_first_den = models.PositiveSmallIntegerField("مخرج کسر", default=2)
    quorum_second_num = models.PositiveSmallIntegerField("صورت کسر", default=1)
    quorum_second_den = models.PositiveSmallIntegerField("مخرج کسر", default=3)
    majority_num = models.PositiveSmallIntegerField("صورت کسر", default=1)
    majority_den = models.PositiveSmallIntegerField("مخرج کسر", default=2)
    special_num = models.PositiveSmallIntegerField("صورت کسر", default=2)
    special_den = models.PositiveSmallIntegerField("مخرج کسر", default=3)

    # ---- deadlines ----
    notice_days_ordinary = models.PositiveSmallIntegerField("فاصله دعوت‌نامه تا مجمع عادی (روز)", default=15)
    notice_days_extraordinary = models.PositiveSmallIntegerField("فاصله دعوت‌نامه تا مجمع فوق‌العاده (روز)",
                                                                 default=7)
    second_call_min_days = models.PositiveSmallIntegerField("کمترین فاصله مجمع نوبت دوم از نوبت اول (روز)",
                                                            default=7)
    reminder_days_before = models.PositiveSmallIntegerField(
        "یادآوری چند روز پیش از مجمع فرستاده شود", default=1, help_text="۰ یعنی یادآوری فرستاده نشود",
    )
    max_proxies_per_holder = models.PositiveSmallIntegerField("بیشترین تعداد وکالت برای هر عضو حاضر", default=1)

    # ---- panel texts ----
    intro = RichTextField("توضیح بالای صفحه مجمع در پنل (فارسی)", blank=True,
                          default="<p>مجمع عمومی بالاترین مرجع تصمیم‌گیری خانه است. اعضای رسمی در اینجا دعوت‌نامه "
                                  "و دستور جلسه را می‌بینند، حضور خود را اعلام می‌کنند و رأی می‌دهند.</p>")
    intro_en = RichTextField("توضیح بالای صفحه مجمع در پنل (انگلیسی)", blank=True,
                             default="<p>The General Assembly is the House's highest decision-making body. Full "
                                     "members see the invitation and agenda here, register their attendance and "
                                     "vote.</p>")
    secret_note = models.TextField(
        "توضیح رأی مخفی (فارسی)", blank=True,
        default="این رأی مخفی است: سامانه فقط ثبت می‌کند که شما رأی داده‌اید و رأی شما بدون نام شمرده می‌شود.",
    )
    secret_note_en = models.TextField(
        "توضیح رأی مخفی (انگلیسی)", blank=True,
        default="This is a secret ballot: the system only records that you voted; your vote is counted without "
                "your name.",
    )

    # ---- e-mails ----
    invitation_subject = models.CharField("موضوع (فارسی)", max_length=200,
                                          default="دعوت به {assembly}")
    invitation_body = models.TextField(
        "متن (فارسی)",
        default="{name} گرامی،\n\nبه {assembly} دعوت می‌شوید.\n\nزمان: {date}\nشیوه برگزاری: {mode}\n{location}\n\n"
                "دستور جلسه:\n{agenda}\n\nدعوت‌نامه، پیوند جلسه برخط، ثبت حضور و رأی‌گیری در پنل اعضا:\n{panel_url}\n\n"
                "اگر نمی‌توانید حاضر شوید، می‌توانید با وکالت‌نامه کتبی رأی خود را به عضو رسمی دیگری از همان گروه "
                "بسپارید؛ وکالت‌نامه باید پیش از شروع جلسه نزد دبیر مجمع ثبت شود.\n\nبا احترام،\nدبیر مجمع عمومی، {site_name}",
    )
    invitation_subject_en = models.CharField("موضوع (انگلیسی)", max_length=200, blank=True,
                                             default="Invitation: {assembly}")
    invitation_body_en = models.TextField(
        "متن (انگلیسی)", blank=True,
        default="Dear {name},\n\nYou are invited to the {assembly}.\n\nWhen: {date}\nFormat: {mode}\n{location}\n\n"
                "Agenda:\n{agenda}\n\nThe invitation, the online meeting link, attendance and voting are in the "
                "member panel:\n{panel_url}\n\nIf you cannot attend, you may give your vote by written proxy to "
                "another full member of your group; the proxy must be registered with the Assembly Secretary "
                "before the session starts.\n\nKind regards,\nSecretary of the General Assembly, {site_name}",
    )
    reminder_subject = models.CharField("موضوع (فارسی)", max_length=200, default="یادآوری: {assembly}")
    reminder_body = models.TextField(
        "متن (فارسی)",
        default="{name} گرامی،\n\n{assembly} در {date} برگزار می‌شود.\n\nپنل اعضا:\n{panel_url}\n\nبا احترام،\n"
                "دبیر مجمع عمومی، {site_name}",
    )
    reminder_subject_en = models.CharField("موضوع (انگلیسی)", max_length=200, blank=True,
                                           default="Reminder: {assembly}")
    reminder_body_en = models.TextField(
        "متن (انگلیسی)", blank=True,
        default="Dear {name},\n\nThe {assembly} takes place on {date}.\n\nMember panel:\n{panel_url}\n\nKind regards,\n"
                "Secretary of the General Assembly, {site_name}",
    )
    voting_subject = models.CharField("موضوع (فارسی)", max_length=200, default="رأی‌گیری آغاز شد: {item}")
    voting_body = models.TextField(
        "متن (فارسی)",
        default="{name} گرامی،\n\nرأی‌گیری «{item}» در {assembly} آغاز شد{closes}.\n\nرأی دادن در پنل اعضا:\n"
                "{panel_url}\n\nبا احترام،\nدبیر مجمع عمومی، {site_name}",
    )
    voting_subject_en = models.CharField("موضوع (انگلیسی)", max_length=200, blank=True,
                                         default="Voting is open: {item}")
    voting_body_en = models.TextField(
        "متن (انگلیسی)", blank=True,
        default="Dear {name},\n\nVoting on \"{item}\" at the {assembly} is open{closes}.\n\nVote in the member "
                "panel:\n{panel_url}\n\nKind regards,\nSecretary of the General Assembly, {site_name}",
    )
    results_subject = models.CharField("موضوع (فارسی)", max_length=200, default="نتایج {assembly}")
    results_body = models.TextField(
        "متن (فارسی)",
        default="{name} گرامی،\n\nنتایج رأی‌گیری {assembly}:\n\n{results}\n\nجزئیات و صورتجلسه در پنل اعضا:\n"
                "{panel_url}\n\nبا احترام،\nدبیر مجمع عمومی، {site_name}",
    )
    results_subject_en = models.CharField("موضوع (انگلیسی)", max_length=200, blank=True,
                                          default="Results: {assembly}")
    results_body_en = models.TextField(
        "متن (انگلیسی)", blank=True,
        default="Dear {name},\n\nResults of the votes at the {assembly}:\n\n{results}\n\nDetails and the minutes "
                "are in the member panel:\n{panel_url}\n\nKind regards,\nSecretary of the General Assembly, "
                "{site_name}",
    )

    def email_panels(kind, heading):
        return MultiFieldPanel([
            FieldPanel(f"{kind}_subject"), FieldPanel(f"{kind}_body"),
            FieldPanel(f"{kind}_subject_en"), FieldPanel(f"{kind}_body_en"),
        ], heading=heading)

    edit_handler = TabbedInterface([
        ObjectList([
            FieldPanel("enabled"),
            MultiFieldPanel([
                FieldPanel("weight_producers"), FieldPanel("weight_institutions"), FieldPanel("weight_individuals"),
            ], heading="وزن رأی گروه‌ها (بند ۱-۲)",
                help_text="رأی اعضای هر گروه درون گروه برابر است. وزن گروهی که عضو حاضر ندارد به نسبت وزن‌ها میان دیگر گروه‌ها تقسیم می‌شود."),
            MultiFieldPanel([
                FieldRowPanel([FieldPanel("quorum_first_num"), FieldPanel("quorum_first_den")],
                              heading="رسمیت نوبت اول: بیش از"),
                FieldRowPanel([FieldPanel("quorum_second_num"), FieldPanel("quorum_second_den")],
                              heading="رسمیت نوبت دوم: دست‌کم"),
                FieldRowPanel([FieldPanel("majority_num"), FieldPanel("majority_den")],
                              heading="مصوبات عادی: بیش از"),
                FieldRowPanel([FieldPanel("special_num"), FieldPanel("special_den")],
                              heading="اساسنامه، شکل حقوقی، مأموریت و انحلال: دست‌کم"),
            ], heading="حد نصاب و اکثریت (بند ۲)",
                help_text="کسری از امتیاز وزنی. رسمیت از امتیاز وزنی همه اعضای دارای حق رأی و تصویب از امتیاز وزنی حاضران حساب می‌شود."),
            MultiFieldPanel([
                FieldPanel("notice_days_ordinary"), FieldPanel("notice_days_extraordinary"),
                FieldPanel("second_call_min_days"), FieldPanel("reminder_days_before"),
                FieldPanel("max_proxies_per_holder"),
            ], heading="مهلت‌ها و وکالت"),
        ], heading="قواعد"),
        ObjectList([
            FieldPanel("intro"), FieldPanel("intro_en"), FieldPanel("secret_note"), FieldPanel("secret_note_en"),
        ], heading="متن‌های پنل"),
        ObjectList([
            email_panels("invitation", "دعوت‌نامه"),
            email_panels("reminder", "یادآوری پیش از مجمع"),
            email_panels("voting", "آغاز رأی‌گیری"),
            email_panels("results", "اعلام نتایج"),
        ], heading="ایمیل‌ها",
            help_text="می‌توانید از این‌ها استفاده کنید: {name} {assembly} {date} {mode} {location} {agenda} "
                      "{item} {closes} {results} {panel_url} {site_name}. متن پیامک‌ها در «پیامک > متن‌های پیامک» است."),
    ])
    del email_panels

    class Meta:
        verbose_name = "مجمع عمومی"

    def tr(self, field):
        return BilingualMixin.tr(self, field)

    @property
    def weights(self):
        return {PRODUCERS: self.weight_producers, INSTITUTIONS: self.weight_institutions,
                INDIVIDUALS: self.weight_individuals}

    def clean(self):
        if not any(self.weights.values()):
            raise ValidationError("دست‌کم یکی از وزن‌ها باید بیشتر از صفر باشد.")
        for prefix in ("quorum_first", "quorum_second", "majority", "special"):
            num, den = getattr(self, f"{prefix}_num"), getattr(self, f"{prefix}_den")
            if not den or num > den:
                raise ValidationError({f"{prefix}_den": "مخرج باید بزرگ‌تر از صفر و دست‌کم برابر صورت باشد."})


class Assembly(BilingualMixin, models.Model):
    class Kind(models.TextChoices):
        ORDINARY = "ordinary", "عادی"
        EXTRAORDINARY = "extraordinary", "فوق‌العاده"

    class Call(models.TextChoices):
        FIRST = "first", "نوبت اول"
        SECOND = "second", "نوبت دوم"

    class Mode(models.TextChoices):
        IN_PERSON = "in_person", "حضوری"
        ONLINE = "online", "برخط"
        HYBRID = "hybrid", "ترکیبی (حضوری و برخط)"

    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        INVITED = "invited", "دعوت‌نامه فرستاده شد"
        IN_SESSION = "in_session", "در حال برگزاری"
        ENDED = "ended", "پایان یافته"
        CANCELLED = "cancelled", "لغو شده"

    KIND_EN = {Kind.ORDINARY: "Ordinary", Kind.EXTRAORDINARY: "Extraordinary"}
    CALL_EN = {Call.FIRST: "first call", Call.SECOND: "second call"}
    MODE_EN = {Mode.IN_PERSON: "In person", Mode.ONLINE: "Online", Mode.HYBRID: "Hybrid (in person and online)"}
    STATUS_EN = {Status.DRAFT: "Draft", Status.INVITED: "Upcoming", Status.IN_SESSION: "In session",
                 Status.ENDED: "Ended", Status.CANCELLED: "Cancelled"}

    title = models.CharField("عنوان (فارسی)", max_length=200,
                             help_text="مثلاً «مجمع عمومی عادی سالانه ۱۴۰۵»")
    title_en = models.CharField("عنوان (انگلیسی)", max_length=200, blank=True)
    kind = models.CharField("نوع مجمع", max_length=20, choices=Kind.choices, default=Kind.ORDINARY)
    call = models.CharField("نوبت", max_length=10, choices=Call.choices, default=Call.FIRST)
    first_call = models.ForeignKey(
        "self", verbose_name="مجمع نوبت اول", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="second_calls", help_text="برای مجمع نوبت دوم: مجمعی که به حد نصاب نرسید",
    )
    mode = models.CharField("شیوه برگزاری", max_length=20, choices=Mode.choices, default=Mode.ONLINE)
    starts_at = models.DateTimeField("زمان شروع")
    ends_at = models.DateTimeField("زمان پایان (تقریبی)", null=True, blank=True)
    location = models.CharField("محل برگزاری (فارسی)", max_length=255, blank=True)
    location_en = models.CharField("محل برگزاری (انگلیسی)", max_length=255, blank=True)
    meeting_url = models.URLField(
        "پیوند جلسه برخط", blank=True,
        help_text="نشانی جلسه تصویری برای گفتگوی همزمان؛ فقط به اعضای دارای حق رأی در پنل نمایش داده می‌شود",
    )
    description = RichTextField("متن دعوت‌نامه و توضیحات (فارسی)", blank=True)
    description_en = RichTextField("متن دعوت‌نامه و توضیحات (انگلیسی)", blank=True)
    counters = models.CharField("ناظران شمارش آرا", max_length=255, blank=True,
                                help_text="دو ناظر منتخب حاضران (بند ۲-۱)")

    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.DRAFT,
                              db_index=True)
    invited_at = models.DateTimeField("ارسال دعوت‌نامه", null=True, blank=True)
    started_at = models.DateTimeField("آغاز جلسه", null=True, blank=True)
    ended_at = models.DateTimeField("پایان جلسه", null=True, blank=True)
    results_published_at = models.DateTimeField("انتشار نتایج برای اعضا", null=True, blank=True)

    minutes = RichTextField("صورتجلسه (فارسی)", blank=True)
    minutes_en = RichTextField("صورتجلسه (انگلیسی)", blank=True)
    minutes_document = models.ForeignKey(
        "wagtaildocs.Document", verbose_name="فایل صورتجلسه امضاشده", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
        help_text="بهتر است در مجموعه «اسناد اعضا» بارگذاری شود تا فقط اعضا و ارکان آن را ببینند",
    )
    minutes_published = models.BooleanField("صورتجلسه برای اعضا نمایش داده شود", default=False)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="ثبت‌کننده", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)

    panels = [
        MultiFieldPanel([
            FieldPanel("title"), FieldPanel("title_en"),
            FieldRowPanel([FieldPanel("kind"), FieldPanel("call")]),
            FieldPanel("first_call"),
        ], heading="مجمع"),
        MultiFieldPanel([
            FieldRowPanel([FieldPanel("starts_at"), FieldPanel("ends_at")]),
            FieldPanel("mode"),
            FieldPanel("location"), FieldPanel("location_en"),
            FieldPanel("meeting_url"),
        ], heading="زمان و شیوه برگزاری"),
        MultiFieldPanel([FieldPanel("description"), FieldPanel("description_en")], heading="دعوت‌نامه"),
        MultiFieldPanel([
            FieldPanel("counters"),
            FieldPanel("minutes"), FieldPanel("minutes_en"), FieldPanel("minutes_document"),
            FieldPanel("minutes_published"),
        ], heading="صورتجلسه",
            help_text="دبیر مجمع صورتجلسه را تنظیم و امضا می‌کند و ظرف ۷ روز به هیئت مدیره و کمیسیون نظارتی ابلاغ می‌شود"),
    ]

    class Meta:
        verbose_name = "مجمع عمومی"
        verbose_name_plural = "مجامع عمومی"
        ordering = ["-starts_at"]

    def __str__(self):
        return self.title

    def clean(self):
        if self.call == self.Call.SECOND and not self.first_call_id:
            raise ValidationError({"first_call": "برای مجمع نوبت دوم، مجمع نوبت اول را انتخاب کنید."})
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "زمان پایان باید پس از زمان شروع باشد."})

    # ---- labels ----

    @property
    def kind_display(self):
        return _en(self.KIND_EN, self.kind, self.get_kind_display())

    @property
    def call_display(self):
        return _en(self.CALL_EN, self.call, self.get_call_display())

    @property
    def mode_display(self):
        return _en(self.MODE_EN, self.mode, self.get_mode_display())

    @property
    def status_display(self):
        return _en(self.STATUS_EN, self.status, self.get_status_display())

    # ---- state ----

    @property
    def is_open_to_members(self):
        return self.status in (self.Status.INVITED, self.Status.IN_SESSION, self.Status.ENDED)

    @property
    def in_session(self):
        return self.status == self.Status.IN_SESSION

    @property
    def roll_is_frozen(self):
        """The roll and proxies are fixed once the session has started (section 2: proxies before the start)."""
        return self.status in (self.Status.IN_SESSION, self.Status.ENDED, self.Status.CANCELLED)

    @property
    def online_voting(self):
        return self.mode in (self.Mode.ONLINE, self.Mode.HYBRID)

    @property
    def results_published(self):
        return self.results_published_at is not None


class AgendaItem(BilingualMixin, ClusterableModel):
    class Kind(models.TextChoices):
        RESOLUTION = "resolution", "تصمیم (موافق / مخالف / ممتنع)"
        ELECTION = "election", "انتخابات (انتخاب از میان نامزدها)"
        DISCUSSION = "discussion", "گزارش یا گفتگو (بدون رأی)"

    class Majority(models.TextChoices):
        ORDINARY = "ordinary", "عادی (بیش از نصف امتیاز وزنی حاضران)"
        SPECIAL = "special", "دوسوم (اساسنامه، این سند، شکل حقوقی، مأموریت، انحلال)"

    KIND_EN = {Kind.RESOLUTION: "Resolution", Kind.ELECTION: "Election", Kind.DISCUSSION: "Report or discussion"}
    MAJORITY_EN = {Majority.ORDINARY: "Simple majority", Majority.SPECIAL: "Two-thirds majority"}

    assembly = models.ForeignKey(Assembly, verbose_name="مجمع", on_delete=models.CASCADE, related_name="items")
    sort_order = models.PositiveSmallIntegerField("ردیف در دستور جلسه", default=1)
    title = models.CharField("عنوان (فارسی)", max_length=255)
    title_en = models.CharField("عنوان (انگلیسی)", max_length=255, blank=True)
    description = RichTextField("توضیح (فارسی)", blank=True)
    description_en = RichTextField("توضیح (انگلیسی)", blank=True)
    kind = models.CharField("نوع", max_length=20, choices=Kind.choices, default=Kind.RESOLUTION)
    majority = models.CharField("اکثریت لازم", max_length=20, choices=Majority.choices, default=Majority.ORDINARY)
    seats = models.PositiveSmallIntegerField("تعداد کرسی‌ها", default=1,
                                             help_text="برای انتخابات: هر رأی‌دهنده حداکثر به همین تعداد نامزد رأی می‌دهد")
    secret = models.BooleanField("رأی مخفی", default=False,
                                 help_text="انتخابات همیشه مخفی است (بند ۲). در رأی مخفی نام رأی‌دهنده کنار رأی ذخیره نمی‌شود.")
    opens_at = models.DateTimeField("آغاز رأی‌گیری", null=True, blank=True,
                                    help_text="خالی: دبیر مجمع هنگام جلسه رأی‌گیری را باز می‌کند")
    closes_at = models.DateTimeField("پایان رأی‌گیری", null=True, blank=True,
                                     help_text="خالی: تا دبیر مجمع رأی‌گیری را ببندد یا جلسه تمام شود")
    counted_at = models.DateTimeField("شمارش نهایی", null=True, blank=True)
    result = models.JSONField("نتیجه", null=True, blank=True, editable=False)

    panels = [
        FieldPanel("assembly"),
        FieldRowPanel([FieldPanel("sort_order"), FieldPanel("kind")]),
        FieldPanel("title"), FieldPanel("title_en"),
        FieldPanel("description"), FieldPanel("description_en"),
        MultiFieldPanel([
            FieldPanel("majority"), FieldPanel("secret"), FieldPanel("seats"),
            FieldRowPanel([FieldPanel("opens_at"), FieldPanel("closes_at")]),
        ], heading="رأی‌گیری"),
        InlinePanel("options", heading="نامزدها (فقط برای انتخابات)", label="نامزد",
                    help_text="برای تصمیم‌ها گزینه‌های موافق، مخالف و ممتنع خودکار ساخته می‌شوند"),
    ]

    class Meta:
        verbose_name = "بند دستور جلسه"
        verbose_name_plural = "بندهای دستور جلسه"
        ordering = ["assembly", "sort_order", "pk"]

    def __str__(self):
        return f"{self.assembly} | {self.title}"

    def clean(self):
        if self.kind == self.Kind.ELECTION:
            self.secret = True
            if not self.seats:
                raise ValidationError({"seats": "تعداد کرسی‌ها دست‌کم یک است."})
        if self.opens_at and self.closes_at and self.closes_at <= self.opens_at:
            raise ValidationError({"closes_at": "پایان رأی‌گیری باید پس از آغاز آن باشد."})

    def save(self, *args, **kwargs):
        if self.kind == self.Kind.ELECTION:
            self.secret = True
        super().save(*args, **kwargs)

    @property
    def kind_display(self):
        return _en(self.KIND_EN, self.kind, self.get_kind_display())

    @property
    def majority_display(self):
        return _en(self.MAJORITY_EN, self.majority, self.get_majority_display())

    @property
    def has_vote(self):
        return self.kind != self.Kind.DISCUSSION

    @property
    def is_counted(self):
        return self.counted_at is not None

    def voting_state(self, now=None):
        """'none' (no vote), 'waiting', 'open', 'counted' or 'closed' (time passed, not counted yet)."""
        if not self.has_vote:
            return "none"
        if self.is_counted:
            return "counted"
        now = now or timezone.now()
        if self.closes_at and self.closes_at <= now:
            return "closed"
        if self.assembly.in_session and self.opens_at and self.opens_at <= now:
            return "open"
        return "waiting"

    def ballot_options(self):
        """Options a voter may pick from: yes/no/abstain for resolutions, the candidates for elections."""
        if self.kind == self.Kind.RESOLUTION:
            return [o for o in self.options.all() if o.code]
        return [o for o in self.options.all() if not o.code]


class Option(BilingualMixin, Orderable):
    YES, NO, ABSTAIN = "yes", "no", "abstain"
    CODE_LABELS = {YES: ("موافق", "In favour"), NO: ("مخالف", "Against"), ABSTAIN: ("ممتنع", "Abstain")}

    item = ParentalKey(AgendaItem, verbose_name="بند", on_delete=models.CASCADE, related_name="options")
    label = models.CharField("نام نامزد (فارسی)", max_length=200)
    label_en = models.CharField("نام نامزد (انگلیسی)", max_length=200, blank=True)
    note = models.CharField("توضیح کوتاه (فارسی)", max_length=255, blank=True)
    note_en = models.CharField("توضیح کوتاه (انگلیسی)", max_length=255, blank=True)
    member = models.ForeignKey("members.Member", verbose_name="عضو نامزد", null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="+")
    code = models.CharField(max_length=10, blank=True, editable=False)

    panels = [
        FieldRowPanel([FieldPanel("label"), FieldPanel("label_en")]),
        FieldRowPanel([FieldPanel("note"), FieldPanel("note_en")]),
        FieldPanel("member"),
    ]

    class Meta(Orderable.Meta):
        verbose_name = "گزینه"
        verbose_name_plural = "گزینه‌ها"

    def __str__(self):
        return self.label


class Participant(models.Model):
    """A member on the roll of an assembly: a full member with the right to vote when the roll was made."""

    ONLINE, IN_PERSON = "online", "in_person"
    PRESENCE_CHOICES = [("", "غایب"), (ONLINE, "حاضر برخط"), (IN_PERSON, "حاضر در محل")]
    PRESENCE_EN = {"": "Not present", ONLINE: "Present online", IN_PERSON: "Present in person"}

    assembly = models.ForeignKey(Assembly, verbose_name="مجمع", on_delete=models.CASCADE,
                                 related_name="participants")
    member = models.ForeignKey("members.Member", verbose_name="عضو", on_delete=models.CASCADE,
                               related_name="assembly_seats")
    group = models.CharField("گروه رأی", max_length=20, choices=GROUP_CHOICES)
    presence = models.CharField("حضور", max_length=20, choices=PRESENCE_CHOICES, blank=True)
    present_at = models.DateTimeField("زمان اعلام حضور", null=True, blank=True)
    proxy_holder = models.ForeignKey(
        "self", verbose_name="وکیل", null=True, blank=True, on_delete=models.SET_NULL, related_name="proxies_held",
    )
    proxy_reference = models.CharField("شماره یا تاریخ وکالت‌نامه", max_length=200, blank=True)
    invited_at = models.DateTimeField("زمان دعوت", null=True, blank=True)
    reminded_at = models.DateTimeField("زمان یادآوری", null=True, blank=True)

    class Meta:
        verbose_name = "عضو دارای حق رأی"
        verbose_name_plural = "دفتر حاضران"
        ordering = ["group", "member__name"]
        constraints = [models.UniqueConstraint(fields=["assembly", "member"], name="assembly_one_seat_per_member")]

    def __str__(self):
        return f"{self.assembly} | {self.member}"

    @property
    def group_display(self):
        return group_label(self.group)

    @property
    def presence_display(self):
        return _en(self.PRESENCE_EN, self.presence, self.get_presence_display())

    @property
    def is_present(self):
        """Present in person or online, or represented by a proxy holder who is present."""
        if self.presence:
            return True
        return bool(self.proxy_holder_id and self.proxy_holder.presence)

    @property
    def votes_on_paper(self):
        """Votes of members in the room (and of their proxies) are counted on paper by the secretary."""
        holder = self.proxy_holder if self.proxy_holder_id else self
        return holder.presence == self.IN_PERSON


class BallotCast(models.Model):
    """That a member voted on an item (never what they voted, for secret ballots)."""

    item = models.ForeignKey(AgendaItem, verbose_name="بند", on_delete=models.CASCADE, related_name="ballots")
    participant = models.ForeignKey(Participant, verbose_name="رأی‌دهنده", on_delete=models.CASCADE,
                                    related_name="ballots")
    cast_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="ثبت با حساب", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="+")
    by_proxy = models.BooleanField("با وکالت", default=False)
    cast_at = models.DateTimeField("زمان", auto_now_add=True)

    class Meta:
        verbose_name = "ثبت رأی"
        verbose_name_plural = "ثبت آرا"
        constraints = [models.UniqueConstraint(fields=["item", "participant"], name="assembly_one_ballot_per_item")]


class Vote(models.Model):
    """
    One choice in a ballot. For secret items `participant` stays empty and
    the row has a random id and no time, so it cannot be traced back to the
    BallotCast row; only the voting group is kept, for the weighted count.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(AgendaItem, on_delete=models.CASCADE, related_name="votes")
    option = models.ForeignKey(Option, on_delete=models.CASCADE, related_name="votes")
    group = models.CharField(max_length=20, choices=GROUP_CHOICES)
    participant = models.ForeignKey(Participant, null=True, blank=True, on_delete=models.CASCADE,
                                    related_name="open_votes")

    class Meta:
        verbose_name = "رأی"
        verbose_name_plural = "آرا"


class PaperTally(models.Model):
    """Paper ballots counted in the room, entered by the assembly secretary per group and option."""

    item = models.ForeignKey(AgendaItem, on_delete=models.CASCADE, related_name="paper_tallies")
    option = models.ForeignKey(Option, on_delete=models.CASCADE, related_name="paper_tallies")
    group = models.CharField(max_length=20, choices=GROUP_CHOICES)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["item", "option", "group"], name="assembly_one_tally")]
        verbose_name = "شمارش آرای کاغذی"
        verbose_name_plural = "شمارش‌های آرای کاغذی"


class AssemblyLog(models.Model):
    """The record of the session (section 2: records of online sessions are kept)."""

    assembly = models.ForeignKey(Assembly, on_delete=models.CASCADE, related_name="log")
    at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="+")
    text = models.CharField(max_length=500)

    class Meta:
        ordering = ["-at", "-pk"]
        verbose_name = "گزارش جلسه مجمع"
        verbose_name_plural = "گزارش‌های جلسه مجمع"
