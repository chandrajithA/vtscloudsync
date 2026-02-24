from django.utils import timezone
from datetime import timedelta
from storageapp.models import CloudFile
from storageapp.s3_utils import delete_from_s3


def cleanup_trash():
    cutoff = timezone.now() - timedelta(days=30)

    files = CloudFile.objects.filter(
        is_deleted=True,
        deleted_at__lte=cutoff
    )

    for file in files:
        try:
            if file.public_id:
                delete_from_s3(file.public_id)
        except Exception:
            pass

        file.delete()