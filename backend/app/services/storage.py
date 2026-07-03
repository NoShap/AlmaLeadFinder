"""Resume file storage behind a small interface.

Two implementations: S3-compatible object storage (MinIO locally — swapping to real
AWS S3 is just endpoint/credential config) and local disk as a zero-dependency
fallback for tests and non-docker development. Selection is config-driven, mirroring
the email service: S3 when S3_ENDPOINT_URL is set, local disk otherwise.
"""

import abc
import uuid
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.core.config import Settings, settings


class FileStorage(abc.ABC):
    @abc.abstractmethod
    def save(self, original_filename: str, content: bytes, content_type: str) -> str:
        """Persist the file and return an opaque storage key."""

    @abc.abstractmethod
    def load(self, key: str) -> bytes:
        """Return the file's bytes. Raises FileNotFoundError if the key is unknown."""

    @abc.abstractmethod
    def delete(self, key: str) -> None:
        """Remove the file. Deleting an unknown key is a no-op."""


def _make_key(original_filename: str) -> str:
    suffix = Path(original_filename).suffix.lower()
    return f"{uuid.uuid4().hex}{suffix}"


class LocalDiskStorage(FileStorage):
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, original_filename: str, content: bytes, content_type: str) -> str:
        key = _make_key(original_filename)
        (self._root / key).write_bytes(content)
        return key

    def load(self, key: str) -> bytes:
        path = (self._root / key).resolve()
        if self._root.resolve() not in path.parents:
            raise FileNotFoundError(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = (self._root / key).resolve()
        if self._root.resolve() not in path.parents:
            return
        path.unlink(missing_ok=True)


class S3FileStorage(FileStorage):
    def __init__(
        self, endpoint_url: str, bucket: str, access_key: str, secret_key: str, region: str
    ) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        self._bucket = bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    def save(self, original_filename: str, content: bytes, content_type: str) -> str:
        key = _make_key(original_filename)
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=content, ContentType=content_type
        )
        return key

    def load(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                raise FileNotFoundError(key) from exc
            raise
        return response["Body"].read()

    def delete(self, key: str) -> None:
        # S3 DeleteObject is idempotent — no error for a missing key.
        self._client.delete_object(Bucket=self._bucket, Key=key)


@lru_cache(maxsize=4)
def _cached_s3_storage(
    endpoint_url: str, bucket: str, access_key: str, secret_key: str, region: str
) -> S3FileStorage:
    # Cached so the client is built and the bucket ensured once per process,
    # not once per request.
    return S3FileStorage(endpoint_url, bucket, access_key, secret_key, region)


def get_storage(config: Settings | None = None) -> FileStorage:
    config = config or settings
    if config.s3_endpoint_url:
        return _cached_s3_storage(
            config.s3_endpoint_url,
            config.s3_bucket,
            config.s3_access_key,
            config.s3_secret_key,
            config.s3_region,
        )
    return LocalDiskStorage(root=Path(config.upload_dir))
