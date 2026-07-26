"""Thin presentation views for all five workspaces.

Views only parse input and call exactly one service method, then render a
template (Requirement 18.4). No business logic lives here.
"""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.exceptions import DomainError
from core.services import ACTIVE_DEMO_USER_SESSION_KEY

from .services import LandingService


# ─── Home workspace ─────────────────────────────────────────────────────────

def home(request):
    """Render the Home landing page for the active role."""
    landing = LandingService.landing(
        getattr(request, "role_context", None),
        getattr(request, "demo_user_id", None),
    )
    return render(request, "web/home.html", {
        "landing": landing,
        "active_workspace": "home",
    })


@require_POST
def switch_role(request):
    """Switch the active demo role (no authentication, Req 15.2/15.4)."""
    demo_user_id = request.POST.get("demo_user_id")
    try:
        context = LandingService.switch_role(int(demo_user_id or 0))
    except (DomainError, ValueError):
        messages.error(request, "Peran yang dipilih tidak tersedia.")
        return redirect("web:home")

    request.session[ACTIVE_DEMO_USER_SESSION_KEY] = context.demo_user_id
    messages.success(request, f"Sekarang melihat sebagai {context.role_label}.")
    return redirect("web:home")


# ─── Timeline workspace ─────────────────────────────────────────────────────

def timeline_workspace(request):
    """Render the Timeline workspace overview."""
    from timeline.models import OBECycle, TimelineTemplate
    cycles = list(OBECycle.objects.all()[:20])
    templates = list(TimelineTemplate.objects.all()[:20])
    return render(request, "web/timeline.html", {
        "cycles": cycles,
        "templates": templates,
        "active_workspace": "timeline",
    })


def timeline_cycles(request):
    """List OBE cycles."""
    from timeline.models import OBECycle
    cycles = list(OBECycle.objects.all())
    return render(request, "web/timeline_cycles.html", {
        "cycles": cycles,
        "active_workspace": "timeline",
    })


def timeline_templates(request):
    """List timeline templates."""
    from timeline.models import TimelineTemplate
    templates = list(TimelineTemplate.objects.all())
    return render(request, "web/timeline_templates.html", {
        "templates": templates,
        "active_workspace": "timeline",
    })


def timeline_detail(request, pk):
    """Show an OBE cycle with its full phase -> milestone -> task hierarchy."""
    from timeline.models import OBECycle, Phase, TimelineInstance
    cycle = get_object_or_404(OBECycle, pk=pk)
    # Get the timeline instance for this cycle
    try:
        instance = cycle.timeline_instance
        phases = list(
            Phase.objects.filter(instance=instance)
            .prefetch_related("milestones__tasks")
            .order_by("order")
        )
    except TimelineInstance.DoesNotExist:
        phases = []

    return render(request, "web/timeline_detail.html", {
        "cycle": cycle,
        "phases": phases,
        "active_workspace": "timeline",
    })


# ─── Curriculum workspace ────────────────────────────────────────────────────

def curriculum_workspace(request):
    """Render the Curriculum workspace overview."""
    from curriculum.models import Curriculum
    curricula = list(Curriculum.objects.all()[:20])
    return render(request, "web/curriculum.html", {
        "curricula": curricula,
        "active_workspace": "curriculum",
    })


@require_POST
def curriculum_create(request):
    """Create a new curriculum (wizard step 1 - autosave)."""
    from curriculum.services import CurriculumService
    try:
        actor_id = getattr(request, "demo_user_id", None)
        data = {
            "name": request.POST.get("name", "Kurikulum Baru"),
            "year": request.POST.get("year", ""),
            "description": request.POST.get("description", ""),
        }
        CurriculumService.create_curriculum(data, actor_id)
        messages.success(request, "Kurikulum berhasil dibuat.")
    except DomainError as e:
        messages.error(request, e.full_message)
    return redirect("web:curriculum")


@require_POST
def curriculum_activate(request, pk):
    """Activate a curriculum."""
    from curriculum.services import CurriculumService
    try:
        actor_id = getattr(request, "demo_user_id", None)
        CurriculumService.activate_curriculum(pk, actor_id)
        messages.success(request, "Kurikulum berhasil diaktifkan.")
    except DomainError as e:
        messages.error(request, e.full_message)
    return redirect("web:curriculum")


