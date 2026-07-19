from django.contrib import admin

from obe.shared.models import (
    AcademicAppeal,
    AcademicDecision,
    AcademicRule,
    AuditEvent,
    AuditReference,
    AuditSensitivePayload,
    CohortRulePackage,
    ConsumerCursor,
    DecisionOverride,
    FeatureFlag,
    FileManifest,
    InboxEvent,
    JobExecution,
    OutboxEvent,
)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "actor_label", "action", "object_type", "object_id", "outcome")
    list_filter = ("action", "object_type", "outcome")
    search_fields = ("actor_label", "object_id", "summary", "correlation_id")
    readonly_fields = [field.name for field in AuditEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyOperationalAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(
    [
        OutboxEvent,
        InboxEvent,
        ConsumerCursor,
        JobExecution,
        AuditReference,
        AuditSensitivePayload,
    ],
    ReadOnlyOperationalAdmin,
)
admin.site.register(
    [AcademicRule, CohortRulePackage, DecisionOverride, AcademicAppeal, FileManifest]
)
admin.site.register(AcademicDecision, ReadOnlyOperationalAdmin)
admin.site.register(FeatureFlag, ReadOnlyOperationalAdmin)
