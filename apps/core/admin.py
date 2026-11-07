from django.contrib import admin

from .models import AuditLog

admin.site.site_header = "إدارة مولّد أوراق الرياضيات"
admin.site.site_title = "إدارة المنصة"
admin.site.index_title = "البيانات والمنهج"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "target", "actor")
    list_filter = ("action",)
    search_fields = ("target", "request_id")
    readonly_fields = ("created_at", "updated_at", "action", "target", "actor", "payload", "request_id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
