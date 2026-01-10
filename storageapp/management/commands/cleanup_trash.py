from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import cloudinary.uploader
from storageapp.models import CloudFile

class Command(BaseCommand):
    help = "Delete trashed files older than 30 days"

    def handle(self, *args, **kwargs):
        expiry = timezone.now() - timedelta(days=30)

        files = CloudFile.objects.filter(
            is_deleted=True,
            deleted_at__lte=expiry
        )

        for file in files:
            cloudinary.uploader.destroy(
                file.public_id,
                resource_type="raw" if file.file_type in ["document", "other"] else file.file_type
            )
            file.delete()

        self.stdout.write("Old trash cleaned successfully")
