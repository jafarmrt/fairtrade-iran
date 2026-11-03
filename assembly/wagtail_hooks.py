from django.contrib import messages
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from wagtail import hooks
from wagtail.admin.ui.components import Component
from wagtail.admin.views.generic import CreateView, EditView
from wagtail.admin.viewsets.model import ModelViewSet

from .admin_views import AssemblyControlViewSet, can_view
from .models import AgendaItem, Assembly
from .services import ensure_resolution_options, log


def control_url(assembly_id):
    return reverse("assembly_control:control", args=[assembly_id])


@hooks.register("register_admin_viewset")
def register_control_viewset():
    return AssemblyControlViewSet()


# ---- assemblies ----


class AssemblyCreateView(CreateView):
    def save_instance(self):
        self.form.instance.created_by = self.request.user
        instance = super().save_instance()
        log(instance, "مجمع ساخته شد.", self.request.user)
        return instance

    def get_success_url(self):
        return control_url(self.object.pk)


class AssemblyEditView(EditView):
    def get_success_url(self):
        return control_url(self.object.pk)


class AssemblyViewSet(ModelViewSet):
    """Assemblies are edited here and run from «مجمع عمومی» (admin_views.control)."""

    model = Assembly
    icon = "group"
    menu_label = "مجامع"
    add_to_admin_menu = False
    copy_view_enabled = False
    inspect_view_enabled = False
    add_view_class = AssemblyCreateView
    edit_view_class = AssemblyEditView
    list_display = ["title", "kind", "call", "starts_at", "status"]
    list_filter = ["status", "kind"]
    search_fields = ["title"]


# ---- agenda items ----


class ItemCreateView(CreateView):
    def get_initial_form_instance(self):
        assembly_id = self.request.GET.get("assembly", "")
        if assembly_id.isdigit():
            instance = AgendaItem(assembly_id=int(assembly_id))
            last = AgendaItem.objects.filter(assembly_id=int(assembly_id)).order_by("-sort_order").first()
            instance.sort_order = (last.sort_order + 1) if last else 1
            return instance
        return super().get_initial_form_instance()

    def save_instance(self):
        instance = super().save_instance()
        ensure_resolution_options(instance)
        log(instance.assembly, f"بند «{instance.title}» به دستور جلسه افزوده شد.", self.request.user)
        return instance

    def get_success_url(self):
        return control_url(self.object.assembly_id)


class ItemEditView(EditView):
    def dispatch(self, request, *args, **kwargs):
        item = AgendaItem.objects.filter(pk=kwargs.get("pk")).first()
        if item is not None and (item.opens_at and item.assembly.in_session or item.is_counted
                                 or item.ballots.exists()):
            messages.error(request, "رأی‌گیری این بند آغاز شده و دیگر ویرایش نمی‌شود.")
            return redirect(control_url(item.assembly_id))
        return super().dispatch(request, *args, **kwargs)

    def save_instance(self):
        instance = super().save_instance()
        ensure_resolution_options(instance)
        return instance

    def get_success_url(self):
        return control_url(self.object.assembly_id)


class AgendaItemViewSet(ModelViewSet):
    model = AgendaItem
    icon = "list-ol"
    menu_label = "بندهای دستور جلسه"
    add_to_admin_menu = False
    copy_view_enabled = False
    inspect_view_enabled = False
    add_view_class = ItemCreateView
    edit_view_class = ItemEditView
    list_display = ["title", "assembly", "kind", "sort_order"]
    list_filter = ["assembly", "kind"]


@hooks.register("register_admin_viewset")
def register_assembly_viewset():
    return AssemblyViewSet("assemblies")


@hooks.register("register_admin_viewset")
def register_item_viewset():
    return AgendaItemViewSet("assembly_items")


# ---- dashboard ----


class AssemblyPanel(Component):
    name = "assembly_now"
    order = 70

    def __init__(self, request):
        self.request = request

    def render_html(self, parent_context=None):
        if not can_view(self.request.user):
            return ""
        current = Assembly.objects.filter(status__in=(Assembly.Status.INVITED, Assembly.Status.IN_SESSION)) \
            .order_by("starts_at")
        if not current:
            return ""
        return render_to_string("assembly/admin/dashboard_panel.html", {"assemblies": current}, request=self.request)


@hooks.register("construct_homepage_panels")
def add_assembly_panel(request, panels):
    panels.append(AssemblyPanel(request))
