"""The asset store (spec A3, section 9): the SigV4 signer against AWS's published vectors, the local backend, the S3
backend against a server that checks every signature it is sent, and against a REAL MinIO when AWP_TEST_S3_ENDPOINT
(with AWP_TEST_S3_ACCESS_KEY and AWP_TEST_S3_SECRET_KEY) names one the tests may write to."""
import asyncio
import hashlib
import os
import re
import secrets
import time
from types import SimpleNamespace
from urllib.parse import parse_qsl, unquote, urlsplit

import httpx
import pytest

from awp import assets
from awp.assets import LocalStore, S3Store, StoreError

# ---- AWS's own examples ("Signature Calculations for the Authorization Header", "Authenticating Requests: Using Query
# Parameters" in the S3 API reference): the example credentials, bucket and date of that documentation ---------------------
AK, SK = "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
HOST, DATE, REGION = "examplebucket.s3.amazonaws.com", "20130524T000000Z", "us-east-1"
EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def sig(method, path, query, headers, payload_hash):
    return assets.signature(SK, REGION, DATE, assets.canonical_request(method, path, query, headers, payload_hash))


def test_the_signature_of_a_get_with_a_range_header_is_the_one_aws_publishes():
    headers = {"host": HOST, "range": "bytes=0-9", "x-amz-content-sha256": EMPTY, "x-amz-date": DATE}
    assert sig("GET", "/test.txt", {}, headers, EMPTY) == "f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    assert assets.authorization("GET", "/test.txt", {}, headers, EMPTY, access_key=AK, secret_key=SK, region=REGION, amz_date=DATE) == (
        "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request,"
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date,"
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41")


def test_the_signature_of_a_put_with_a_body_and_a_key_that_needs_encoding_is_the_one_aws_publishes():
    digest = hashlib.sha256(b"Welcome to Amazon S3.").hexdigest()
    assert digest == "44ce7dd67c959e0d3524ffac1771dfbba87d2b6b4b4e99e42034a8b803f8b072"
    headers = {"date": "Fri, 24 May 2013 00:00:00 GMT", "host": HOST, "x-amz-content-sha256": digest, "x-amz-date": DATE,
               "x-amz-storage-class": "REDUCED_REDUNDANCY"}
    assert sig("PUT", "/test$file.text", {}, headers, digest) == "98ad721746da40c64f1a55b78f14c238d841ea1380cd77a1b5971af0ece108bd"


def test_the_signatures_of_requests_with_query_parameters_are_the_ones_aws_publishes():
    headers = {"host": HOST, "x-amz-content-sha256": EMPTY, "x-amz-date": DATE}
    assert sig("GET", "/", {"lifecycle": ""}, headers, EMPTY) == "fea454ca298b7da1c68078a5d1bdbfbbe0d65c699e0f91ac7a200a0136783543"
    assert sig("GET", "/", {"prefix": "J", "max-keys": "2"}, headers, EMPTY) == "34b48302e7b5fa45bde8084f4b7868a86f0a534bc59db6670ed5711ef69dc6f7"


def test_the_presigned_url_is_the_one_aws_publishes():
    q = assets.presigned_query("GET", HOST, "/test.txt", access_key=AK, secret_key=SK, region=REGION, amz_date=DATE, expires=86400)
    assert q == ("X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAIOSFODNN7EXAMPLE%2F20130524%2Fus-east-1%2Fs3%2Faws4_request"
                 "&X-Amz-Date=20130524T000000Z&X-Amz-Expires=86400&X-Amz-SignedHeaders=host"
                 "&X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404")
    # the same through the store, in the virtual-host style of the example
    store = S3Store("https://s3.amazonaws.com", "examplebucket", AK, SK, REGION, path_style=False, clock=lambda: 1369353600.0)
    assert store.link("test.txt", 86400) == f"https://{HOST}/test.txt?{q}"


def test_a_changed_byte_anywhere_changes_the_signature():
    headers = {"host": HOST, "x-amz-content-sha256": EMPTY, "x-amz-date": DATE}
    base = sig("GET", "/test.txt", {}, headers, EMPTY)
    assert sig("GET", "/test.txu", {}, headers, EMPTY) != base
    assert sig("PUT", "/test.txt", {}, headers, EMPTY) != base
    assert sig("GET", "/test.txt", {}, {**headers, "host": "other.example"}, EMPTY) != base
    assert assets.signature(SK + "x", REGION, DATE, assets.canonical_request("GET", "/test.txt", {}, headers, EMPTY)) != base


