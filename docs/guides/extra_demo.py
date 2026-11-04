# Extra demo data for the guide screenshots (demo database only). Run with manage.py shell < this file.
import datetime
from django.utils import timezone
from django.contrib.auth import get_user_model
from core.models import MembershipSettings
from members.models import Member
from standing import services as st
from standing.models import Dues
from assembly.models import Assembly, AgendaItem, Option
from assembly import services as asv

admin = get_user_model().objects.get(username="demo-admin")
ms = MembershipSettings.load()
for f, v in [("application_fee_producer", 5_000_000), ("annual_fee_producer", 20_000_000),
             ("application_fee_institution", 10_000_000), ("annual_fee_institution", 40_000_000),
             ("application_fee_network", 10_000_000), ("annual_fee_network", 40_000_000),
             ("application_fee_individual", 2_000_000), ("annual_fee_individual", 5_000_000)]:
    if hasattr(ms, f) and not getattr(ms, f):
        setattr(ms, f, v)
for f, v in [("bank_name", "بانک نمونه"),
             ("sheba", "IR000000000000000000000000")]:
    if hasattr(ms, f) and not getattr(ms, f):
        setattr(ms, f, v)
ms.save()

armoz = Member.objects.get(name="ارموز")
today = datetime.date.today()
if not Dues.objects.filter(member=armoz).exists():
    st.create_dues(armoz, 1405, today - datetime.timedelta(days=20), ms, due_date=today + datetime.timedelta(days=10))
papital = Member.objects.get(name="پاپیتال")
if not Dues.objects.filter(member=papital).exists():
    d, _ = st.create_dues(papital, 1405, today - datetime.timedelta(days=40), ms, due_date=today - datetime.timedelta(days=5))

if not Assembly.objects.exists():
    a = Assembly.objects.create(
        title="مجمع عمومی عادی سالانه ۱۴۰۵", title_en="Annual ordinary general assembly 1405",
        kind=Assembly.Kind.ORDINARY, mode=Assembly.Mode.HYBRID,
        starts_at=timezone.now() - datetime.timedelta(minutes=30), ends_at=timezone.now() + datetime.timedelta(hours=2),
        location="تهران، دفتر خانه", meeting_url="https://meet.example.org/fairtrade", created_by=admin)
    AgendaItem.objects.create(assembly=a, sort_order=1, title="گزارش هیئت مدیره از کارهای سال", kind=AgendaItem.Kind.DISCUSSION)
    item = AgendaItem.objects.create(assembly=a, sort_order=2, title="تصویب بودجه سال ۱۴۰۶", kind=AgendaItem.Kind.RESOLUTION)
    el = AgendaItem.objects.create(assembly=a, sort_order=3, title="انتخاب اعضای کمیسیون نظارتی", kind=AgendaItem.Kind.ELECTION, seats=2)
    for n in ["نامزد نمونه یک", "نامزد نمونه دو", "نامزد نمونه سه"]:
        Option.objects.create(item=el, label=n)
    asv.ensure_resolution_options(item)
    asv.send_invitations(a, admin)
    asv.start_session(a, admin)
    asv.open_voting(item, admin, closes_at=timezone.now() + datetime.timedelta(hours=1))
from sms.models import SmsSettings
from memberpanel.models import PanelSettings
_s = SmsSettings.load(); _s.enabled = True; _s.provider = "console"; _s.save()
_p = PanelSettings.load(); _p.sms_login = True; _p.save()
print("extra demo ok")
