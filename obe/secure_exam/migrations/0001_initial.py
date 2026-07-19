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
            name='Exam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('offering_public_id', models.UUIDField()),
                ('title', models.CharField(max_length=200)),
                ('blueprint', models.JSONField(default=dict)),
                ('item_versions', models.JSONField(default=list)),
                ('roster_hash', models.CharField(max_length=64)),
                ('duration_minutes', models.PositiveSmallIntegerField()),
                ('policies', models.JSONField(default=dict)),
                ('classification', models.CharField(default='restricted-exam', max_length=32)),
                ('status', models.CharField(default='draft', max_length=24)),
                ('signature', models.CharField(blank=True, max_length=128)),
                ('approved_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='exams_approved', to=settings.AUTH_USER_MODEL)),
                ('authored_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='exams_authored', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='exams_reviewed', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ExamSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('participant_id', models.CharField(max_length=80)),
                ('session_code_hash', models.CharField(max_length=64)),
                ('device_id', models.CharField(max_length=80)),
                ('seat', models.CharField(blank=True, max_length=20)),
                ('state', models.CharField(default='issued', max_length=24)),
                ('starts_at', models.DateTimeField()),
                ('ends_at', models.DateTimeField()),
                ('finalized_at', models.DateTimeField(blank=True, null=True)),
                ('incident_log', models.JSONField(default=list)),
                ('exam', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sessions', to='secure_exam.exam')),
            ],
        ),
        migrations.CreateModel(
            name='ExamResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item_id', models.CharField(max_length=80)),
                ('version', models.PositiveIntegerField()),
                ('idempotency_key', models.CharField(max_length=160, unique=True)),
                ('response_ciphertext', models.TextField()),
                ('checksum', models.CharField(max_length=64)),
                ('saved_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='responses', to='secure_exam.examsession')),
            ],
        ),
        migrations.AddConstraint(
            model_name='examsession',
            constraint=models.UniqueConstraint(fields=('exam', 'participant_id'), name='exam_participant_unique'),
        ),
        migrations.AddConstraint(
            model_name='examsession',
            constraint=models.UniqueConstraint(condition=models.Q(('state__in', ['active', 'reconnected'])), fields=('exam', 'device_id'), name='active_exam_device_unique'),
        ),
        migrations.AddConstraint(
            model_name='examresponse',
            constraint=models.UniqueConstraint(fields=('session', 'item_id', 'version'), name='exam_response_version_unique'),
        ),
    ]
