from subscriptions.models import UserSubscription
from django.db.models import Sum
from storageapp.models import CloudFile

def storage_info(request):
    if not request.user.is_authenticated:
        return {}

    sub = UserSubscription.objects.select_related("plan").filter(user=request.user).first()

    used = (
        CloudFile.objects
        .filter(user=request.user, is_deleted=False)
        .aggregate(total=Sum("file_size"))["total"] or 0
    )

    limit = sub.plan.storage_limit if sub and sub.plan else 0

    storage_percent = int((used / limit) * 100) if limit else 0


    return {
        "storage_used": used,
        "storage_limit": limit,
        "current_plan": sub.plan,
        "storage_percent":storage_percent,
        "storage_near_limit": storage_percent >= 99,
    }