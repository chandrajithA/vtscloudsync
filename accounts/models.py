from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
import uuid
from django.utils.text import slugify


def profile_image_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}.{ext}"

    name = slugify(instance.first_name or "user")
    user_id = instance.pk or "temp"

    return f'User_images/{name}_ID_{user_id}/{new_filename}'

class User(AbstractUser):
    profile_picture = models.ImageField(null=True, blank=True, upload_to = profile_image_upload_path)
    phone = models.CharField(max_length=10, unique=True, null=True, blank=True) 


class Organization(models.Model):
    name = models.CharField(max_length=255, unique=True)
    short_name = models.CharField(max_length=10, unique=True)
    storage_limit = models.BigIntegerField(null=True, blank=True,help_text="Value in bytes. Leave empty if no limit")
    file_size_lmt = models.BigIntegerField(null=True, blank=True,help_text="Value in bytes. Leave empty if no limit")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    

class OrganizationMember(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        related_name="org_membership"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="members"
    )
    is_admin = models.BooleanField(default=False)
    can_upload = models.BooleanField(default=False)
    can_view = models.BooleanField(default=False)
    can_download = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_share = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "organization")

    def __str__(self):
        return f"{self.user.username} - {self.organization.name} ({self.is_admin})"


class UserLoginActivity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    login_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['login_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.login_at}"