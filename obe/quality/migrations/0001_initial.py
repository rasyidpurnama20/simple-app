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
            name='QualityCycle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('period', models.CharField(max_length=40)),
                ('scope_type', models.CharField(max_length=40)),
                ('scope_id', models.CharField(max_length=80)),
                ('standard', models.JSONField(default=dict)),
                ('execution', models.JSONField(default=dict)),
                ('evaluation', models.JSONField(default=dict)),
                ('control', models.JSONField(default=dict)),
                ('improvement', models.JSONField(default=dict)),
                ('status', models.CharField(default='draft', max_length=24)),
                ('approvals', models.JSONField(default=list)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='IntegrityIssue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('severity', models.CharField(choices=[('blocking', 'Blocking'), ('warning', 'Warning'), ('information', 'Information')], max_length=20)),
                ('reason_code', models.CharField(db_index=True, max_length=80)),
                ('object_type', models.CharField(max_length=80)),
                ('object_id', models.CharField(max_length=80)),
                ('impact', models.TextField()),
                ('due_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(default='open', max_length=24)),
                ('evidence', models.JSONField(default=list)),
                ('accepted_risk_reason', models.TextField(blank=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ImprovementAction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('root_cause', models.TextField()),
                ('action', models.TextField()),
                ('due_at', models.DateTimeField()),
                ('success_indicator', models.TextField()),
                ('status', models.CharField(default='planned', max_length=24)),
                ('baseline', models.JSONField(default=dict)),
                ('result', models.JSONField(default=dict)),
                ('approval', models.JSONField(default=dict)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('issue', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='actions', to='quality.integrityissue')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
