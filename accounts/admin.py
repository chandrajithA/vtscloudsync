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

    def has_delete_permission(self, request, obj=None):
        return False


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

    date_hierarchy = "login_at"

    readonly_fields = (
        "user",
        "login_at",
    )

    list_per_page = 50
