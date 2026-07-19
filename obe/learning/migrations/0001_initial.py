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
            name='CourseOffering',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('course_public_id', models.UUIDField(db_index=True)),
                ('academic_year', models.CharField(max_length=12)),
                ('semester', models.CharField(max_length=12)),
                ('class_code', models.CharField(max_length=20)),
                ('parallel_group', models.CharField(blank=True, max_length=40)),
                ('schedule', models.JSONField(blank=True, default=dict)),
                ('room', models.CharField(blank=True, max_length=80)),
                ('capacity', models.PositiveIntegerField(default=40)),
                ('status', models.CharField(default='draft', max_length=20)),
                ('coordinator', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('lecturers', models.ManyToManyField(blank=True, related_name='offerings_taught', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Attendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('student_id', models.CharField(max_length=64)),
                ('activity_id', models.CharField(max_length=64)),
                ('status', models.CharField(choices=[('present', 'Hadir'), ('late', 'Terlambat'), ('permit', 'Izin'), ('sick', 'Sakit'), ('absent', 'Alpa'), ('cancelled', 'Dibatalkan'), ('exempt', 'Pengecualian')], max_length=16)),
                ('occurred_at', models.DateTimeField()),
                ('recorded_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('offering', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='attendance', to='learning.courseoffering')),
            ],
        ),
        migrations.CreateModel(
            name='RPSVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('gpm_review', 'Review GPM'), ('prodi_approval', 'Approval Prodi'), ('published', 'Published'), ('returned', 'Returned')], default='draft', max_length=24)),
                ('content', models.JSONField(default=dict)),
                ('total_assessment_weight', models.DecimalField(decimal_places=3, default=0, max_digits=6)),
                ('approval_snapshot', models.JSONField(blank=True, default=dict)),
                ('revision_reason', models.TextField(blank=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rps_approved', to=settings.AUTH_USER_MODEL)),
                ('authored_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rps_authored', to=settings.AUTH_USER_MODEL)),
                ('offering', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rps_versions', to='learning.courseoffering')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rps_reviewed', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='WeeklyPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('week', models.PositiveSmallIntegerField()),
                ('meeting_type', models.CharField(default='regular', max_length=20)),
                ('outcomes', models.JSONField(default=list)),
                ('indicators', models.JSONField(default=list)),
                ('material', models.TextField()),
                ('methods', models.JSONField(default=list)),
                ('activities', models.JSONField(default=list)),
                ('contact_minutes', models.PositiveIntegerField(default=100)),
                ('structured_minutes', models.PositiveIntegerField(default=120)),
                ('independent_minutes', models.PositiveIntegerField(default=120)),
                ('planned_date', models.DateField(blank=True, null=True)),
                ('actual', models.JSONField(blank=True, default=dict)),
                ('rps', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='weekly_plans', to='learning.rpsversion')),
            ],
        ),
        migrations.AddConstraint(
            model_name='courseoffering',
            constraint=models.UniqueConstraint(fields=('course_public_id', 'academic_year', 'semester', 'class_code'), name='offering_class_unique'),
        ),
        migrations.AddConstraint(
            model_name='attendance',
            constraint=models.UniqueConstraint(fields=('offering', 'student_id', 'activity_id'), name='attendance_once'),
        ),
        migrations.AddConstraint(
            model_name='rpsversion',
            constraint=models.UniqueConstraint(fields=('offering', 'version'), name='rps_offering_version_unique'),
        ),
        migrations.AddConstraint(
            model_name='weeklyplan',
            constraint=models.UniqueConstraint(fields=('rps', 'week'), name='rps_week_unique'),
        ),
    ]