# ---- what an asset is ----------------------------------------------------------------------------------------------------
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 24
GIF = b"GIF89a" + b"\x00" * 24
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 16


@pytest.mark.parametrize("data,kind", [(PNG, "image/png"), (JPEG, "image/jpeg"), (GIF, "image/gif"), (b"GIF87a..", "image/gif"),
                                       (WEBP, "image/webp")])
def test_the_type_is_read_from_the_first_bytes(data, kind):
    assert assets.sniff(data) == kind


@pytest.mark.parametrize("data", [b"", b"\x89PNG", b"<html><script>alert(1)</script>", b"%PDF-1.7", b"RIFF\x00\x00\x00\x00WAVEfmt ",
                                  b"<svg xmlns='http://www.w3.org/2000/svg'/>", b"MZ\x90\x00", b"GIF90a", b"PK\x03\x04"])
def test_bytes_that_are_not_one_of_the_four_image_types_have_no_type(data):
    assert assets.sniff(data) is None


def test_an_object_key_is_random_and_holds_nothing_of_the_upload():
    a, b = assets.new_key("client_1", "image/png"), assets.new_key("client_1", "image/png")
    assert a != b and re.fullmatch(r"client_1/[0-9a-f]{40}\.png", a)
    assert assets.new_key("client_1", "image/jpeg").endswith(".jpg")


def test_a_signed_link_is_recognised_and_cut_down_wherever_it_stands():
    link = "http://minio:9000/b/client_1/abc.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Expires=900&X-Amz-Signature=0123abcd"
    assert assets.unsigned(link) == "http://minio:9000/b/client_1/abc.png"
    text = f'{{"photo": "{link}", "note": "see {link} now"}}'
    assert assets.redact(text) == '{"photo": "http://minio:9000/b/client_1/abc.png", "note": "see http://minio:9000/b/client_1/abc.png now"}'
    assert assets.redact("no link here: http://example.org/a?b=1") == "no link here: http://example.org/a?b=1"
    assert assets.stable({"a": [link, 3], "b": {"c": link}, "n": None}) == {
        "a": ["http://minio:9000/b/client_1/abc.png", 3], "b": {"c": "http://minio:9000/b/client_1/abc.png"}, "n": None}


# ---- the local backend ----------------------------------------------------------------------------------------------------
def test_the_local_store_keeps_reads_and_removes_objects(tmp_path):
    async def go():
        store = LocalStore(tmp_path / "assets")
        await store.ensure()
        await store.ensure()
        key = assets.new_key("client_1", "image/png")
        assert await store.get(key) is None and await store.head(key) is None
        await store.put(key, PNG, "image/png")
        assert await store.get(key) == PNG and await store.head(key) == len(PNG)
        link = store.link(key, 60)
        assert assets.SIGNED.fullmatch(link) and link.startswith("file:") and store.mine(link) and store.mine(assets.unsigned(link))
        assert not store.mine("http://example.org/x.png")
        await store.delete(key)
        await store.delete(key)  # gone is gone
        assert await store.get(key) is None
        assert not list((tmp_path / "assets").rglob("*.part"))
    asyncio.run(go())


def test_the_local_store_never_leaves_its_directory(tmp_path):
    async def go():
        store = LocalStore(tmp_path / "assets")
        for key in ("../outside.png", "a/../../outside.png", str(tmp_path / "elsewhere.png")):
            with pytest.raises(StoreError):
                await store.put(key, PNG, "image/png")
        assert not (tmp_path / "outside.png").exists() and not (tmp_path / "elsewhere.png").exists()
    asyncio.run(go())


