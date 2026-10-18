"""Where uploaded photos and files live: a private folder on disk, or an S3 bucket (MinIO included).

The deployment decides once, by its settings: with VINHOMES_API_S3_ENDPOINT set every object is in
the bucket, without it every object is under the file root. The database says the same thing in
`storage_locations.provider` (`s3` or `local_fs`), and the routes only read and write objects of
the provider in force; `python -m vinhomes_api.storage_setup` moves a deployment from disk to the
bucket.

The upload and download routes were written against pathlib. `at()` therefore returns a Path for
disk and, for a bucket, an object with the few Path methods those routes use, so one route serves
both. The bucket is private: content always leaves through a route that checked who is asking.
"""
import io
import os
from functools import lru_cache
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote, urlsplit

from fastapi.responses import FileResponse, Response


def provider() -> str:
    return 's3' if os.getenv('VINHOMES_API_S3_ENDPOINT', '').strip() else 'local_fs'


def bucket() -> str:
    return os.getenv('VINHOMES_API_S3_BUCKET', '').strip() or 'vinhomes-files'


@lru_cache(maxsize=4)
def _client(endpoint: str, access: str, secret: str, region: str):
    from minio import Minio  # only a deployment that stores in a bucket needs the library
    address = urlsplit(endpoint)
    if address.scheme not in ('http', 'https') or not address.netloc or not access or not secret:
        raise RuntimeError('VINHOMES_API_S3_ENDPOINT, VINHOMES_API_S3_ACCESS_KEY and VINHOMES_API_S3_SECRET_KEY are required')
    return Minio(address.netloc, access_key=access, secret_key=secret, secure=address.scheme == 'https', region=region or None)


def client():
    return _client(os.getenv('VINHOMES_API_S3_ENDPOINT', '').strip(), os.getenv('VINHOMES_API_S3_ACCESS_KEY', '').strip(),
                   os.getenv('VINHOMES_API_S3_SECRET_KEY', '').strip(), os.getenv('VINHOMES_API_S3_REGION', '').strip())


def direct_enabled() -> bool:
    return provider() == 's3' and bool(os.getenv('VINHOMES_API_S3_PUBLIC_ENDPOINT', '').strip())


def signed_upload(key: str, size: int, mime: str, expires: datetime):
    from minio.datatypes import PostPolicy
    address = urlsplit(os.environ['VINHOMES_API_S3_PUBLIC_ENDPOINT'].strip())
    if address.username or address.password or address.path not in ('', '/') or address.query or address.fragment:
        raise RuntimeError('S3 public endpoint must be an HTTP(S) origin')
    signer = _client(os.environ['VINHOMES_API_S3_PUBLIC_ENDPOINT'].strip(),
                     os.environ['VINHOMES_API_S3_ACCESS_KEY'].strip(), os.environ['VINHOMES_API_S3_SECRET_KEY'].strip(),
                     os.getenv('VINHOMES_API_S3_REGION', '').strip() or 'us-east-1')
    policy = PostPolicy(bucket(), expires)
    policy.add_equals_condition('key', key)
    policy.add_equals_condition('Content-Type', mime)
    policy.add_content_length_range_condition(size, size)
    fields = signer.presigned_post_policy(policy)
    fields.update({'key': key, 'Content-Type': mime})
    return os.environ['VINHOMES_API_S3_PUBLIC_ENDPOINT'].rstrip('/') + '/' + bucket(), fields


class BucketObject:
    """One object of the bucket, with the pathlib methods the file routes use. Calls block."""

    def __init__(self, key: str):
        if not key or key.startswith('/') or '..' in key.split('/') or '\\' in key:
            raise ValueError('Invalid object key')
        self.key = key

    @property
    def parent(self):
        return self  # a bucket has no folders to create

    def mkdir(self, **options) -> None:
        pass

    @property
    def suffix(self) -> str:
        return Path(self.key).suffix

    def with_suffix(self, suffix: str) -> 'BucketObject':
        return BucketObject(self.key[:len(self.key) - len(self.suffix)] + suffix)

    def stat(self):
        from minio.error import S3Error
        try:
            return SimpleNamespace(st_size=client().stat_object(bucket(), self.key).size)
        except S3Error as error:
            if error.code in ('NoSuchKey', 'NoSuchObject'):
                raise FileNotFoundError(self.key) from None
            raise

    def exists(self) -> bool:
        try:
            self.stat()
            return True
        except FileNotFoundError:
            return False

    is_file = exists

    def read_bytes(self) -> bytes:
        reply = client().get_object(bucket(), self.key)
        try:
            return reply.read()
        finally:
            reply.close()
            reply.release_conn()

    def write_bytes(self, data: bytes) -> None:
        client().put_object(bucket(), self.key, io.BytesIO(bytes(data)), len(data))

    def open(self, mode: str):
        if mode != 'xb':
            raise ValueError('A bucket object is only opened to be created')
        if self.exists():
            raise FileExistsError(self.key)
        target = self

        class Created:
            def __enter__(self): return self
            def __exit__(self, *error): return False
            def write(self, data): target.write_bytes(data)
        return Created()

    def replace(self, target: 'BucketObject') -> None:
        target.write_bytes(self.read_bytes())
        self.unlink(missing_ok=True)

    def unlink(self, missing_ok: bool = False) -> None:
        if not missing_ok and not self.exists():
            raise FileNotFoundError(self.key)
        client().remove_object(bucket(), self.key)


def at(root: Path, key: str):
    """The object a key names, in the storage in force. Raises ValueError for a key that would leave it."""
    if provider() == 's3':
        return BucketObject(key)
    path = (root / key).resolve()
    if Path(key).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError('Invalid object key')
    return path


def respond(stored, *, media_type: str, filename: str | None = None, content_disposition_type: str = 'attachment',
            headers: dict[str, str] | None = None) -> Response:
    """The object's content as a response, after the route decided the caller may have it."""
    if isinstance(stored, Path):
        return FileResponse(stored, media_type=media_type, filename=filename, content_disposition_type=content_disposition_type, headers=headers)
    headers = dict(headers or {})
    if filename:
        quoted = quote(filename)
        headers['content-disposition'] = (f'{content_disposition_type}; filename="{filename}"' if quoted == filename
                                          else f"{content_disposition_type}; filename*=utf-8''{quoted}")
    return Response(stored.read_bytes(), media_type=media_type, headers=headers)
