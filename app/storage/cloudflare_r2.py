from __future__ import annotations

from .aws_s3 import AWSS3StorageService


class CloudflareR2StorageService(AWSS3StorageService):
    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        public_url_base: str | None = None,
    ):
        super().__init__(
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            bucket_name=bucket_name,
            public_url_base=public_url_base,
            region_name="auto",
        )
        self.account_id = account_id

    @property
    def endpoint_url(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"
