import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from obe.shared.models import TimeStampedModel, VersionedModel


class AssessmentInstrument(VersionedModel):
    source_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
    offering_public_id = models.UUIDField(db_index=True)
    rps_public_id = models.UUIDField(null=True, blank=True, db_index=True)
    code = models.CharField(max_length=24)
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=30)
    purpose = models.TextField(blank=True)
    participant_scope = models.JSONField(default=dict, blank=True)
    mode = models.CharField(max_length=24, default="onsite")
    weight = models.DecimalField(max_digits=6, decimal_places=3)
    schedule = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=1)
    assessor_id = models.CharField(max_length=64)
    mappings = models.JSONField(default=list)
    blueprint = models.JSONField(default=dict, blank=True)
    rubric = models.JSONField(default=dict, blank=True)
    rubric_public_id = models.UUIDField(null=True, blank=True, db_index=True)
    evidence_required = models.BooleanField(default=True)
    evidence_class = models.CharField(max_length=32, default="assessment")
    status = models.CharField(max_length=20, default="draft")
    published_at = models.DateTimeField(null=True, blank=True)
    first_score_at = models.DateTimeField(null=True, blank=True)
    deadline_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        if not self.code.strip() or not self.title.strip() or not self.purpose.strip():
            raise ValidationError("Kode, judul, dan tujuan instrumen wajib")
        if not self.mappings:
            raise ValidationError("Instrumen wajib memiliki pemetaan outcome")
        if self.status == "published" and not self.published_at:
            raise ValidationError("Waktu publikasi instrumen wajib")

    def save(self, *args, **kwargs):
        if self.pk:
            previous = (
                type(self).objects.filter(pk=self.pk).values("status", "first_score_at").first()
            )
            if previous and (previous["status"] == "published" or previous["first_score_at"]):
                raise ValidationError("Instrumen yang published/dipakai immutable; buat versi baru")
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["offering_public_id", "code", "version"],
                name="instrument_code_version_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(weight__gt=0) & models.Q(weight__lte=100),
                name="instrument_weight_range",
            ),
        ]


class ParallelExamPolicy(VersionedModel):
    program_code = models.CharField(max_length=32)
    strict_same_question = models.BooleanField(default=False)
    disparity_threshold = models.DecimalField(max_digits=6, decimal_places=2, default=10)
    status = models.CharField(
        max_length=16,
        choices=[("draft", "Draft"), ("active", "Active"), ("retired", "Retired")],
        default="draft",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="parallel_exam_policies_created",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="parallel_exam_policies_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        if self.disparity_threshold < 0:
            raise ValidationError("Batas disparity tidak boleh negatif")
        if self.status == "active":
            if not self.approved_by_id or not self.approved_at:
                raise ValidationError("Kebijakan aktif memerlukan approval")
            if self.created_by_id == self.approved_by_id:
                raise ValidationError("Maker dan approver kebijakan harus berbeda")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk, status="active").exists():
            raise ValidationError("Kebijakan aktif immutable; buat versi baru")
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["program_code", "version"], name="parallel_exam_policy_version_unique"
            )
        ]


class QuestionSetVersion(VersionedModel):
    instrument = models.ForeignKey(
        AssessmentInstrument, on_delete=models.PROTECT, related_name="question_sets"
    )
    parallel_group = models.CharField(max_length=80)
    code = models.CharField(max_length=40)
    blueprint_checksum = models.CharField(max_length=64)
    question_checksum = models.CharField(max_length=64)
    coverage = models.JSONField(default=dict)
    difficulty = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("gpm_review", "GPM review"),
            ("approved", "Approved"),
            ("released", "Released"),
        ],
        default="draft",
    )
    authored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="question_sets_authored",
    )

    def clean(self):
        super().clean()
        if not self.parallel_group.strip() or not self.code.strip():
            raise ValidationError("Question set wajib memiliki parallel group dan code")
        for value in (self.blueprint_checksum, self.question_checksum):
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValidationError("Checksum question set harus SHA-256 lowercase")

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] == "released":
                raise ValidationError("Question set released immutable; buat versi baru")
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["instrument", "code", "version"],
                name="question_set_instrument_code_version_unique",
            )
        ]