def curriculum_cpls(request, pk):
    """Show CPLs for a curriculum."""
    from curriculum.models import Curriculum
    from curriculum.services import CurriculumService
    curriculum = get_object_or_404(Curriculum, pk=pk)
    cpls = CurriculumService.get_cpls(pk)
    return render(request, "web/curriculum_cpls.html", {
        "cpls": cpls,
        "curriculum": curriculum,
        "curriculum_id": pk,
        "active_workspace": "curriculum",
    })


def curriculum_courses(request, pk):
    """Show courses for a curriculum."""
    from curriculum.models import CPL, Curriculum
    from curriculum.services import CurriculumService
    curriculum = get_object_or_404(Curriculum, pk=pk)
    courses = CurriculumService.get_courses(pk)
    cpls = CurriculumService.get_cpls(pk)
    return render(request, "web/curriculum_courses.html", {
        "courses": courses,
        "cpls": cpls,
        "curriculum": curriculum,
        "curriculum_id": pk,
        "active_workspace": "curriculum",
    })


@require_POST
def curriculum_map_course(request, pk):
    """Map a course to a CPL (wizard step - autosave)."""
    from curriculum.services import CurriculumService
    try:
        actor_id = getattr(request, "demo_user_id", None)
        course_id = int(request.POST.get("course_id", 0))
        cpl_id = int(request.POST.get("cpl_id", 0))
        level = request.POST.get("level", "")
        CurriculumService.map_course_to_cpl(course_id, cpl_id, level, actor_id)
        messages.success(request, "Kontribusi berhasil dipetakan.")
    except DomainError as e:
        messages.error(request, e.full_message)
    return redirect("web:curriculum_courses", pk=pk)


@require_POST
def add_cpl(request, pk):
    """Add a CPL to a curriculum."""
    from curriculum.services import CurriculumService
    try:
        actor_id = getattr(request, "demo_user_id", None)
        data = {
            "code": request.POST.get("code", ""),
            "description": request.POST.get("description", ""),
        }
        CurriculumService.add_cpl(pk, data, actor_id)
        messages.success(request, "CPL berhasil ditambahkan.")
    except DomainError as e:
        messages.error(request, e.full_message)
    return redirect("web:curriculum_cpls", pk=pk)


@require_POST
def add_cpl_indicator(request, cpl_id):
    """Add an indicator to a CPL."""
    from curriculum.models import CPL
    from curriculum.services import CurriculumService
    try:
        actor_id = getattr(request, "demo_user_id", None)
        data = {
            "code": request.POST.get("code", ""),
            "description": request.POST.get("description", ""),
            "target_value": request.POST.get("target_value", "70.00"),
        }
        CurriculumService.add_cpl_indicator(cpl_id, data, actor_id)
        cpl = CPL.objects.get(pk=cpl_id)
        messages.success(request, "Indikator berhasil ditambahkan.")
        return redirect("web:curriculum_cpls", pk=cpl.curriculum_id)
    except DomainError as e:
        messages.error(request, e.full_message)
        return redirect("web:curriculum")


@require_POST
def add_course(request, pk):
    """Add a course to a curriculum."""
    from curriculum.services import CurriculumService
    try:
        actor_id = getattr(request, "demo_user_id", None)
        data = {
            "code": request.POST.get("code", ""),
            "name": request.POST.get("name", ""),
            "credits": int(request.POST.get("credits", 3)),
        }
        CurriculumService.add_course(pk, data, actor_id)
        messages.success(request, "Mata kuliah berhasil ditambahkan.")
    except DomainError as e:
        messages.error(request, e.full_message)
    return redirect("web:curriculum_courses", pk=pk)


# ─── Learning workspace (RPS) ───────────────────────────────────────────────

def learning_workspace(request):
    """Render the Learning workspace overview (RPS list)."""
    from curriculum.models import Course, Curriculum
    from rps.models import RPS
    rps_list = list(RPS.objects.select_related("course", "curriculum").all()[:20])
    curricula = list(Curriculum.objects.all())
    courses = list(Course.objects.all())
    return render(request, "web/learning.html", {
        "rps_list": rps_list,
        "curricula": curricula,
        "courses": courses,
        "active_workspace": "learning",
    })


