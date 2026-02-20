import os
from django.contrib.auth import get_user_model
from subscriptions.models import Plan, UserSubscription

def run():
    User = get_user_model()

    username = os.getenv("DJANGO_SUPERUSER_USERNAME")
    email = os.getenv("DJANGO_SUPERUSER_EMAIL")
    password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

    if not (username and email and password):
        print("Env vars missing")
        return

    # Create plans
    Plan.objects.get_or_create(
        name="Pro",
        defaults={"price": 2499, "storage_limit": 53687091200},
    )

    Plan.objects.get_or_create(
        name="Ultra",
        defaults={"price": 4999, "storage_limit": 107374182400},
    )

    free_plan, _ = Plan.objects.get_or_create(
        name="Free",
        defaults={"price": 0, "storage_limit": 5368709120},
    )

    # Create superuser
    user = User.objects.filter(username=username).first()
    if not user:
        user = User.objects.create_superuser(username, email, password)

    # Attach subscription
    UserSubscription.objects.get_or_create(
        user=user,
        defaults={"plan": free_plan},
    )

    print("Superuser ready")
