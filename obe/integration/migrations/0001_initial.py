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
            name='IntegrationBatch',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('contract_code', models.CharField(max_length=80)),
                ('schema_version', models.CharField(max_length=40)),
                ('direction', models.CharField(choices=[('in', 'Incoming'), ('out', 'Outgoing')], max_length=8)),
                ('source', models.CharField(max_length=80)),
                ('idempotency_key', models.CharField(max_length=160, unique=True)),
                ('checksum', models.CharField(max_length=64)),
                ('record_count', models.PositiveIntegerField(default=0)),
                ('state', models.CharField(default='staging', max_length=24)),
                ('staging_payload', models.JSONField(default=list)),
                ('validation_report', models.JSONField(default=dict)),
                ('reconciliation', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('committed_at', models.DateTimeField(blank=True, null=True)),
                ('approved_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
