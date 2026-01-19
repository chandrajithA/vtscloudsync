from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.urls import reverse
from django.contrib import messages
from .models import User
import re

def generate_unique_username_from_email(email):
    base = email.split('@')[0].lower()
    base = re.sub(r'[^a-z0-9_]', '', base)

    username = base
    counter = 1

    while User.objects.filter(username=username).exists():
        username = f"{base}_{counter}"
        counter += 1

    return username


class MySocialAccountAdapter(DefaultSocialAccountAdapter):

    def pre_social_login(self, request, sociallogin):
        email = sociallogin.account.extra_data.get("email")
        name = sociallogin.account.extra_data.get("name", "")

        if not email:
            messages.error(
                request,
                "We couldn't get your email from Google. Please sign up manually."
            )
            return

        # If already linked → do nothing
        if sociallogin.is_existing:
            return

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            user = User.objects.create(
                username=generate_unique_username_from_email(email),
                email=email,
                first_name=name,
                is_active=True,
            )
            user.set_unusable_password()
            user.save()

        # 🔗 LINK social account to user
        sociallogin.connect(request, user)
        pass
