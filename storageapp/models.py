from django.db import models
from django.conf import settings
from datetime import timedelta
from django.utils import timezone

class CloudFile(models.Model):
    FILE_TYPES = (
        ("image", "Image"),
        ("video", "Video"),
        ("document", "Document"),
        ("other", "Other"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField()
    file_type = models.CharField(max_length=20, choices=FILE_TYPES)
    file_url = models.URLField(null=True, blank=True)
    uploaded_file = models.FileField(upload_to='cloud/',null=True)
    public_id = models.CharField(max_length=255,null=True) 
    uploaded_at = models.DateTimeField(auto_now_add=True)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def expires_at(self):
        if self.deleted_at:
            return self.deleted_at + timedelta(days=30)
        return None

    def days_left(self):
        if self.deleted_at:
            return (self.expires_at() - timezone.now()).days
        return None

   
