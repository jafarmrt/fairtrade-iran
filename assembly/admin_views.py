"""
Admin: «مجمع عمومی». A list of assemblies and one page per assembly from
which the Assembly Secretary runs it: roll and proxies, invitations,
attendance, opening and closing votes, paper ballots, quorum, results.
"""

import datetime

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from wagtail.admin.menu import MenuItem
from wagtail.admin.viewsets.base import ViewSet

from . import notifications, services
from .models import GROUP_LABELS, GROUPS, Assembly, AssemblySettings, Participant
from .services import AssemblyError, option_label


def can_view(user):
    return user.is_authenticated and user.has_perm("assembly.view_assembly")


def can_run(user):
    return user.is_authenticated and user.has_perm("assembly.change_assembly")


def index(request):
    if not can_view(request.user):
        raise PermissionDenied
    return TemplateResponse(request, "assembly/admin/index.html", {
        "page_title": "مجمع عمومی",
        "header_icon": "group",
        "assemblies": Assembly.objects.all()[:200],
        "can_run": can_run(request.user),
    })


def _group_rows(eligible, present, weights, paper):
    return [{"label": GROUP_LABELS[g][0], "eligible": eligible.get(g, 0), "present": present.get(g, 0),
             "weight": weights[g], "paper": paper.get(g, 0)} for g in GROUPS]


def _act(request, assembly):
    action = request.POST.get("action", "")
    user = request.user
    if action == "roll":
        added, removed = services.build_roll(assembly, user)
        return f"دفتر حاضران به‌روز شد: {added} افزوده، {removed} برداشته."
    if action == "invite":
        sent = services.send_invitations(assembly, user)
        return f"دعوت‌نامه برای {sent} عضو فرستاده شد."
    if action == "start":
        services.start_session(assembly, user)
        return "جلسه آغاز شد."
    if action == "end":
        services.end_session(assembly, user)
        return "جلسه پایان یافت و رأی‌گیری‌های باز شمرده شد."
    if action == "cancel":
        services.cancel(assembly, user)
        return "مجمع لغو شد."
    if action == "publish":
        services.publish_results(assembly, user, notify=bool(request.POST.get("notify")))
        return "نتایج برای اعضا منتشر شد."
    if action == "presence":
        p = get_object_or_404(assembly.participants, pk=request.POST.get("participant"))
        presence = request.POST.get("presence", "")
        if presence not in dict(Participant.PRESENCE_CHOICES):
            raise AssemblyError("حضور نامعتبر است.")
        services.set_presence(p, presence, user)
        return "حضور ثبت شد."
    if action == "proxy":
        principal = get_object_or_404(assembly.participants, pk=request.POST.get("principal"))
        holder = get_object_or_404(assembly.participants, pk=request.POST.get("holder"))
        services.register_proxy(assembly, principal, holder, request.POST.get("reference", "").strip(), user)
        return "وکالت ثبت شد."
    if action == "unproxy":
        principal = get_object_or_404(assembly.participants, pk=request.POST.get("principal"))
        services.remove_proxy(assembly, principal, user)
        return "وکالت برداشته شد."

    item = get_object_or_404(assembly.items, pk=request.POST.get("item"))
    if action == "open":
        minutes = request.POST.get("minutes", "").strip()
        closes = timezone.now() + datetime.timedelta(minutes=int(minutes)) if minutes.isdigit() and int(minutes) else None
        services.open_voting(item, user, closes_at=closes)
        if request.POST.get("notify"):
            notifications.voting_open(item)
        return f"رأی‌گیری «{item.title}» باز شد."
    if action == "close":
        services.close_voting(item, user)
        return f"رأی‌گیری «{item.title}» بسته و شمرده شد."
    if action == "paper":
        data = {}
        for option in item.ballot_options():
            for g in GROUPS:
                raw = request.POST.get(f"t-{option.pk}-{g}", "").strip() or "0"
                if not raw.isdigit():
                    raise AssemblyError("شمار آرا باید عدد باشد.")
                data[(option.pk, g)] = int(raw)
        services.save_paper_tally(item, data, user)
        return "آرای کاغذی ثبت شد."
    raise AssemblyError("اقدام ناشناخته.")