class ExamEquivalenceReview(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parallel_group = models.CharField(max_length=80)
    exam_code = models.CharField(max_length=24)
    policy = models.ForeignKey(
        ParallelExamPolicy, on_delete=models.PROTECT, related_name="equivalence_reviews"
    )
    question_sets = models.ManyToManyField(QuestionSetVersion, related_name="equivalence_reviews")
    equivalent = models.BooleanField(default=False)
    equivalence_report = models.JSONField(default=dict)
    difference_reason = models.TextField(blank=True)
    result_analysis = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("gpm_reviewed", "GPM reviewed"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="draft",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="exam_equivalence_reviewed",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="exam_equivalence_approved",
    )
    reviewed_at = models.DateTimeField()
    approved_at = models.DateTimeField(null=True, blank=True)


class CompetencyScale(VersionedModel):
    code = models.CharField(max_length=40)
    bands = models.JSONField(default=list)
    status = models.CharField(
        max_length=16,
        choices=[("draft", "Draft"), ("active", "Active"), ("retired", "Retired")],
        default="draft",
    )

    def clean(self):
        super().clean()
        if not self.code.strip() or not isinstance(self.bands, list) or not self.bands:
            raise ValidationError("Skala kompetensi wajib memiliki code dan bands")
        ordered = sorted(self.bands, key=lambda item: Decimal(str(item.get("min", -1))))
        expected = Decimal("0")
        for index, band in enumerate(ordered):
            minimum = Decimal(str(band.get("min", -1)))
            maximum = Decimal(str(band.get("max", -1)))
            if not band.get("code") or minimum != expected or maximum < minimum:
                raise ValidationError("Band kompetensi harus lengkap, berurutan, dan tidak overlap")
            expected = maximum + Decimal("0.01")
            if index == len(ordered) - 1 and maximum != Decimal("100"):
                raise ValidationError("Band kompetensi terakhir harus berakhir pada 100")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk, status="active").exists():
            raise ValidationError("Skala kompetensi aktif immutable; buat versi baru")
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["code", "version"], name="competency_scale_version_unique"
            )
        ]


class Rubric(VersionedModel):
    code = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    kind = models.CharField(
        max_length=20,
        choices=[
            ("analytic", "Analytic"),
            ("holistic", "Holistic"),
            ("checklist", "Checklist"),
            ("numeric", "Numeric"),
            ("pass_fail", "Pass/Fail"),
        ],
    )
    status = models.CharField(max_length=20, default="draft")
    used_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("used_at").first()
            if previous and previous["used_at"]:
                raise ValidationError("Rubrik yang sudah dipakai immutable; buat versi baru")
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["code", "version"], name="rubric_code_version_unique")
        ]


class RubricCriterion(VersionedModel):
    rubric = models.ForeignKey(Rubric, on_delete=models.PROTECT, related_name="criteria")
    code = models.CharField(max_length=32)
    title = models.CharField(max_length=160)
    description = models.TextField()
    weight = models.DecimalField(max_digits=6, decimal_places=2)
    indicator_codes = models.JSONField(default=list)
    sub_outcome_codes = models.JSONField(default=list)
    order = models.PositiveSmallIntegerField(default=1)

    def clean(self):
        super().clean()
        if not self.description.strip() or not self.indicator_codes or not self.sub_outcome_codes:
            raise ValidationError("Kriteria wajib terhubung ke indikator dan Sub-CPMK")
        if not Decimal("0") < self.weight <= Decimal("100"):
            raise ValidationError("Bobot kriteria harus >0 dan <=100")

    def save(self, *args, **kwargs):
        if self.rubric_id and Rubric.objects.filter(pk=self.rubric_id, status="published").exists():
            raise ValidationError("Kriteria rubrik published immutable; buat versi baru")
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["rubric", "code"], name="rubric_criterion_code_unique")
        ]


