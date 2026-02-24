from django.contrib import admin
from .models import *

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "formatted_storage", "price","formatted_file_size","order")
    search_fields = ("name",)
    ordering = ("price",)

    def formatted_storage(self, obj):
        if obj.storage_limit is None:
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
            return "No limit"
        
        filesizelimit = obj.file_size_lmt
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if filesizelimit < 1024:
                return f"{filesizelimit:.2f} {unit}"
            filesizelimit /= 1024
        return f"{filesizelimit:.2f} PB"

    formatted_file_size.short_description = "File size Limit"
    formatted_file_size.admin_order_field = "file_size_limit"

    


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


