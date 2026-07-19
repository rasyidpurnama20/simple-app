from django.contrib import admin

from obe.shared.models import AcademicRule, AuditEvent, FeatureFlag, FileManifest, OutboxEvent


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


admin.site.register([AcademicRule, FeatureFlag, FileManifest, OutboxEvent])
