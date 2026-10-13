"""Where uploaded images are kept (spec A3, section 9): a directory, or any S3 store (MinIO in the compose stack).

Two backends behind one small interface (`ensure`, `put`, `get`, `head`, `delete`, `link`):

  local   files under a directory. For development and tests: its links are `file:` URIs nothing serves.
  s3      five S3 calls and a presigned GET, signed with AWS Signature Version 4 over httpx (no SDK). `link` is the only
          way anything outside the platform reads an object: a URL that works for `ttl` seconds and for that one object.

The endpoint is the OPERATOR's setting (AWP_S3_ENDPOINT). Nothing a partner, a resident or a model sends is ever made
into a URL that the platform calls: an upload arrives as bytes, a message names an asset by its id, and an object's key
is made here from random bytes (`new_key`), never from anything a caller chose.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlsplit

import httpx

ALGORITHM = "AWS4-HMAC-SHA256"
UNSIGNED = "UNSIGNED-PAYLOAD"
MAX_TTL = 7 * 24 * 3600  # the longest a SigV4 presigned URL may live
TIMEOUT = 15.0
EXTENSION = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}  # the types an asset may be
# A link made by `link`: recognised by the signature in its query, whichever backend made it.
KEY = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*(/[A-Za-z0-9_-][A-Za-z0-9_.-]*)*")  # plain names: no "..", no drive, no root
SIGNED = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s\"'<>\\]*[?&]X-(?:Amz|Awp)-Signature=[0-9A-Za-z]+[^\s\"'<>\\]*")


class StoreError(Exception):
    """The store did not do what was asked (unreachable, refused, misconfigured). The message names no secret."""


def sniff(data: bytes) -> str | None:
    """The image type the first bytes say it is; None for anything else. The type a caller declares is never used."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def new_key(client_id: str, content_type: str) -> str:
    """The object's name: the client's platform id as a folder, then 160 random bits. Nothing of the upload is in it."""
    return f"{client_id}/{secrets.token_hex(20)}.{EXTENSION[content_type]}"


def unsigned(url: str) -> str:
    """A link without its query string: it says which object, and opens nothing."""
    return url.split("?", 1)[0]


def redact(text: str) -> str:
    """`text` with every signed link cut down to `unsigned`: what may be stored or shown where the link must not be."""
    return SIGNED.sub(lambda m: unsigned(m.group(0)), text)


def masked(value: Any) -> Any:
    """Arguments of a tool as a resident may be shown them: where a signed link stood it only says that an image goes
    along. Not even the unsigned address: where the bytes are is nobody's business outside the platform."""
    if isinstance(value, str):
        return SIGNED.sub("[image link]", value)
    if isinstance(value, dict):
        return {k: masked(v) for k, v in value.items()}
    if isinstance(value, list):
        return [masked(v) for v in value]
    return value