# ---- the S3 backend against a server that checks what it is sent -------------------------------------------------------------
class FakeS3:
    """Path-style or virtual-host S3 in memory. Every request must carry a signature that is right for exactly what
    arrived on the wire (method, path, host, date, body), computed here from the request itself."""

    def __init__(self, access=AK, secret=SK, region="us-east-1", bucket="pics", virtual=False):
        self.access, self.secret, self.region, self.bucket, self.virtual = access, secret, region, bucket, virtual
        self.buckets: set[str] = set()
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.seen: list[tuple[str, str]] = []

    def _denied(self, why):
        return httpx.Response(403, text=f"<Error><Code>{why}</Code></Error>")

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.seen.append((request.method, str(request.url)))
        auth = request.headers.get("authorization", "")
        m = re.fullmatch(r"AWS4-HMAC-SHA256 Credential=([^/]+)/(\d{8})/([^/]+)/s3/aws4_request,SignedHeaders=([^,]+),Signature=([0-9a-f]{64})", auth)
        if not m or m.group(1) != self.access:
            return self._denied("InvalidAccessKeyId")
        names = m.group(4).split(";")
        if not {"host", "x-amz-content-sha256", "x-amz-date"} <= set(names):
            return self._denied("AccessDenied")
        body = request.content
        if request.headers["x-amz-content-sha256"] != hashlib.sha256(body).hexdigest():
            return self._denied("XAmzContentSHA256Mismatch")
        path = unquote(request.url.raw_path.decode().split("?")[0])
        want = assets.signature(self.secret, m.group(3), request.headers["x-amz-date"], assets.canonical_request(
            request.method, path, dict(parse_qsl(request.url.query.decode(), keep_blank_values=True)),
            {n: request.headers[n] for n in names}, request.headers["x-amz-content-sha256"]))
        if want != m.group(5) or request.headers["x-amz-date"][:8] != m.group(2):
            return self._denied("SignatureDoesNotMatch")
        if self.virtual:
            bucket, key = request.headers["host"].split(".")[0], path.lstrip("/")
        else:
            bucket, _, key = path.lstrip("/").partition("/")
        if not key:
            if request.method == "HEAD":
                return httpx.Response(200 if bucket in self.buckets else 404)
            if request.method == "PUT":
                if bucket in self.buckets:
                    return httpx.Response(409, text="<Error><Code>BucketAlreadyOwnedByYou</Code></Error>")
                self.buckets.add(bucket)
                return httpx.Response(200)
        if bucket not in self.buckets:
            return httpx.Response(404, text="<Error><Code>NoSuchBucket</Code></Error>")
        if request.method == "PUT":
            self.objects[key] = (body, request.headers.get("content-type", ""))
            return httpx.Response(200)
        if request.method == "DELETE":
            self.objects.pop(key, None)
            return httpx.Response(204)
        if key not in self.objects:
            return httpx.Response(404, text="<Error><Code>NoSuchKey</Code></Error>")
        data, kind = self.objects[key]
        return httpx.Response(200, content=b"" if request.method == "HEAD" else data,
                              headers={"content-type": kind, "content-length": str(len(data))})


def s3(fake: FakeS3, **over) -> S3Store:
    args = dict(endpoint="http://s3.test:9000", bucket=fake.bucket, access_key=fake.access, secret_key=fake.secret,
                region=fake.region, path_style=not fake.virtual, client=httpx.AsyncClient(transport=httpx.MockTransport(fake.handle)))
    args.update(over)
    return S3Store(args.pop("endpoint"), args.pop("bucket"), args.pop("access_key"), args.pop("secret_key"), args.pop("region"), **args)


@pytest.mark.parametrize("virtual", [False, True])
def test_every_request_of_the_s3_store_is_signed_for_what_it_really_sends(virtual):
    async def go():
        fake = FakeS3(virtual=virtual)
        store = s3(fake)
        await store.ensure()  # no bucket yet: it is made
        assert fake.buckets == {"pics"}
        await store.ensure()  # there now: nothing is made
        assert [m for m, _ in fake.seen] == ["HEAD", "PUT", "HEAD"]
        key = assets.new_key("client_1", "image/jpeg")
        assert await store.get(key) is None and await store.head(key) is None
        await store.put(key, JPEG, "image/jpeg")
        assert fake.objects[key] == (JPEG, "image/jpeg")
        assert await store.get(key) == JPEG and await store.head(key) == len(JPEG)
        await store.delete(key)
        await store.delete(key)
        assert key not in fake.objects
        where = f"http://pics.s3.test:9000/{key}" if virtual else f"http://s3.test:9000/pics/{key}"
        assert fake.seen[-1] == ("DELETE", where)
    asyncio.run(go())


def test_a_bucket_another_process_made_meanwhile_is_fine_and_a_region_is_named_when_it_is_not_the_default():
    async def go():
        fake = FakeS3(region="ap-southeast-1")
        store = s3(fake)
        sent = []
        real = fake.handle

        def racing(request):
            if request.method == "HEAD":
                return httpx.Response(404)  # "not there" ... and then somebody else makes it first
            sent.append(request.content)
            fake.buckets.add("pics")
            return real(request)
        store._client = httpx.AsyncClient(transport=httpx.MockTransport(racing))
        await store.ensure()
        assert b"<LocationConstraint>ap-southeast-1</LocationConstraint>" in sent[0]
    asyncio.run(go())


