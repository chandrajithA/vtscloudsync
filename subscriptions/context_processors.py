from storageapp.models import CloudFile
from django.db.models import Sum
from subscriptions.models import UserSubscription, Plan

def subscription_context(request):
    if not request.user.is_authenticated:
        return {}

    subscription = UserSubscription.objects.select_related("plan").filter(user=request.user).first()

    used = CloudFile.objects.filter(
        user=request.user,
        is_deleted=False
    ).aggregate(s=Sum("file_size"))["s"] or 0

    if subscription and subscription.plan:
        limit = subscription.plan.storage_limit
        current_plan = subscription.plan

        plans = Plan.objects.filter(
                order__gt=current_plan.order
            ).order_by("order")

        can_upgrade = plans.exists()
    else:
        limit = 0
        current_plan = None
        can_upgrade = False

    percent = min(int((used / limit) * 100), 100) if limit else 0

    return {
        "current_plan": current_plan,
        "can_upgrade": can_upgrade,
        "storage_used": used,
        "storage_limit": limit,
        "storage_percent": percent,
    }