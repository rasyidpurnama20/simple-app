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
            name='StudentProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('student_number', models.CharField(max_length=32, unique=True)),
                ('cohort', models.PositiveSmallIntegerField()),
                ('curriculum_public_id', models.UUIDField()),
                ('rule_package', models.CharField(default='CURRENT-AABBC', max_length=32)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TaskInstance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('code', models.CharField(max_length=80)),
                ('title', models.CharField(max_length=200)),
                ('entity_type', models.CharField(max_length=80)),
                ('entity_id', models.CharField(max_length=80)),
                ('due_at', models.DateTimeField()),
                ('status', models.CharField(default='not-started', max_length=24)),
                ('priority', models.PositiveSmallIntegerField(default=3)),
                ('dependency_ids', models.JSONField(default=list)),
                ('required_evidence', models.JSONField(default=list)),
                ('idempotency_key', models.CharField(max_length=160, unique=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='obe_tasks', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField()),
                ('idempotency_key', models.CharField(max_length=160, unique=True)),
                ('scheduled_at', models.DateTimeField()),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('snoozed_until', models.DateTimeField(blank=True, null=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='academic_lifecycle.taskinstance')),
            ],
        ),
        migrations.CreateModel(
            name='EnrollmentPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('academic_year', models.CharField(max_length=12)),
                ('semester', models.PositiveSmallIntegerField()),
                ('course_public_ids', models.JSONField(default=list)),
                ('total_credits', models.PositiveSmallIntegerField(default=0)),
                ('decision_snapshot', models.JSONField(default=dict)),
                ('status', models.CharField(default='draft', max_length=24)),
                ('advisor_id', models.CharField(blank=True, max_length=64)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='plans', to='academic_lifecycle.studentprofile')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('student', 'academic_year', 'semester', 'version'), name='student_plan_version_unique')],
            },
        ),
        migrations.CreateModel(
            name='AcademicStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('candidate', 'Calon'), ('active', 'Aktif'), ('absent', 'Mangkir'), ('leave', 'Cuti'), ('suspended', 'Skorsing'), ('transfer', 'Pindah'), ('dropout', 'Putus Studi'), ('graduated', 'Lulus'), ('withdrawn', 'Mengundurkan Diri'), ('deceased', 'Wafat')], max_length=24)),
                ('reason', models.TextField()),
                ('documents', models.JSONField(default=list)),
                ('approved_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='statuses', to='academic_lifecycle.studentprofile')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('student', 'effective_from', 'version'), name='student_status_period_unique')],
            },
        ),
        migrations.CreateModel(
            name='AcademicResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('course_public_id', models.UUIDField()),
                ('academic_year', models.CharField(max_length=12)),
                ('semester', models.PositiveSmallIntegerField()),
                ('attempt', models.PositiveSmallIntegerField(default=1)),
                ('credits', models.PositiveSmallIntegerField()),
                ('letter', models.CharField(max_length=3)),
                ('grade_point', models.DecimalField(decimal_places=2, max_digits=3, null=True)),
                ('passed', models.BooleanField(default=False)),
                ('source_type', models.CharField(default='regular', max_length=24)),
                ('trace', models.JSONField(default=dict)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='results', to='academic_lifecycle.studentprofile')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('student', 'course_public_id', 'attempt'), name='result_attempt_unique')],
            },
        ),
    ]
