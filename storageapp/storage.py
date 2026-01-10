from cloudinary_storage.storage import MediaCloudinaryStorage

class CloudinaryAutoStorage(MediaCloudinaryStorage):
    resource_type = "auto"
