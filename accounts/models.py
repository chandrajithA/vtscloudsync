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


class UserLoginActivity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    login_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['login_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.login_at}"