from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User

    list_display = ("username", "email", "is_staff", "is_superuser", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {
            "fields": ("first_name", "last_name", "email", "phone", "profile_picture")
        }),
        ("Permissions", {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")
        }),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "password1", "password2", "is_staff", "is_superuser"),
        }),
    )

    search_fields = ("username", "email")
    ordering = ("username",)

    def has_add_permission(self, request):
        return False

    # def has_delete_permission(self, request, obj=None):
    #     return False


@admin.register(UserLoginActivity)
class UserLoginActivityAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "login_at",
        "ip_address",
    )

    list_filter = (
        "login_at",
    )

    search_fields = (
        "user__username",
        "user__email",
    )

    ordering = ("-login_at",)

    readonly_fields = (
        "user",
        "login_at",
    )

    list_per_page = 50



@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "short_name", "formatted_storage", "formatted_file_size", "created_at")
    search_fields = ("name", "short_name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)

    def formatted_storage(self, obj):
        if not obj.storage_limit:
            return "Unlimited"
        
        size = obj.storage_limit
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"

    formatted_storage.short_description = "Storage Limit"
    formatted_storage.admin_order_field = "storage_limit"

    def formatted_file_size(self, obj):
        if obj.file_size_lmt is None:
            return "No File Limit"
        
        filesizelimit = obj.file_size_lmt
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if filesizelimit < 1024:
                return f"{filesizelimit:.2f} {unit}"
            filesizelimit /= 1024
        return f"{filesizelimit:.2f} PB"

    formatted_file_size.short_description = "File size Limit"
    formatted_file_size.admin_order_field = "file_size_limit"





@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "organization",
        "is_admin",
        "joined_at",
    )

    list_filter = ("is_admin", "organization")
    search_fields = (
        "user__username",
        "user__email",
        "organization__name",
    )

    ordering = ("-joined_at",)
    autocomplete_fields = ("user", "organization")
    readonly_fields = ("joined_at",)

    fieldsets = (
        ("Member Info", {
            "fields": ("organization", "user")
        }),
        ("Active Status", {
            "fields": ("is_active",)
        }),
        ("Permissions", {
            "fields": ("is_admin", "can_upload", "can_view", "can_download", "can_share", "can_delete")
        }),
        ("Metadata", {
            "fields": ("joined_at",)
        }),
    )