class PerformanceLevel(VersionedModel):
    rubric = models.ForeignKey(Rubric, on_delete=models.PROTECT, related_name="levels")
    code = models.CharField(max_length=24)
    descriptor = models.TextField()
    minimum = models.DecimalField(max_digits=7, decimal_places=2)
    maximum = models.DecimalField(max_digits=7, decimal_places=2)
    points = models.DecimalField(max_digits=7, decimal_places=2)
    order = models.PositiveSmallIntegerField(default=1)

    def clean(self):
        super().clean()
        if not self.descriptor.strip() or self.maximum < self.minimum:
            raise ValidationError("Descriptor/interval level performa tidak valid")

    def save(self, *args, **kwargs):
        if self.rubric_id and Rubric.objects.filter(pk=self.rubric_id, status="published").exists():
            raise ValidationError("Level rubrik published immutable; buat versi baru")
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["rubric", "code"], name="rubric_level_code_unique")
        ]


class AssessmentItem(VersionedModel):
    instrument = models.ForeignKey(
        AssessmentInstrument, on_delete=models.PROTECT, related_name="items"
    )
    code = models.CharField(max_length=32)
    prompt = models.TextField()
    item_type = models.CharField(max_length=24)
    points = models.DecimalField(max_digits=7, decimal_places=2)
    difficulty = models.CharField(max_length=16, blank=True)
    indicator_codes = models.JSONField(default=list)
    sub_outcome_codes = models.JSONField(default=list)
    answer_key = models.JSONField(default=dict, blank=True)
    order = models.PositiveSmallIntegerField(default=1)

    def clean(self):
        super().clean()
        if not self.prompt.strip() or not self.indicator_codes or not self.sub_outcome_codes:
            raise ValidationError("Butir wajib memiliki isi dan pemetaan outcome")

    def save(self, *args, **kwargs):
        if (
            self.instrument_id
            and AssessmentInstrument.objects.filter(pk=self.instrument_id)
            .filter(models.Q(status="published") | models.Q(first_score_at__isnull=False))
            .exists()
        ):
            raise ValidationError("Butir instrumen published/dipakai immutable")
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["instrument", "code"], name="instrument_item_code_unique"
            )
        ]


class SubmissionGroup(VersionedModel):
    instrument = models.ForeignKey(
        AssessmentInstrument, on_delete=models.PROTECT, related_name="submission_groups"
    )
    code = models.CharField(max_length=40)
    member_ids = models.JSONField(default=list)
    finalized_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        if not self.code.strip() or not isinstance(self.member_ids, list) or not self.member_ids:
            raise ValidationError("Grup submission wajib memiliki code dan anggota")
        if len(self.member_ids) != len(set(self.member_ids)):
            raise ValidationError("Anggota grup submission tidak boleh duplikat")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["instrument", "code", "version"],
                name="submission_group_instrument_code_version_unique",
            )
        ]


class Submission(VersionedModel):
    source_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
    instrument = models.ForeignKey(
        AssessmentInstrument, on_delete=models.PROTECT, related_name="submissions"
    )
    student_id = models.CharField(max_length=64)
    group = models.ForeignKey(
        SubmissionGroup,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="submissions",
    )
    attempt = models.PositiveSmallIntegerField(default=1)
    response = models.JSONField(default=dict)
    evidence_manifest_ids = models.JSONField(default=list)
    status = models.CharField(max_length=20, default="draft")
    submitted_at = models.DateTimeField(null=True, blank=True)
    receipt_checksum = models.CharField(max_length=64, blank=True)
    reopened_reason = models.TextField(blank=True)
    reopened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="submissions_reopened",
    )
    reopened_at = models.DateTimeField(null=True, blank=True)
    late = models.BooleanField(default=False)
    source_version = models.JSONField(default=dict, blank=True)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] == "final" and self.status != "reopened":
                raise ValidationError("Submission final immutable; lakukan reopening resmi")
        if self.status == "final" and (not self.submitted_at or not self.receipt_checksum):
            raise ValidationError("Submission final memerlukan waktu dan receipt checksum")
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["instrument", "student_id", "attempt"], name="submission_attempt_unique"
            )
        ]


