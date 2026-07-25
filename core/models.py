"""Core / shared domain models for the OBE_System.

Contains the abstract ``ProductionReadinessModel`` base carried by every
business entity, plus the shared reference entities: ``ProgramOfStudy``,
``DemoUser`` (role, no real auth), ``ConfigRecord`` (versioned rules /
standards / formulas), and ``DataInjectionLog``.
"""

from __future__ import annotations

from django.db import models


class Role(models.TextChoices):
    """Demo roles. There is NO real authentication (Requirement 15.4)."""

    KAPRODI = "kaprodi", "Kaprodi"
    LECTURER = "lecturer", "Dosen Pengampu"
    DEV_ADMIN = "dev_admin", "Dev Administrator"


class ProgramOfStudy(models.Model):
    """A program of study (prodi) that scopes cycles, curricula and RPS."""

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)
    faculty = models.CharField(max_length=255, blank=True)
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Program of Study"
        verbose_name_plural = "Programs of Study"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class DemoUser(models.Model):
    """A demo user with a role. Used by the Role_Switcher; no credentials.

    This model is intentionally isolated so a real authentication user model
    can replace it later without touching the service layer (Requirement 15.4).
    """

    name = models.CharField(max_length=255)
    role = models.CharField(max_length=32, choices=Role.choices)
    prodi = models.ForeignKey(
        ProgramOfStudy,
        on_delete=models.PROTECT,
        related_name="demo_users",
        null=True,
        blank=True,
    )
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Demo User"
        verbose_name_plural = "Demo Users"
        ordering = ["role", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_role_display()})"


class ProductionReadinessModel(models.Model):
    """Abstract base carrying the seven Production_Readiness_Fields.

    Every persisted business entity extends this base so the development-only
    data model can be promoted to production without restructuring
    (Requirements 1.3, 6.3, 8.4, 9.4).
    """

    prodi = models.ForeignKey(
        ProgramOfStudy,
        on_delete=models.PROTECT,
        related_name="+",
    )
    owner = models.ForeignKey(
        DemoUser,
        on_delete=models.PROTECT,
        related_name="+",
    )
    status = models.CharField(max_length=32)  # lifecycle per entity type
    version = models.PositiveIntegerField(default=1)
    creator = models.ForeignKey(
        DemoUser,
        on_delete=models.PROTECT,
        related_name="+",
    )
    created_time = models.DateTimeField(auto_now_add=True)
    modified_time = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ConfigRecord(models.Model):
    """A versioned configuration record.

    Stores standards, Calculation_Formula definitions, and validation rules as
    versioned, auditable configuration (Requirement 18.2). Each ``key`` may
    have many versions; at most one is active at a time.
    """

    class Category(models.TextChoices):
        RULE = "rule", "Validation Rule"
        STANDARD = "standard", "Standard"
        FORMULA = "formula", "Calculation Formula"

    key = models.CharField(max_length=128)
    category = models.CharField(
        max_length=32,
        choices=Category.choices,
        default=Category.RULE,
    )
    version = models.PositiveIntegerField(default=1)
    definition = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Configuration Record"
        verbose_name_plural = "Configuration Records"
        ordering = ["key", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["key", "version"],
                name="uniq_configrecord_key_version",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.key} v{self.version}"


class DataInjectionLog(models.Model):
    """A record of every synthetic-data load or reset (Requirement 17.3)."""

    class Operation(models.TextChoices):
        LOAD = "load", "Load"
        RESET = "reset", "Reset"

    operation = models.CharField(
        max_length=16,
        choices=Operation.choices,
        default=Operation.LOAD,
    )
    command = models.CharField(max_length=255, blank=True)
    summary = models.TextField(blank=True)
    record_count = models.PositiveIntegerField(default=0)
    created_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Data Injection Log"
        verbose_name_plural = "Data Injection Logs"
        ordering = ["-created_time"]

    def __str__(self) -> str:
        return f"{self.get_operation_display()} @ {self.created_time:%Y-%m-%d %H:%M}"
