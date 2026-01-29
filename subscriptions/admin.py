from django.contrib import admin
from .models import *

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "formatted_storage", "price","file_size_lmt")
    search_fields = ("name",)
    ordering = ("price",)

    def formatted_storage(self, obj):
        size = obj.storage_limit
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"

    formatted_storage.short_description = "Storage Limit"


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "started_at")
    list_filter = ("plan", "started_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("started_at",)

    autocomplete_fields = ("user", "plan")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "amount",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "plan",
        "created_at",
    )

    search_fields = (
        "user__username",
        "user__email",
        "razorpay_order_id",
        "razorpay_payment_id",
    )

    readonly_fields = (
        "user",
        "plan",
        "amount",
        "razorpay_order_id",
        "razorpay_payment_id",
        "razorpay_signature",
        "created_at",
    )

    ordering = ("-created_at",)