def rps_detail(request, pk):
    """Show an RPS with its CPMKs, SubCPMKs, instruments, rubrics, and scores."""
    from rps.models import RPS
    rps = get_object_or_404(
        RPS.objects.select_related("course", "curriculum"),
        pk=pk,
    )
    cpmks = list(
        rps.cpmks.prefetch_related(
            "derived_from", "sub_cpmks__indicators"
        ).all()
    )
    instruments = list(
        rps.instruments.prefetch_related(
            "rubric__criteria__levels",
            "rubric__criteria__scores",
            "rubric__criteria__mapped_indicators",
        ).all()
    )
    return render(request, "web/rps_detail.html", {
        "rps": rps,
        "cpmks": cpmks,
        "instruments": instruments,
        "active_workspace": "learning",
    })


@require_POST
def rps_create(request):
    """Create a new RPS (wizard step 1 - autosave)."""
    from rps.services import RPSService
    try:
        actor_id = getattr(request, "demo_user_id", None)
        RPSService.create_rps(
            course_id=int(request.POST.get("course_id", 0)),
            curriculum_id=int(request.POST.get("curriculum_id", 0)),
            class_name=request.POST.get("class_name", ""),
            period=request.POST.get("period", ""),
            actor=actor_id,
        )
        messages.success(request, "RPS berhasil dibuat.")
    except (DomainError, Exception) as e:
        messages.error(request, str(e))
    return redirect("web:learning")


@require_POST
def rps_add_cpmk(request, pk):
    """Add a CPMK to an RPS (wizard step - autosave)."""
    from rps.services import RPSService
    try:
        actor_id = getattr(request, "demo_user_id", None)
        cpl_ids = [int(x) for x in request.POST.getlist("cpl_ids") if x]
        data = {
            "code": request.POST.get("code", ""),
            "description": request.POST.get("description", ""),
        }
        RPSService.add_cpmk(pk, cpl_ids, data, actor_id)
        messages.success(request, "CPMK berhasil ditambahkan.")
    except DomainError as e:
        messages.error(request, e.full_message)
    return redirect("web:rps_detail", pk=pk)


@require_POST
def rps_add_instrument(request, pk):
    """Add an assessment instrument to an RPS."""
    from rps.services import RPSService
    try:
        actor_id = getattr(request, "demo_user_id", None)
        data = {
            "name": request.POST.get("name", ""),
            "description": request.POST.get("description", ""),
        }
        RPSService.add_instrument(pk, data, actor_id)
        messages.success(request, "Instrumen penilaian berhasil ditambahkan.")
    except DomainError as e:
        messages.error(request, e.full_message)
    return redirect("web:rps_detail", pk=pk)


@require_POST
def rps_define_rubric(request, pk):
    """Define a rubric for an RPS instrument (wizard step - autosave)."""
    from rps.services import RPSService
    try:
        actor_id = getattr(request, "demo_user_id", None)
        # Simplified: accept a JSON criteria payload
        import json
        criteria = json.loads(request.POST.get("criteria_json", "[]"))
        instrument_id = int(request.POST.get("instrument_id", 0))
        RPSService.define_rubric(instrument_id, criteria, actor_id)
        messages.success(request, "Rubrik berhasil disimpan.")
    except DomainError as e:
        messages.error(request, e.full_message)
    return redirect("web:rps_detail", pk=pk)


@require_POST
def rps_submit(request, pk):
    """Submit an RPS for review."""
    from rps.services import RPSService
    try:
        actor_id = getattr(request, "demo_user_id", None)
        RPSService.submit_rps(pk, actor_id)
        messages.success(request, "RPS berhasil diajukan.")
    except DomainError as e:
        messages.error(request, e.full_message)
    return redirect("web:rps_detail", pk=pk)


# ─── Attainment & Quality workspace ─────────────────────────────────────────

def attainment_workspace(request):
    """Render the Attainment & Quality workspace."""
    from attainment.models import AttainmentResult
    from timeline.models import OBECycle
    cycles = list(OBECycle.objects.all()[:10])
    results = list(AttainmentResult.objects.all()[:20])
    return render(request, "web/attainment.html", {
        "cycles": cycles,
        "results": results,
        "active_workspace": "attainment",
    })


@require_POST
def attainment_calculate(request, cycle_id):
    """Run attainment calculation for a cycle."""
    from attainment.services import AttainmentService
    try:
        actor_id = getattr(request, "demo_user_id", None)
        result = AttainmentService.calculate(cycle_id, actor_id)
        messages.success(
            request,
            f"Perhitungan selesai. {len(result['results'])} hasil, "
            f"{result['tasks_created']} tugas evaluasi dibuat.",
        )
    except DomainError as e:
        messages.error(request, e.full_message)
    return redirect("web:attainment")
