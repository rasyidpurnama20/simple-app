"""Timeline_Engine models.

Implements the Timeline_Engine data model (Task 2.1):

* ``OBECycle`` - a time-bounded run of the OBE process (a business entity that
  carries the seven Production_Readiness_Fields).
* ``TimelineTemplate`` - a reusable structure (template rows) used to
  instantiate a ``TimelineInstance``. Template/structure rows are *not*
  business entities, so they use a lightweight ``template`` flag rather than
  the production-readiness base.
* ``TimelineInstance`` - a concrete run bound 1:1 to an ``OBECycle``.
* ``Phase`` / ``Milestone`` / ``Task`` / ``ChecklistItem`` - the timeline
  hierarchy. Each structural row belongs to *either* a template *or* an
  instance (never both), which lets the same tables hold both template
  definitions and instantiated runs.
* ``TaskDependency`` - a hard|soft edge between two tasks.
* ``ScheduleChange`` - a non-destructive audit record of a deadline change.

All human-facing status values use the eight-member ``TaskStatus`` enum with
the Bahasa Indonesia labels required by Requirement 2.1.
"""

from __future__ import annotations

from django.db import models

from core.models import DemoUser, ProductionReadinessModel


class TaskStatus(models.TextChoices):
    """The eight human-friendly task statuses (Requirement 2.1)."""

    BELUM_SIAP = "belum_siap", "Belum Siap"
    SIAP_DIKERJAKAN = "siap_dikerjakan", "Siap Dikerjakan"
    DIKERJAKAN = "dikerjakan", "Dikerjakan"
    DIAJUKAN = "diajukan", "Diajukan"
    PERLU_REVISI = "perlu_revisi", "Perlu Revisi"
    SELESAI = "selesai", "Selesai"
    TERHAMBAT = "terhambat", "Terhambat"
    TERLAMBAT = "terlambat", "Terlambat"


class DeadlineKind(models.TextChoices):
    """A task deadline is either an absolute date or an offset from a reference."""

    FIXED = "fixed", "Tanggal Tetap"
    RELATIVE = "relative", "Tanggal Relatif"


class DependencyKind(models.TextChoices):
    """Hard dependencies block work; soft dependencies only advise."""

    HARD = "hard", "Hard"
    SOFT = "soft", "Soft"


class OBECycle(ProductionReadinessModel):
    """A time-bounded run of the OBE process for a program of study.

    Carries the Production_Readiness_Fields via ``ProductionReadinessModel``
    (Requirement 1.3). Bound 1:1 to a ``TimelineInstance`` (Requirement 1.2).
    """

    name = models.CharField(max_length=255)
    academic_year = models.CharField(max_length=32, blank=True)
    start_date = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "OBE Cycle"
        verbose_name_plural = "OBE Cycles"
        ordering = ["-created_time"]

    def __str__(self) -> str:
        return self.name


class TimelineTemplate(models.Model):
    """A reusable definition of phases/milestones/tasks/checklists/dependencies.

    A template is structural configuration (not a business entity), so it uses
    a simple ``is_template`` flag and does not carry Production_Readiness_Fields.
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    is_template = models.BooleanField(default=True)
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Timeline Template"
        verbose_name_plural = "Timeline Templates"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class TimelineInstance(models.Model):
    """A concrete run instantiated from a template and bound to one cycle."""

    template = models.ForeignKey(
        TimelineTemplate,
        on_delete=models.PROTECT,
        related_name="instances",
        null=True,
        blank=True,
    )
    cycle = models.OneToOneField(
        OBECycle,
        on_delete=models.CASCADE,
        related_name="timeline_instance",
    )
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Timeline Instance"
        verbose_name_plural = "Timeline Instances"
        ordering = ["-created_time"]

    def __str__(self) -> str:
        return f"Instance of {self.template_id} for {self.cycle_id}"


class Phase(models.Model):
    """A top-level stage grouping milestones.

    Belongs to exactly one of ``template`` (a template definition) or
    ``instance`` (an instantiated run).
    """

    template = models.ForeignKey(
        TimelineTemplate,
        on_delete=models.CASCADE,
        related_name="phases",
        null=True,
        blank=True,
    )
    instance = models.ForeignKey(
        TimelineInstance,
        on_delete=models.CASCADE,
        related_name="phases",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.name


class Milestone(models.Model):
    """A dated checkpoint within a Phase that groups tasks."""

    phase = models.ForeignKey(
        Phase,
        on_delete=models.CASCADE,
        related_name="milestones",
    )
    name = models.CharField(max_length=255)
    milestone_date = models.DateField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.name


class Task(models.Model):
    """A unit of work with an owner, status, dependencies, and guidance."""

    milestone = models.ForeignKey(
        Milestone,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    title = models.CharField(max_length=255)
    owner = models.ForeignKey(
        DemoUser,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=32,
        choices=TaskStatus.choices,
        default=TaskStatus.BELUM_SIAP,
    )
    is_complete = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    # --- Deadline (fixed or relative) (Requirement 3.4) ---
    deadline_kind = models.CharField(
        max_length=16,
        choices=DeadlineKind.choices,
        default=DeadlineKind.FIXED,
    )
    fixed_date = models.DateField(null=True, blank=True)
    relative_offset_days = models.IntegerField(null=True, blank=True)
    relative_reference_milestone = models.ForeignKey(
        Milestone,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    relative_reference_task = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    resolved_deadline = models.DateField(null=True, blank=True)

    # --- Six-facet explanation (Requirements 4.5, 13.2, 14.1) ---
    explanation_what = models.TextField(blank=True)
    explanation_why = models.TextField(blank=True)
    explanation_who = models.TextField(blank=True)
    explanation_when = models.TextField(blank=True)
    explanation_how = models.TextField(blank=True)
    explanation_next = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.title


class ChecklistItem(models.Model):
    """An ordered completion item belonging to a Task."""

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="checklist_items",
    )
    text = models.CharField(max_length=255)
    is_complete = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.text


class TaskDependency(models.Model):
    """A hard|soft dependency edge from a predecessor to a successor task."""

    predecessor = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="dependents",
    )
    successor = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="dependencies",
    )
    kind = models.CharField(
        max_length=8,
        choices=DependencyKind.choices,
        default=DependencyKind.HARD,
    )

    class Meta:
        verbose_name = "Task Dependency"
        verbose_name_plural = "Task Dependencies"
        constraints = [
            models.UniqueConstraint(
                fields=["predecessor", "successor", "kind"],
                name="uniq_taskdependency_edge",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.predecessor_id} -> {self.successor_id} ({self.kind})"


class ScheduleChange(models.Model):
    """A non-destructive audit record of a schedule change (Requirement 5).

    Targets either a ``task`` or a ``milestone``. Retains the previous value,
    the new value, the actor, the timestamp, and a required reason.
    """

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="schedule_changes",
        null=True,
        blank=True,
    )
    milestone = models.ForeignKey(
        Milestone,
        on_delete=models.CASCADE,
        related_name="schedule_changes",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        DemoUser,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    previous_value = models.DateField(null=True, blank=True)
    new_value = models.DateField(null=True, blank=True)
    reason = models.TextField()

    class Meta:
        verbose_name = "Schedule Change"
        verbose_name_plural = "Schedule Changes"
        ordering = ["-timestamp", "-id"]

    def __str__(self) -> str:
        return f"Change @ {self.timestamp:%Y-%m-%d %H:%M}"
