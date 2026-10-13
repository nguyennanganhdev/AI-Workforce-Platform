# Private image storage with MinIO or AWS S3

Image bytes belong in object storage. PostgreSQL stores ownership, object URI,
MIME type, byte length, checksum, status, timestamps, and application metadata.
The same `S3BlobStore` code works with local MinIO and AWS S3.

## Construction

```python
import os

from sqlalchemy.ext.asyncio import create_async_engine

from agentscope.app.media import ImageAssetService
from agentscope.app.rag.blob_store import S3BlobStore

engine = create_async_engine(os.environ["AGENTSCOPE_SQL_URL"])
blob_store = S3BlobStore(
    bucket=os.environ["S3_BUCKET"],
    endpoint_url=os.getenv("S3_ENDPOINT") or None,
    region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID") or None,
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY") or None,
    session_token=os.getenv("AWS_SESSION_TOKEN") or None,
    use_ssl=not os.getenv("S3_ENDPOINT", "").startswith("http://"),
)

await blob_store.__aenter__()
images = ImageAssetService(engine=engine, blob_store=blob_store)
```

In an application, enter and close `blob_store` through the application
lifespan instead of calling `__aenter__` directly.

## Upload and download

```python
asset = await images.upload(
    tenant_id=tenant_id,
    user_id=user_id,
    filename=upload.filename or "image",
    stream=upload.file,
    metadata={"purpose": "avatar"},
)

url = await images.create_download_url(
    tenant_id=tenant_id,
    user_id=user_id,
    asset_id=asset.id,
    expires_in=900,
)
```

Supported formats are JPEG, PNG, GIF, and WebP. Detection uses file signatures,
not the untrusted HTTP `Content-Type` header. The default limit is 20 MiB.

Objects remain private. Clients receive short-lived presigned URLs only after
the service verifies `tenant_id` and `user_id` against PostgreSQL.

## Moving from MinIO to AWS S3

For local MinIO:

```dotenv
S3_ENABLED=true
S3_ENDPOINT=http://minio:9000
S3_BUCKET=agentscope
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=change-me
AWS_DEFAULT_REGION=us-east-1
```

For AWS S3, leave the endpoint and static credentials empty when the workload
has an IAM role:

```dotenv
S3_ENABLED=true
S3_ENDPOINT=
S3_BUCKET=my-production-bucket
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=
AWS_DEFAULT_REGION=ap-southeast-1
```

No business-code change is required. Existing `s3://bucket/key` values retain
the bucket name, which also permits a controlled bucket migration.

