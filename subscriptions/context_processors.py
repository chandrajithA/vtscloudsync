from storageapp.models import CloudFile
from django.db.models import Sum
from subscriptions.models import UserSubscription

def subscription_context(request):
    if not request.user.is_authenticated:
        return {}

    subscription = UserSubscription.objects.select_related("plan").get(user=request.user)

    used = CloudFile.objects.filter(
        user=request.user,
        is_deleted=False
    ).aggregate(s=Sum("file_size"))["s"] or 0

    limit = subscription.plan.storage_limit

    percent = min(int((used / limit) * 100), 100) if limit else 0

    return {
        "current_plan": subscription.plan,
        "storage_used": used,
        "storage_limit": limit,
        "storage_percent": percent,
    }