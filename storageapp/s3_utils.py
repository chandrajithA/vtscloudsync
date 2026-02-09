import boto3
from django.conf import settings
import uuid

s3 = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_S3_REGION_NAME,
)

def upload_to_s3(file, folder):
    ext = file.name.split(".")[-1]
    key = f"{folder}/{uuid.uuid4()}.{ext}"

    s3.upload_fileobj(
        file,
        settings.AWS_STORAGE_BUCKET_NAME,
        key,
        ExtraArgs={
            "ContentType": file.content_type,
        }
    )

    file_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{key}"
    return file_url, key


def generate_presigned_url(key, download=False, filename=None):
    params = {
        "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
        "Key": key,
    }

    if download and filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

    url = s3.generate_presigned_url(
        "get_object",
        Params=params,
    )
    return url


def delete_from_s3(key):
    s3.delete_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=key
    )