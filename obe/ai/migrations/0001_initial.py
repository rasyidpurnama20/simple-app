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
            name='PromptTemplate',
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
                ('task_class', models.CharField(default='A1', max_length=4)),
                ('input_schema', models.JSONField(default=dict)),
                ('output_schema', models.JSONField(default=dict)),
                ('data_class', models.CharField(default='internal', max_length=32)),
                ('model_alias', models.CharField(default='local-small', max_length=40)),
                ('template', models.TextField()),
                ('policy', models.JSONField(default=dict)),
                ('status', models.CharField(default='draft', max_length=20)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='AIRun',
            fields=[
                ('request_id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('source_versions', models.JSONField(default=dict)),
                ('policy_decision', models.JSONField(default=dict)),
                ('model_alias', models.CharField(max_length=40)),
                ('status', models.CharField(default='queued', max_length=24)),
                ('queue_wait_ms', models.PositiveIntegerField(default=0)),
                ('latency_ms', models.PositiveIntegerField(default=0)),
                ('input_tokens', models.PositiveIntegerField(default=0)),
                ('output_tokens', models.PositiveIntegerField(default=0)),
                ('result', models.JSONField(default=dict)),
                ('human_decision', models.CharField(blank=True, max_length=20)),
                ('human_diff', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('prompt', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ai.prompttemplate')),
            ],
        ),
        migrations.AddConstraint(
            model_name='prompttemplate',
            constraint=models.UniqueConstraint(fields=('code', 'version'), name='prompt_code_version_unique'),
        ),
    ]
