from django.contrib import messages
from django.shortcuts import redirect
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from .models import User
import re
from allauth.account.utils import perform_login

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
        """
        If the social account email matches an existing user, link it and log in.
        """

        email = sociallogin.account.extra_data.get('email')
        name = sociallogin.account.extra_data.get('name')


        if not email:
            messages.error(request, "We couldn't get your email from the social provider. Please sign up manually.")
            return redirect('accounts:signup_page')  # or wherever you want to send them
        

        if sociallogin.is_existing:
            return  # Already linked

        
        try:
            user = User.objects.get(email=email)
            
            
        except User.DoesNotExist:
            # Auto-create user without going to signup
            user = User.objects.create(
                username=generate_unique_username_from_email(email),
                email=email,
                first_name=name,
                is_active=True,
            )
            user.set_unusable_password()
            user.save()

        sociallogin.connect(request, user)

        # 🔑 THIS IS THE KEY LINE
        perform_login(
            request,
            user,
            email_verification="none"
        )