def test_a_wrong_secret_a_refusal_and_a_dead_endpoint_are_errors_that_name_no_secret():
    async def go():
        fake = FakeS3()
        fake.buckets.add("pics")
        wrong = s3(fake, secret_key="not-the-secret")
        with pytest.raises(StoreError) as e:
            await wrong.put("client_1/x.png", PNG, "image/png")
        assert "SignatureDoesNotMatch" in str(e.value) and "not-the-secret" not in str(e.value) and "403" in str(e.value)
        with pytest.raises(StoreError):
            await wrong.ensure()
        for call in (wrong.get("client_1/x.png"), wrong.head("client_1/x.png"), wrong.delete("client_1/x.png")):
            with pytest.raises(StoreError):
                await call

        def dead(request):
            raise httpx.ConnectError("refused")
        down = s3(fake, client=httpx.AsyncClient(transport=httpx.MockTransport(dead)))
        with pytest.raises(StoreError) as e:
            await down.put("client_1/x.png", PNG, "image/png")
        assert "did not answer" in str(e.value) and SK not in str(e.value)
    asyncio.run(go())


def test_links_are_made_for_the_public_address_and_only_for_the_time_asked():
    store = S3Store("http://minio:9000", "pics", AK, SK, public_endpoint="https://files.example.org", clock=lambda: 1_800_000_000.0)
    link = store.link("client_1/abc.png", 900)
    parts = urlsplit(link)
    q = dict(parse_qsl(parts.query))
    assert (parts.scheme, parts.netloc, parts.path) == ("https", "files.example.org", "/pics/client_1/abc.png")
    assert q["X-Amz-Expires"] == "900" and q["X-Amz-Date"] == "20270115T080000Z" and q["X-Amz-SignedHeaders"] == "host"
    assert SK not in link and assets.SIGNED.fullmatch(link)
    assert store.link("client_1/abc.png", 900) == link  # the same moment, the same link
    assert store.link("client_1/abc.png", 900, at=1_800_000_001.0) != link
    assert dict(parse_qsl(urlsplit(store.link("k.png", 10**9)).query))["X-Amz-Expires"] == str(assets.MAX_TTL)
    assert store.mine(link) and store.mine("http://minio:9000/pics/x") and not store.mine("https://elsewhere.example/pics/x")


@pytest.mark.parametrize("bad", [dict(endpoint=""), dict(bucket=""), dict(access_key=""), dict(secret_key=""),
                                 dict(endpoint="ftp://x"), dict(endpoint="http://user:pw@host"), dict(endpoint="http://host/path"),
                                 dict(endpoint="minio:9000"), dict(public_endpoint="http://host/x?y=1")])
def test_a_setting_that_cannot_work_is_refused_when_the_store_is_built(bad):
    args = {"endpoint": "http://minio:9000", "bucket": "b", "access_key": "a", "secret_key": "s", "public_endpoint": "", **bad}
    with pytest.raises(ValueError):
        S3Store(args["endpoint"], args["bucket"], args["access_key"], args["secret_key"], public_endpoint=args["public_endpoint"])


def test_the_settings_choose_the_store(tmp_path):
    def settings(**kw):
        base = dict(asset_backend="", workspace_dir=str(tmp_path), s3_endpoint="http://minio:9000", s3_public_endpoint="",
                    s3_bucket="b", s3_access_key="a", s3_secret_key="s", s3_region="us-east-1", s3_path_style=True)
        return SimpleNamespace(**{**base, **kw})
    assert assets.build_store(settings()) is None
    local = assets.build_store(settings(asset_backend="local"))
    assert isinstance(local, LocalStore) and local.root == (tmp_path / "assets").resolve()
    assert isinstance(assets.build_store(settings(asset_backend="s3")), S3Store)
    with pytest.raises(ValueError):
        assets.build_store(settings(asset_backend="s3", s3_secret_key=""))
    with pytest.raises(ValueError):
        assets.build_store(settings(asset_backend="gcs"))