class Score(VersionedModel):
    source_id = models.CharField(max_length=120, null=True, blank=True, unique=True)
    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name="scores")
    raw_score = models.DecimalField(max_digits=9, decimal_places=3)
    max_score = models.DecimalField(max_digits=9, decimal_places=3)
    normalized = models.DecimalField(max_digits=6, decimal_places=2)
    attempt = models.PositiveSmallIntegerField(default=1)
    letter = models.CharField(max_length=3, blank=True)
    grade_point = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    state = models.CharField(
        max_length=20,
        choices=[
            ("graded", "Graded"),
            ("absent", "Absent"),
            ("exempt", "Exempt"),
            ("not_graded", "Not graded"),
            ("invalid", "Invalid"),
            ("regraded", "Regraded"),
        ],
        default="graded",
    )
    rubric_trace = models.JSONField(default=dict)
    feedback = models.JSONField(default=dict)
    assessor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    second_assessor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="scores_second_marked",
    )
    moderation_state = models.CharField(max_length=20, default="not_required")
    moderation_comment = models.TextField(blank=True)
    reconciliation = models.JSONField(default=dict, blank=True)
    blind_reference = models.CharField(max_length=80, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    change_reason = models.TextField(blank=True)
    rule_package = models.CharField(max_length=32, default="CURRENT-AABBC")
    rule_package_version = models.PositiveSmallIntegerField(default=1)
    competency_category = models.CharField(max_length=40, blank=True)
    source_version = models.JSONField(default=dict, blank=True)
    calculation_trace = models.JSONField(default=list, blank=True)

    def clean(self):
        super().clean()
        if self.max_score <= 0:
            raise ValidationError("Max score harus lebih dari nol")
        if not Decimal("0") <= self.normalized <= Decimal("100"):
            raise ValidationError("Normalized score harus 0–100")


class ScoreRevision(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    score = models.ForeignKey(Score, on_delete=models.PROTECT, related_name="revision_requests")
    proposed_raw_score = models.DecimalField(max_digits=9, decimal_places=3)
    proposed_max_score = models.DecimalField(max_digits=9, decimal_places=3)
    reason = models.TextField()
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="score_revisions_requested",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="score_revisions_approved",
    )
    status = models.CharField(
        max_length=16,
        choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
        default="pending",
    )
    decision_reason = models.TextField(blank=True)
    recalculation = models.JSONField(default=dict, blank=True)
    notification_key = models.CharField(max_length=160, unique=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if not self.reason.strip() or self.proposed_max_score <= 0:
            raise ValidationError("Revisi nilai memerlukan alasan dan max score valid")
        if self.status == "approved":
            if not self.approved_by_id or not self.decided_at or not self.recalculation:
                raise ValidationError("Revisi approved memerlukan checker dan recalculation")
            if self.approved_by_id == self.requested_by_id:
                raise ValidationError("Pemohon tidak boleh menyetujui revisi nilai sendiri")


class CriterionScore(models.Model):
    score = models.ForeignKey(Score, on_delete=models.PROTECT, related_name="criterion_scores")
    criterion = models.ForeignKey(
        RubricCriterion, on_delete=models.PROTECT, related_name="criterion_scores"
    )
    points = models.DecimalField(max_digits=7, decimal_places=2)
    weighted_score = models.DecimalField(max_digits=7, decimal_places=2)
    feedback = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["score", "criterion"], name="score_criterion_unique")
        ]


class AttainmentSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope_type = models.CharField(max_length=30)
    scope_id = models.CharField(max_length=80)
    outcome_code = models.CharField(max_length=24)
    actual = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    target = models.DecimalField(max_digits=6, decimal_places=2)
    denominator = models.PositiveIntegerField()
    coverage = models.DecimalField(max_digits=6, decimal_places=2)
    formula_version = models.CharField(max_length=40)
    source_versions = models.JSONField(default=dict)
    trace = models.JSONField(default=list)
    blocking_reasons = models.JSONField(default=list)
    generated_at = models.DateTimeField(auto_now_add=True)
