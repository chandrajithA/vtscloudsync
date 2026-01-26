from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


def profile_image_upload_path(instance, filename):
    from django.utils.text import slugify
    name = slugify(instance.first_name)
    id = instance.pk
    return f'User_images/{name}_ID_{id}/{filename}'

class User(AbstractUser):
    profile_picture = models.ImageField(null=True, blank=True, upload_to = profile_image_upload_path)
    phone = models.CharField(max_length=10, unique=True, null=True, blank=True) 


class UserLoginActivity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    login_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['login_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.login_at}"