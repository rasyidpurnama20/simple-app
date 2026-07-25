"""Test helpers for building Timeline_Engine fixtures.

These builders create prodi/users and template/instance structures directly
through the ORM so property-based tests can generate random timeline shapes.
"""

from __future__ import annotations

from core.models import DemoUser, ProgramOfStudy, Role
from timeline.models import (
    ChecklistItem,
    DependencyKind,
    Milestone,
    Phase,
    Task,
    TaskDependency,
    TaskStatus,
    TimelineInstance,
    TimelineTemplate,
    OBECycle,
)

_counter = {"n": 0}


def _uniq(prefix: str) -> str:
    _counter["n"] += 1
    return f"{prefix}-{_counter['n']}"


def make_prodi() -> ProgramOfStudy:
    return ProgramOfStudy.objects.create(code=_uniq("P"), name="Prodi Uji")


def make_user(prodi=None, role=Role.KAPRODI) -> DemoUser:
    prodi = prodi or make_prodi()
    return DemoUser.objects.create(name=_uniq("User"), role=role, prodi=prodi)


def build_template(structure, checklist_per_task=2, edges=None) -> tuple[TimelineTemplate, list[Task]]:
    """Build a template from a nested ``structure`` spec.

    ``structure`` is a list of phases; each phase is a list of milestones; each
    milestone is an integer count of tasks. ``edges`` is a list of
    ``(pred_index, succ_index, kind)`` tuples over the flat task list.

    Returns the template and the flat list of created tasks (in creation order).
    """
    template = TimelineTemplate.objects.create(name=_uniq("Template"))
    tasks: list[Task] = []
    for pi, phase_spec in enumerate(structure):
        phase = Phase.objects.create(template=template, name=_uniq("Phase"), order=pi)
        for mi, task_count in enumerate(phase_spec):
            milestone = Milestone.objects.create(
                phase=phase, name=_uniq("MS"), order=mi
            )
            for ti in range(task_count):
                task = Task.objects.create(
                    milestone=milestone,
                    title=_uniq("Task"),
                    order=ti,
                    explanation_what="apa", explanation_why="mengapa",
                    explanation_who="siapa", explanation_when="kapan",
                    explanation_how="bagaimana", explanation_next="berikutnya",
                )
                for ci in range(checklist_per_task):
                    ChecklistItem.objects.create(
                        task=task, text=_uniq("Item"), order=ci
                    )
                tasks.append(task)

    for (pi, si, kind) in edges or []:
        TaskDependency.objects.create(
            predecessor=tasks[pi], successor=tasks[si], kind=kind
        )
    return template, tasks


def make_instance(cycle_name=None) -> TimelineInstance:
    """Create a bare TimelineInstance bound to a fresh cycle."""
    user = make_user()
    cycle = OBECycle.objects.create(
        name=cycle_name or _uniq("Cycle"),
        prodi=user.prodi, owner=user, creator=user, status="active",
    )
    return TimelineInstance.objects.create(cycle=cycle)


def add_task(instance, status=TaskStatus.BELUM_SIAP, owner=None, **kwargs) -> Task:
    """Add a single task under a fresh phase/milestone of an instance."""
    phase = Phase.objects.create(instance=instance, name=_uniq("Phase"))
    milestone = Milestone.objects.create(phase=phase, name=_uniq("MS"))
    defaults = dict(
        explanation_what="", explanation_why="", explanation_who="",
        explanation_when="", explanation_how="", explanation_next="",
    )
    defaults.update(kwargs)
    return Task.objects.create(
        milestone=milestone, title=_uniq("Task"), status=status, owner=owner,
        **defaults,
    )