def _named_votes(item):
    """For open (non-secret) votes only: who chose what."""
    if item.secret:
        return []
    rows = {}
    for v in item.votes.select_related("participant__member", "option"):
        rows.setdefault(option_label({"code": v.option.code, "label": v.option.label}), []).append(
            v.participant.member.name if v.participant else "")
    return sorted(rows.items())


def control(request, pk):
    if not can_view(request.user):
        raise PermissionDenied
    assembly = get_object_or_404(Assembly, pk=pk)
    if request.method == "POST":
        if not can_run(request.user):
            raise PermissionDenied
        try:
            done = _act(request, assembly)
        except AssemblyError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, done)
        return redirect(reverse("assembly_control:control", args=[assembly.pk]) + request.POST.get("anchor", ""))

    services.finalize_due(assembly)
    settings = AssemblySettings.load()
    q = services.quorum_now(assembly, settings)
    paper = services.paper_voters(assembly)
    items = list(assembly.items.prefetch_related("options", "paper_tallies"))
    for item in items:
        item.state = item.voting_state()
        item.ballot_count = item.ballots.count()
        item.editable = (item.state in ("waiting", "none") and not item.ballot_count
                         and not (item.opens_at and assembly.in_session) and not item.is_counted)
        item.choices = item.ballot_options()
        tallies = {(t.option_id, t.group): t.count for t in item.paper_tallies.all()}
        item.paper_rows = [{"option": o, "label": option_label({"code": o.code, "label": o.label}),
                            "cells": [{"group": g, "value": tallies.get((o.pk, g), 0)} for g in GROUPS]}
                           for o in item.choices]
        r = item.result or {}
        item.result_rows = [{"label": option_label(o), "counts": [o["counts"].get(g, 0) for g in GROUPS],
                             "votes": o["votes"], "score": o["score"], "elected": o["id"] in r.get("elected", [])}
                            for o in r.get("options", [])]
        item.named_votes = _named_votes(item) if item.is_counted else []
    participants = list(assembly.participants.select_related("member", "proxy_holder__member"))
    return TemplateResponse(request, "assembly/admin/control.html", {
        "page_title": f"مجمع عمومی: {assembly.title}",
        "header_icon": "group",
        "assembly": assembly,
        "settings": settings,
        "warnings": services.notice_warning(assembly, settings),
        "quorum": q,
        "groups": _group_rows(q["eligible"], q["present"], settings.weights, paper),
        "group_labels": [GROUP_LABELS[g][0] for g in GROUPS],
        "has_paper": assembly.mode != Assembly.Mode.ONLINE,
        "items": items,
        "participants": participants,
        "presence_choices": Participant.PRESENCE_CHOICES,
        "log": assembly.log.select_related("user")[:200],
        "can_run": can_run(request.user),
        "can_publish": (not assembly.results_published and (
            assembly.status == Assembly.Status.ENDED
            or (assembly.status == Assembly.Status.IN_SESSION and items
                and all(i.is_counted for i in items if i.has_vote)))),
        "S": Assembly.Status,
    })


class AssemblyMenuItem(MenuItem):
    def is_shown(self, request):
        return can_view(request.user)


class AssemblyControlViewSet(ViewSet):
    name = "assembly_control"
    icon = "group"
    menu_label = "مجمع عمومی"
    menu_order = 270
    add_to_admin_menu = True

    def get_urlpatterns(self):
        return [
            path("", index, name="index"),
            path("<int:pk>/", control, name="control"),
        ]

    @property
    def menu_url(self):
        return reverse(self.get_url_name("index"))

    @property
    def menu_item_class(self):
        return AssemblyMenuItem
