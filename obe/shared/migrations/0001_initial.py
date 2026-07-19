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
            name='OutboxEvent',
            fields=[
                ('event_id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(db_index=True, max_length=160)),
                ('aggregate_id', models.CharField(db_index=True, max_length=80)),
                ('aggregate_version', models.PositiveIntegerField(default=1)),
                ('occurred_at', models.DateTimeField(auto_now_add=True)),
                ('actor_id', models.CharField(blank=True, max_length=64)),
                ('correlation_id', models.UUIDField(db_index=True, default=uuid.uuid4)),
                ('payload_schema', models.CharField(default='1.0', max_length=40)),
                ('payload', models.JSONField(default=dict)),
                ('sensitivity', models.CharField(default='internal', max_length=32)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'ordering': ['occurred_at'],
            },
        ),
        migrations.CreateModel(
            name='AuditEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('occurred_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('actor_id', models.CharField(blank=True, max_length=64)),
                ('actor_label', models.CharField(blank=True, max_length=160)),
                ('actor_scope', models.CharField(blank=True, max_length=160)),
                ('action', models.CharField(db_index=True, max_length=120)),
                ('object_type', models.CharField(db_index=True, max_length=120)),
                ('object_id', models.CharField(db_index=True, max_length=80)),
                ('summary', models.CharField(max_length=255)),
                ('before', models.JSONField(blank=True, default=dict)),
                ('after', models.JSONField(blank=True, default=dict)),
                ('reason', models.TextField(blank=True)),
                ('correlation_id', models.UUIDField(db_index=True, default=uuid.uuid4)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=255)),
                ('outcome', models.CharField(default='success', max_length=40)),
                ('integrity_hash', models.CharField(blank=True, max_length=64)),
            ],
            options={
                'ordering': ['-occurred_at'],
                'indexes': [models.Index(fields=['object_type', 'object_id', 'occurred_at'], name='shared_audi_object__49ec3b_idx')],
            },
        ),
        migrations.CreateModel(
            name='FeatureFlag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('code', models.SlugField(max_length=100)),
                ('state', models.CharField(choices=[('disabled', 'Disabled'), ('internal', 'Internal'), ('pilot', 'Pilot'), ('general', 'General'), ('deprecated', 'Deprecated'), ('retired', 'Retired')], default='disabled', max_length=20)),
                ('scope', models.JSONField(blank=True, default=dict)),
                ('owner', models.CharField(max_length=160)),
                ('acceptance_evidence', models.TextField(blank=True)),
                ('rollback_plan', models.TextField(blank=True)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('code', 'version'), name='flag_version_unique')],
            },
        ),
        migrations.CreateModel(
            name='FileManifest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('sha256', models.CharField(db_index=True, max_length=64)),
                ('size', models.PositiveBigIntegerField()),
                ('mime_type', models.CharField(max_length=120)),
                ('owner_id', models.CharField(max_length=64)),
                ('academic_object', models.CharField(max_length=160)),
                ('period', models.CharField(blank=True, max_length=40)),
                ('version', models.PositiveIntegerField(default=1)),
                ('classification', models.CharField(default='internal', max_length=32)),
                ('content_path', models.CharField(max_length=255, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('sha256', 'academic_object', 'version'), name='manifest_object_version_unique')],
            },
        ),
        migrations.CreateModel(
            name='AcademicRule',
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
                ('scope', models.JSONField(default=dict)),
                ('input_schema', models.JSONField(default=dict)),
                ('expression', models.JSONField(default=dict)),
                ('priority', models.PositiveSmallIntegerField(default=100)),
                ('severity', models.CharField(default='blocking', max_length=20)),
                ('cohort', models.CharField(blank=True, max_length=40)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('reviewed', 'Reviewed'), ('active', 'Active'), ('retired', 'Retired')], default='draft', max_length=20)),
                ('activated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rules_activated', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rules_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('code', 'version'), name='rule_version_unique')],
            },
        ),
    ]
