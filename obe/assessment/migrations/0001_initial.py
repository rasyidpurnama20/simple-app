import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AttainmentSnapshot',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('scope_type', models.CharField(max_length=30)),
                ('scope_id', models.CharField(max_length=80)),
                ('outcome_code', models.CharField(max_length=24)),
                ('actual', models.DecimalField(decimal_places=2, max_digits=6, null=True)),
                ('target', models.DecimalField(decimal_places=2, max_digits=6)),
                ('denominator', models.PositiveIntegerField()),
                ('coverage', models.DecimalField(decimal_places=2, max_digits=6)),
                ('formula_version', models.CharField(max_length=40)),
                ('source_versions', models.JSONField(default=dict)),
                ('trace', models.JSONField(default=list)),
                ('blocking_reasons', models.JSONField(default=list)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='AssessmentInstrument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('offering_public_id', models.UUIDField(db_index=True)),
                ('code', models.CharField(max_length=24)),
                ('title', models.CharField(max_length=200)),
                ('kind', models.CharField(max_length=30)),
                ('weight', models.DecimalField(decimal_places=3, max_digits=6)),
                ('schedule', models.DateTimeField()),
                ('attempts', models.PositiveSmallIntegerField(default=1)),
                ('assessor_id', models.CharField(max_length=64)),
                ('mappings', models.JSONField(default=list)),
                ('rubric', models.JSONField(default=dict)),
                ('evidence_required', models.BooleanField(default=True)),
                ('status', models.CharField(default='draft', max_length=20)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('offering_public_id', 'code', 'version'), name='instrument_code_version_unique'), models.CheckConstraint(condition=models.Q(('weight__gt', 0), ('weight__lte', 100)), name='instrument_weight_range')],
            },
        ),
        migrations.CreateModel(
            name='Submission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('student_id', models.CharField(max_length=64)),
                ('attempt', models.PositiveSmallIntegerField(default=1)),
                ('response', models.JSONField(default=dict)),
                ('evidence_manifest_ids', models.JSONField(default=list)),
                ('status', models.CharField(default='draft', max_length=20)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('receipt_checksum', models.CharField(blank=True, max_length=64)),
                ('reopened_reason', models.TextField(blank=True)),
                ('instrument', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='submissions', to='assessment.assessmentinstrument')),
            ],
        ),
        migrations.CreateModel(
            name='Score',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('raw_score', models.DecimalField(decimal_places=3, max_digits=9)),
                ('max_score', models.DecimalField(decimal_places=3, max_digits=9)),
                ('normalized', models.DecimalField(decimal_places=2, max_digits=6)),
                ('letter', models.CharField(blank=True, max_length=3)),
                ('grade_point', models.DecimalField(blank=True, decimal_places=2, max_digits=3, null=True)),
                ('state', models.CharField(default='graded', max_length=20)),
                ('rubric_trace', models.JSONField(default=dict)),
                ('feedback', models.JSONField(default=dict)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('change_reason', models.TextField(blank=True)),
                ('assessor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='scores', to='assessment.submission')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddConstraint(
            model_name='submission',
            constraint=models.UniqueConstraint(fields=('instrument', 'student_id', 'attempt'), name='submission_attempt_unique'),
        ),
    ]