# ---- a real MinIO -----------------------------------------------------------------------------------------------------------
ENDPOINT = os.environ.get("AWP_TEST_S3_ENDPOINT", "").strip()
needs_minio = pytest.mark.skipif(not ENDPOINT, reason="a real S3 needs AWP_TEST_S3_ENDPOINT (and AWP_TEST_S3_ACCESS_KEY, "
                                                      "AWP_TEST_S3_SECRET_KEY): a MinIO the tests may write to")


def real(bucket: str | None = None, **over) -> S3Store:
    return S3Store(ENDPOINT, bucket or "awpt-" + secrets.token_hex(6), os.environ["AWP_TEST_S3_ACCESS_KEY"],
                   over.pop("secret_key", os.environ["AWP_TEST_S3_SECRET_KEY"]), os.environ.get("AWP_TEST_S3_REGION", "us-east-1"), **over)


async def drop(store: S3Store, *keys: str) -> None:
    for key in keys:
        await store.delete(key)
    await store._call("DELETE", None)  # the bucket itself (empty now)
    await store.aclose()


@needs_minio
def test_minio_a_missing_bucket_is_made_and_an_object_goes_round():
    async def go():
        store = real()
        assert (await store._call("HEAD", None)).status_code == 404
        await store.ensure()
        await store.ensure()
        assert (await store._call("HEAD", None)).status_code == 200
        key = assets.new_key("client_1", "image/png")
        data = PNG + secrets.token_bytes(200_000)
        assert await store.get(key) is None and await store.head(key) is None
        await store.put(key, data, "image/png")
        assert await store.head(key) == len(data) and await store.get(key) == data
        await store.put(key, JPEG, "image/jpeg")  # the same key again replaces
        assert await store.get(key) == JPEG
        await store.delete(key)
        await store.delete(key)
        assert await store.get(key) is None
        await drop(store)
    asyncio.run(go())


@needs_minio
def test_minio_a_presigned_link_reads_that_one_object_without_credentials_until_it_expires():
    async def go():
        store = real()
        await store.ensure()
        mine, other = assets.new_key("client_1", "image/png"), assets.new_key("client_2", "image/png")
        await store.put(mine, PNG + b"mine", "image/png")
        await store.put(other, PNG + b"other", "image/png")
        async with httpx.AsyncClient() as anyone:  # no key, no signature header: only the link
            link = store.link(mine, 60)
            got = await anyone.get(link)
            assert got.status_code == 200 and got.content == PNG + b"mine" and got.headers["content-type"] == "image/png"
            assert (await anyone.get(assets.unsigned(link))).status_code == 403  # the bucket is private
            assert (await anyone.get(link.replace(mine, other))).status_code == 403  # the signature is for one object
            assert (await anyone.get(link[:-1] + ("0" if link[-1] != "0" else "1"))).status_code == 403
            assert (await anyone.put(link, content=b"overwrite")).status_code == 403  # a link to read, not to write
            assert (await anyone.delete(link)).status_code == 403
            longer = link.replace("X-Amz-Expires=60", "X-Amz-Expires=86400")
            assert (await anyone.get(longer)).status_code == 403  # the lifetime is signed too
            assert (await anyone.get(store.link(mine, 30, at=time.time() - 120))).status_code == 403  # expired 90 s ago
            short = store.link(mine, 1)
            assert (await anyone.get(short)).status_code == 200
            await asyncio.sleep(2.5)
            assert (await anyone.get(short)).status_code == 403
        assert await store.get(mine) == PNG + b"mine"
        await drop(store, mine, other)
    asyncio.run(go())


@needs_minio
def test_minio_refuses_a_wrong_secret_and_the_error_says_so_without_the_secret():
    async def go():
        good = real()
        await good.ensure()
        bad = real(good.bucket, secret_key="definitely-not-the-secret")
        for call in (bad.put("client_1/x.png", PNG, "image/png"), bad.get("client_1/x.png"), bad.ensure()):
            with pytest.raises(StoreError) as e:
                await call
            assert "403" in str(e.value) and "definitely-not-the-secret" not in str(e.value)
        assert await good.head("client_1/x.png") is None  # nothing was written
        await bad.aclose()
        await drop(good)
    asyncio.run(go())


@needs_minio
def test_minio_two_processes_making_the_bucket_at_once_both_succeed():
    async def go():
        a = real()
        b = real(a.bucket)
        await asyncio.gather(a.ensure(), b.ensure(), a.ensure(), b.ensure())
        assert (await a._call("HEAD", None)).status_code == 200
        await b.aclose()
        await drop(a)
    asyncio.run(go())
