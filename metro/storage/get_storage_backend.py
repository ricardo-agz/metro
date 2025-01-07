from metro.storage.storage_backends import FileSystemStorage, S3Storage
from metro.config import config


def get_storage_backend():
    if config.FILE_STORAGE_BACKEND == "filesystem":
        return FileSystemStorage(
            location=config.FILE_SYSTEM_STORAGE_LOCATION,
            base_url=config.FILE_SYSTEM_BASE_URL,
        )
    elif config.FILE_STORAGE_BACKEND == "s3":
        if not all(
            [
                config.S3_BUCKET_NAME,
                config.AWS_ACCESS_KEY_ID,
                config.AWS_SECRET_ACCESS_KEY,
                config.AWS_REGION_NAME,
            ]
        ):
            raise ValueError(
                "Missing AWS S3 configuration settings. The following environment variables are required: "
                "S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME"
            )

        return S3Storage(
            bucket_name=config.S3_BUCKET_NAME,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            region_name=config.AWS_REGION_NAME,
        )
    else:
        raise ValueError(
            f"Invalid file storage backend specified: {config.FILE_STORAGE_BACKEND}"
        )


storage_backend = get_storage_backend()
