import uuid

from django.conf import settings
from django.db import models

from obe.shared.models import VersionedModel


class PromptTemplate(VersionedModel):
    code = models.CharField(max_length=80)
    task_class = models.CharField(max_length=4, default="A1")
    input_schema = models.JSONField(default=dict)
    output_schema = models.JSONField(default=dict)
    data_class = models.CharField(max_length=32, default="internal")
    model_alias = models.CharField(max_length=40, default="local-small")
    template = models.TextField()
    policy = models.JSONField(default=dict)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default="draft")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["code", "version"], name="prompt_code_version_unique")
        ]


class AIRun(models.Model):
    request_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prompt = models.ForeignKey(PromptTemplate, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    source_versions = models.JSONField(default=dict)
    policy_decision = models.JSONField(default=dict)
    model_alias = models.CharField(max_length=40)
    status = models.CharField(max_length=24, default="queued")
    queue_wait_ms = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    result = models.JSONField(default=dict)
    human_decision = models.CharField(max_length=20, blank=True)
    human_diff = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
