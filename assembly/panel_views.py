"""The General Assembly in the member panel: invitations, agenda, attendance, ballots, results and minutes."""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from memberpanel.views import member_view, render, t

from .models import AgendaItem, Assembly, AssemblySettings, BallotCast
from .services import AssemblyError, cast_ballot, check_in_online, finalize_due, has_vote_right, option_label, voting_rights

VISIBLE = (Assembly.Status.INVITED, Assembly.Status.IN_SESSION, Assembly.Status.ENDED)


def _settings(request):
    s = AssemblySettings.load(request_or_site=request)
    if not s.enabled:
        raise Http404
    return s


@member_view(editing=False)
def assembly_list(request, member):
    s = _settings(request)
    assemblies = list(Assembly.objects.filter(status__in=VISIBLE).order_by("-starts_at"))
    seats = {p.assembly_id: p for p in member.assembly_seats.filter(assembly__in=assemblies)}
    for a in assemblies:
        a.seat = seats.get(a.pk)
    return render(request, "assembly/panel_list.html", {
        "member": member, "assemblies": assemblies, "assembly_settings": s, "current": "assembly",
        "can_vote_now": has_vote_right(member),
    })


def _result_rows(item):
    r = item.result or {}
    elected = set(r.get("elected", []))
    rows = []
    for o in r.get("options", []):
        rows.append({"label": option_label(o), "votes": o["votes"], "score": o["score"], "elected": o["id"] in elected,
                     "code": o.get("code", "")})
    return rows


@member_view(editing=False)
def assembly_detail(request, member, pk):
    s = _settings(request)
    assembly = get_object_or_404(Assembly, pk=pk, status__in=VISIBLE)
    finalize_due(assembly)
    seat = member.assembly_seats.filter(assembly=assembly).select_related("proxy_holder__member").first()
    rights = voting_rights(member, assembly) if has_vote_right(member) else []
    items = list(assembly.items.prefetch_related("options"))
    cast = set()
    if rights:
        cast = set(BallotCast.objects.filter(item__assembly=assembly, participant__in=rights)
                   .values_list("item_id", "participant_id"))
    for item in items:
        item.state = item.voting_state()
        item.choices = item.ballot_options()
        item.ballots_for = [{"seat": r, "done": (item.pk, r.pk) in cast, "proxy": r.member_id != member.pk}
                            for r in rights] if item.has_vote else []
        item.pending = [b for b in item.ballots_for if not b["done"]]
        item.result_rows = _result_rows(item) if (item.is_counted and assembly.results_published) else []
    return render(request, "assembly/panel_detail.html", {
        "member": member,
        "assembly": assembly,
        "seat": seat,
        "rights": rights,
        "items": items,
        "assembly_settings": s,
        "current": "assembly",
        "can_check_in": bool(seat and assembly.in_session and assembly.online_voting and not seat.presence
                             and not seat.proxy_holder_id and rights),
        "votes_online": assembly.online_voting and not (seat and seat.votes_on_paper and seat.presence),
    })


@require_POST
@member_view(editing=False)
def assembly_check_in(request, member, pk):
    assembly = get_object_or_404(Assembly, pk=pk, status__in=VISIBLE)
    seat = member.assembly_seats.filter(assembly=assembly).first()
    if seat is None or not has_vote_right(member):
        raise Http404
    try:
        check_in_online(seat, request.user)
    except AssemblyError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, t("حضور شما در جلسه برخط ثبت شد.", "Your attendance at the online session was recorded."))
    return redirect("panel:assembly", member_id=member.pk, pk=assembly.pk)


@require_POST
@member_view(editing=False)
def assembly_vote(request, member, pk, item_id):
    assembly = get_object_or_404(Assembly, pk=pk, status__in=VISIBLE)
    item = get_object_or_404(AgendaItem, pk=item_id, assembly=assembly)
    rights = {r.pk: r for r in voting_rights(member, assembly)} if has_vote_right(member) else {}
    try:
        seat = rights[int(request.POST.get("seat", 0))]
    except (KeyError, ValueError):
        raise Http404
    try:
        ids = [int(v) for v in request.POST.getlist("option")]
    except ValueError:
        ids = []
    if item.kind == AgendaItem.Kind.RESOLUTION and not ids:
        messages.error(request, t("یک گزینه را انتخاب کنید.", "Please choose an option."))
        return redirect(f"{_detail_url(member, assembly)}#item-{item.pk}")
    try:
        cast_ballot(item, seat, request.user, ids, by_proxy=(seat.member_id != member.pk))
    except AssemblyError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, t("رأی شما ثبت شد.", "Your vote was recorded."))
    return redirect(f"{_detail_url(member, assembly)}#item-{item.pk}")


def _detail_url(member, assembly):
    return reverse("panel:assembly", kwargs={"member_id": member.pk, "pk": assembly.pk})