def stable(value: Any) -> Any:
    """Arguments of a tool with their signed links made `unsigned`: two links to one object differ only by when they
    were signed, and a request sent twice must still be recognised as the same request (ledger.py)."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


# ---- AWS Signature Version 4 (S3 flavour: single-chunk payload, or UNSIGNED-PAYLOAD in a presigned URL) --------------------
def _enc(text: str, safe: str = "") -> str:
    return quote(text, safe=safe + "-_.~")


def _hmac(key: bytes, text: str) -> bytes:
    return hmac.new(key, text.encode(), hashlib.sha256).digest()


def canonical_request(method: str, path: str, query: dict[str, str], headers: dict[str, str], payload_hash: str) -> str:
    """`path` is the plain (not yet encoded) path; `headers` has lower-case names and all of them are signed."""
    pairs = sorted((_enc(k), _enc(v)) for k, v in query.items())
    names = sorted(headers)
    return "\n".join([method, _enc(path, "/"), "&".join(f"{k}={v}" for k, v in pairs),
                      "".join(f"{n}:{' '.join(headers[n].split())}\n" for n in names), ";".join(names), payload_hash])


def signature(secret_key: str, region: str, amz_date: str, canonical: str, service: str = "s3") -> str:
    day = amz_date[:8]
    to_sign = "\n".join([ALGORITHM, amz_date, f"{day}/{region}/{service}/aws4_request",
                         hashlib.sha256(canonical.encode()).hexdigest()])
    key = _hmac(_hmac(_hmac(_hmac(("AWS4" + secret_key).encode(), day), region), service), "aws4_request")
    return hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()


def authorization(method: str, path: str, query: dict[str, str], headers: dict[str, str], payload_hash: str, *,
                  access_key: str, secret_key: str, region: str, amz_date: str) -> str:
    """The Authorization header of a request whose signed headers are exactly `headers` (host and x-amz-* among them)."""
    sig = signature(secret_key, region, amz_date, canonical_request(method, path, query, headers, payload_hash))
    return (f"{ALGORITHM} Credential={access_key}/{amz_date[:8]}/{region}/s3/aws4_request,"
            f"SignedHeaders={';'.join(sorted(headers))},Signature={sig}")


def presigned_query(method: str, host: str, path: str, *, access_key: str, secret_key: str, region: str, amz_date: str,
                    expires: int) -> str:
    """The query string of a presigned URL (only the host header is signed, the payload is not)."""
    query = {"X-Amz-Algorithm": ALGORITHM, "X-Amz-Credential": f"{access_key}/{amz_date[:8]}/{region}/s3/aws4_request",
             "X-Amz-Date": amz_date, "X-Amz-Expires": str(expires), "X-Amz-SignedHeaders": "host"}
    sig = signature(secret_key, region, amz_date, canonical_request(method, path, query, {"host": host}, UNSIGNED))
    return "&".join(f"{_enc(k)}={_enc(v)}" for k, v in sorted(query.items())) + f"&X-Amz-Signature={sig}"


def amz_time(at: float) -> str:
    return datetime.fromtimestamp(at, timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class S3Store:
    """One bucket of an S3 service. `public_endpoint`: the address the links are made for, when the readers of a link
    reach the store by another name than the platform does (a signature covers the host, so a link cannot be rewritten
    afterwards)."""

    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str, region: str = "us-east-1", *,
                 path_style: bool = True, public_endpoint: str = "", client: httpx.AsyncClient | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        for name, value in (("AWP_S3_ENDPOINT", endpoint), ("AWP_S3_BUCKET", bucket), ("AWP_S3_ACCESS_KEY", access_key),
                            ("AWP_S3_SECRET_KEY", secret_key), ("AWP_S3_REGION", region)):
            if not value:
                raise ValueError(f"{name} is required for AWP_ASSET_BACKEND=s3")
        self.bucket, self.access_key, self.secret_key, self.region = bucket, access_key, secret_key, region
        self.path_style, self.clock = path_style, clock
        self.endpoint, self.public = self._parse(endpoint, "AWP_S3_ENDPOINT"), self._parse(
            public_endpoint or endpoint, "AWP_S3_PUBLIC_ENDPOINT")
        self._client, self._own = client, client is None

    @staticmethod
    def _parse(endpoint: str, name: str) -> tuple[str, str]:
        parts = urlsplit(endpoint)
        if parts.scheme not in ("http", "https") or not parts.netloc or parts.username or parts.path.strip("/") or parts.query:
            raise ValueError(f"{name} must be http(s)://host[:port] with nothing after it")
        return parts.scheme, parts.netloc.lower()

    def _where(self, key: str | None, endpoint: tuple[str, str]) -> tuple[str, str, str]:
        """(scheme, host, plain path) of an object, or of the bucket itself (key None)."""
        scheme, host = endpoint
        tail = "/" + key if key else ""
        return (scheme, host, f"/{self.bucket}{tail}") if self.path_style else (scheme, f"{self.bucket}.{host}", tail or "/")

    async def _call(self, method: str, key: str | None, *, data: bytes | None = None, content_type: str | None = None) -> httpx.Response:
        scheme, host, path = self._where(key, self.endpoint)
        digest = hashlib.sha256(data or b"").hexdigest()
        signed = {"host": host, "x-amz-content-sha256": digest, "x-amz-date": amz_time(self.clock())}
        if content_type:
            signed["content-type"] = content_type
        auth = authorization(method, path, {}, signed, digest, access_key=self.access_key, secret_key=self.secret_key,
                             region=self.region, amz_date=signed["x-amz-date"])
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False)
        try:
            return await self._client.request(method, f"{scheme}://{host}{_enc(path, '/')}", content=data,
                                              headers={**signed, "authorization": auth})
        except httpx.HTTPError as e:
            raise StoreError(f"the asset store did not answer ({type(e).__name__})") from e

    @staticmethod
    def _refused(what: str, r: httpx.Response) -> StoreError:
        code = re.search(r"<Code>([A-Za-z0-9]{1,60})</Code>", r.text[:2000] if r.content else "")
        return StoreError(f"the asset store refused to {what}: HTTP {r.status_code}" + (f" {code.group(1)}" if code else ""))

    async def ensure(self) -> None:
        """The bucket exists (made when missing). Safe to call from several processes at once."""
        r = await self._call("HEAD", None)
        if r.status_code == 200:
            return
        if r.status_code != 404:
            raise self._refused("show the bucket", r)
        body = None if self.region == "us-east-1" else (
            f'<CreateBucketConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><LocationConstraint>{self.region}'
            "</LocationConstraint></CreateBucketConfiguration>").encode()
        r = await self._call("PUT", None, data=body)
        if r.status_code != 200 and "BucketAlreadyOwnedByYou" not in r.text:
            raise self._refused("make the bucket", r)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        r = await self._call("PUT", key, data=data, content_type=content_type)
        if r.status_code != 200:
            raise self._refused("store an object", r)

    async def get(self, key: str) -> bytes | None:
        r = await self._call("GET", key)
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise self._refused("return an object", r)
        return r.content

    async def head(self, key: str) -> int | None:
        """The size of the object in bytes; None when there is none."""
        r = await self._call("HEAD", key)
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise self._refused("describe an object", r)
        return int(r.headers.get("content-length", 0))

    async def delete(self, key: str) -> None:
        """Gone afterwards, whether or not it was there."""
        r = await self._call("DELETE", key)
        if r.status_code not in (200, 204, 404):
            raise self._refused("delete an object", r)

    def link(self, key: str, ttl: int, at: float | None = None) -> str:
        """A URL that reads this one object for `ttl` seconds from `at` (now), for whoever holds it."""
        scheme, host, path = self._where(key, self.public)
        q = presigned_query("GET", host, path, access_key=self.access_key, secret_key=self.secret_key, region=self.region,
                            amz_date=amz_time(self.clock() if at is None else at), expires=max(1, min(int(ttl), MAX_TTL)))
        return f"{scheme}://{host}{_enc(path, '/')}?{q}"

    def mine(self, text: str) -> bool:
        """`text` holds an address of this store (signed or not)."""
        return any(f"{scheme}://{host}/" in text for scheme, host, _ in (self._where("x", self.public), self._where("x", self.endpoint)))

    async def aclose(self) -> None:
        if self._client is not None and self._own:
            await self._client.aclose()
        self._client = None if self._own else self._client


class LocalStore:
    """Objects as files under one directory. A link is a `file:` URI with an expiry and a signature in its query, shaped
    like the real thing so that what handles links is the same code in development; nothing serves or checks it."""

    def __init__(self, directory: str | os.PathLike, clock: Callable[[], float] = time.time) -> None:
        self.root, self.clock = Path(directory).resolve(), clock
        self._secret = secrets.token_bytes(32)

    def _path(self, key: str) -> Path:
        """Judged by how the key is written, not by asking the file system where it leads (which answers differently
        while another upload is making the same folder)."""
        if not KEY.fullmatch(key):
            raise StoreError("the object's key leaves the asset directory")
        return self.root.joinpath(*key.split("/"))

    async def ensure(self) -> None:
        await asyncio.to_thread(self.root.mkdir, parents=True, exist_ok=True)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        def write() -> None:
            path = self._path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".part")
            tmp.write_bytes(data)
            os.replace(tmp, path)  # a reader never sees half a file
        try:
            await asyncio.to_thread(write)
        except OSError as e:
            raise StoreError(f"the asset directory could not be written ({type(e).__name__})") from e

    async def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return await asyncio.to_thread(path.read_bytes) if path.is_file() else None

    async def head(self, key: str) -> int | None:
        path = self._path(key)
        return path.stat().st_size if path.is_file() else None

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._path(key).unlink, True)

    def link(self, key: str, ttl: int, at: float | None = None) -> str:
        until = int((self.clock() if at is None else at) + max(1, min(int(ttl), MAX_TTL)))
        sig = hmac.new(self._secret, f"{key}\n{until}".encode(), hashlib.sha256).hexdigest()
        return f"{self._path(key).as_uri()}?X-Awp-Expires={until}&X-Awp-Signature={sig}"

    def mine(self, text: str) -> bool:
        return self.root.as_uri() + "/" in text

    async def aclose(self) -> None:
        return None


def build_store(settings: Any) -> S3Store | LocalStore | None:
    """The store the settings name; None when uploads are off (AWP_ASSET_BACKEND empty). A setting that cannot work
    stops the start with its name, like any other."""
    backend = (settings.asset_backend or "").strip().lower()
    if not backend:
        return None
    if backend == "local":
        return LocalStore(Path(settings.workspace_dir) / "assets")
    if backend == "s3":
        return S3Store(settings.s3_endpoint, settings.s3_bucket, settings.s3_access_key, settings.s3_secret_key,
                       settings.s3_region, path_style=settings.s3_path_style, public_endpoint=settings.s3_public_endpoint)
    raise ValueError(f"AWP_ASSET_BACKEND must be local or s3 (or empty: no uploads), not {settings.asset_backend!r}")
