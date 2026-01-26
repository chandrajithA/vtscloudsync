from django.contrib import admin
from .models import *
from django.utils.html import format_html

@admin.register(CloudFile)
class CloudFileAdmin(admin.ModelAdmin):

    list_display = (
        "file_name",
        "file_type",
        "user",
        "formatted_size",
        "is_deleted",
        "uploaded_at",
    )

    list_filter = (
        "file_type",
        "is_deleted",
        "uploaded_at",
    )

    search_fields = (
        "file_name",
        "user__username",
        "user__email",
    )

    ordering = ("-uploaded_at",)

    readonly_fields = (
        "uploaded_at",
        "deleted_at",
        "public_id",
    )

    actions = ["soft_delete_files", "restore_files"]

    # 📦 Pretty file size
    def formatted_size(self, obj):
        size = obj.file_size
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"

    formatted_size.short_description = "File Size"

    # 🗑️ Soft delete
    def soft_delete_files(self, request, queryset):
        queryset.update(is_deleted=True)
    soft_delete_files.short_description = "Move selected files to Trash"

    # ♻️ Restore
    def restore_files(self, request, queryset):
        queryset.update(is_deleted=False, deleted_at=None)
    restore_files.short_description = "Restore selected files"


@admin.register(SharedFile)
class SharedFileAdmin(admin.ModelAdmin):

    list_display = (
        "file",
        "owner",
        "shared_with",
        "shared_at",
    )

    list_filter = (
        "shared_at",
    )

    search_fields = (
        "file__file_name",
        "owner__username",
        "shared_with__username",
    )

    readonly_fields = (
        "file",
        "owner",
        "shared_with",
        "shared_at",
    )

    ordering = ("-shared_at",)
