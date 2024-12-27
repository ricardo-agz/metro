from pyrails.storage.storage_backends.base_backend import StorageBackend

try:
    import boto3

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class S3Storage(StorageBackend):
    def __init__(
        self,
        bucket_name,
        aws_access_key_id=None,
        aws_secret_access_key=None,
        region_name=None,
    ):
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 is required to use S3Storage backend")

        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )

    def save(self, name, content):
        self.s3_client.upload_fileobj(content, self.bucket_name, name)
        return name

    def url(self, name):
        return self.s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": name},
            ExpiresIn=3600,  # URL expires in 1 hour
        )

    def delete(self, name):
        self.s3_client.delete_object(Bucket=self.bucket_name, Key=name)
