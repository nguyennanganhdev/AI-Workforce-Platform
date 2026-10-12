"""Image assets at the partner API (spec A3, an extension beyond contract v1): the upload, every refusal, idempotency,
messages that carry an image, what the public reads show, the admin's switch. Fake engine, local store."""
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from assetkit import ASSET, GIF, JPEG, OPS, PNG, URL, WEBP, error, files, grant, image, rows, store_of, upload, uploaded, with_images
from conftest import ADM, ADM_B, key_headers


@pytest.fixture
def flow(make_flow):
    with make_flow(asset_backend="local") as f:
        yield with_images(f)


def test_an_upload_is_stored_under_a_key_nobody_chose_and_answers_with_an_id_only(flow):
    data = PNG + b"the picture"
    r = upload(flow.http, flow.key["api_key"], data, rid="up-first", user="resident-123", conv="CHAT-../../etc")
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) == {"asset_id", "content_type", "size", "sha256", "external_user_id", "external_conversation_id", "created_at"}
    assert ASSET.fullmatch(body["asset_id"]) and body["content_type"] == "image/png" and body["size"] == len(data)
    assert body["sha256"] == hashlib.sha256(data).hexdigest() and body["created_at"].endswith("Z")
    [row] = rows(flow.env)
    assert (row["id"], row["client_id"], row["external_user_id"], row["external_conversation_id"], row["conversation_id"]) == (
        body["asset_id"], flow.client["client_id"], "resident-123", "CHAT-../../etc", None)
    # the key: the client's platform id and random hex. Nothing the caller sent is in it, and it is in no answer.
    key = row["object_key"]
    assert key.startswith(flow.client["client_id"] + "/") and key.endswith(".png") and len(key.split("/")[1]) == 44
    assert not any(part in key for part in ("resident", "CHAT", "etc", "up-first", body["asset_id"][4:]))
    assert key not in r.text and "object_key" not in r.text and "http" not in r.text.lower() and "file:" not in r.text
    [stored] = files(flow.env)
    assert stored.read_bytes() == data and stored.is_relative_to(store_of(flow.env).root)


@pytest.mark.parametrize("data,kind", [(PNG, "image/png"), (JPEG, "image/jpeg"), (GIF, "image/gif"), (WEBP, "image/webp")])
def test_the_four_image_types_are_taken_whatever_the_header_says(flow, data, kind):
    for declared in ("image/png", "text/plain", "application/octet-stream", None):
        assert uploaded(flow, data, content_type=declared)["content_type"] == kind
    assert {r["content_type"] for r in rows(flow.env)} == {kind}


@pytest.mark.parametrize("data", [b"", b"<html><script>alert(1)</script></html>", b"%PDF-1.7 ...", b"\x89PNG but not really",
                                  b"<svg xmlns='http://www.w3.org/2000/svg' onload='x()'/>", b"MZ\x90\x00\x03", b"RIFF\x00\x00\x00\x00WAVEfmt "])
def test_bytes_that_are_not_an_image_are_refused_whatever_the_header_says(flow, data):
    r = upload(flow.http, flow.key["api_key"], data, content_type="image/png")
    assert error(r) == (422, "VALIDATION_FAILED") and r.json()["error"]["details"]["errors"][0]["field"] == "body"
    assert rows(flow.env) == [] and files(flow.env) == []


def test_without_the_operation_on_the_key_nothing_is_taken(flow):
    plain = flow.env.key(flow.client["client_id"])  # every operation of contract v1, not attach_asset
    r = upload(flow.http, plain["api_key"])
    assert error(r) == (403, "PERMISSION_DENIED") and r.json()["error"]["details"] == {"operation": "attach_asset"}
    assert rows(flow.env) == [] and files(flow.env) == []


def test_without_the_capability_on_the_client_nothing_is_taken_and_the_switch_works_at_once(flow):
    assert grant(flow.env, flow.client["client_id"], on=False).json()["capabilities"] == []
    r = upload(flow.http, flow.key["api_key"])
    assert error(r) == (403, "PERMISSION_DENIED") and r.json()["error"]["details"] == {"capability": "attach_asset"}
    assert rows(flow.env) == [] and files(flow.env) == []
    assert grant(flow.env, flow.client["client_id"]).status_code == 200
    assert upload(flow.http, flow.key["api_key"]).status_code == 201


def test_a_missing_or_wrong_credential_is_refused_before_anything_else(flow):
    assert error(flow.http.post(URL, content=PNG)) == (401, "UNAUTHENTICATED")
    assert error(upload(flow.http, "dp_nokey.nosecret")) == (401, "UNAUTHENTICATED")
    provider = flow.env.post(f"/platform/v1/wf/clients/{flow.client['client_id']}/integrations", {"event_schema": {
        "version": "1", "version_mode": "snapshot", "events": {"x.done": {"status": "completed", "rank": 1}}}}).json()
    pkey = flow.env.post(f"/platform/v1/wf/integrations/{provider['integration_id']}/keys").json()["api_key"]
    r = upload(flow.http, pkey)
    assert error(r) == (403, "PERMISSION_DENIED") and r.json()["error"]["details"]["reason"] == "wrong_credential_kind"
    assert rows(flow.env) == []


def test_the_three_ids_are_required_and_checked_like_any_partner_id(flow):
    for missing in ("rid", "user", "conv"):
        kw = {"rid": "up-x", "user": "resident-123", "conv": "CHAT-1", missing: None}
        if missing == "rid":
            r = flow.http.post(URL, params={"external_user_id": "u", "external_conversation_id": "c"}, content=PNG, headers=flow.h)
        else:
            r = upload(flow.http, flow.key["api_key"], **kw)
        assert error(r) == (422, "VALIDATION_FAILED"), r.text
    r = upload(flow.http, flow.key["api_key"], user="x" * 201, conv="bad\x07bell")
    fields = {e["field"] for e in r.json()["error"]["details"]["errors"]}
    assert error(r) == (422, "VALIDATION_FAILED") and fields == {"external_user_id", "external_conversation_id"}
    assert "bell" not in r.text  # a refused value is never echoed
    assert rows(flow.env) == [] and files(flow.env) == []


def test_an_upload_over_the_limit_is_cut_off_while_it_is_read(make_flow):
    with make_flow(asset_backend="local", asset_max_bytes=1000) as f:
        with_images(f)
        assert upload(f.http, f.key["api_key"], PNG + b"x" * (1000 - len(PNG))).status_code == 201  # exactly the limit
        r = upload(f.http, f.key["api_key"], PNG + b"x" * 1000)  # declared by Content-Length: refused unread
        assert error(r) == (413, "PAYLOAD_TOO_LARGE") and r.json()["error"]["details"] == {"limit_bytes": 1000}

        def pieces():  # no Content-Length: the limit is found while reading
            yield PNG
            for _ in range(50):
                yield b"y" * 100
        r = f.http.post(URL, params={"external_request_id": "up-stream", "external_user_id": "u", "external_conversation_id": "c"},
                        content=pieces(), headers=f.h)
        assert error(r) == (413, "PAYLOAD_TOO_LARGE")
        assert len(rows(f.env)) == 1 and len(files(f.env)) == 1
        # the key, the operation and the capability are judged before a byte of the body counts
        plain = f.env.key(f.client["client_id"])
        assert error(upload(f.http, plain["api_key"], PNG + b"x" * 5000)) == (403, "PERMISSION_DENIED")
        assert error(upload(f.http, "dp_nokey.nosecret", PNG + b"x" * 5000)) == (401, "UNAUTHENTICATED")


def test_the_default_limit_is_five_mebibytes_and_a_json_endpoint_keeps_its_own(flow):
    assert flow.env.app.state.wf.settings.asset_max_bytes == 5 * 1024 * 1024
    assert uploaded(flow, PNG + b"z" * 400_000)["size"] == len(PNG) + 400_000  # above the 256 KiB of a JSON body
    big = flow.start_body(message={"type": "text", "text": "x" * 20000}, padding="y" * 300_000)
    assert error(flow.post(big)) == (413, "PAYLOAD_TOO_LARGE")


def test_without_a_store_the_upload_says_so_and_is_not_worth_retrying(make_flow):
    with make_flow() as f:  # AWP_ASSET_BACKEND empty
        with_images(f)
        r = upload(f.http, f.key["api_key"])
        e = r.json()["error"]
        assert (r.status_code, e["code"], e["retryable"], e["details"]) == (
            503, "INTERNAL_ERROR", False, {"reason": "asset_store_not_configured"})
        assert rows(f.env) == []


def test_a_store_that_is_down_costs_the_upload_not_the_start(make_flow):
    with make_flow(asset_backend="s3", s3_endpoint="http://127.0.0.1:9", s3_bucket="b", s3_access_key="a", s3_secret_key="s") as f:
        with_images(f)
        assert f.http.get("/platform/v1/health").status_code == 200  # the platform started without its store
        r = upload(f.http, f.key["api_key"])
        e = r.json()["error"]
        assert (r.status_code, e["code"], e["retryable"], e["details"]) == (503, "INTERNAL_ERROR", True, {"reason": "asset_store_unavailable"})
        assert rows(f.env) == [] and "127.0.0.1" not in r.text
        body, first = f.begin()  # text goes on as ever
        assert first["request_status"] == "completed"


# ---- idempotency ------------------------------------------------------------------------------------------------------------
def test_the_same_upload_again_is_the_same_asset(flow):
    first = upload(flow.http, flow.key["api_key"], PNG, rid="up-same")
    again = upload(flow.http, flow.key["api_key"], PNG, rid="up-same", content_type="text/plain")
    assert first.status_code == again.status_code == 201 and again.json() == first.json()
    assert len(rows(flow.env)) == 1 and len(files(flow.env)) == 1
    other = upload(flow.http, flow.key["api_key"], PNG, rid="up-other")  # the same bytes under another id: another asset
    assert other.json()["asset_id"] != first.json()["asset_id"] and other.json()["sha256"] == first.json()["sha256"]
    assert len(rows(flow.env)) == 2 and len(files(flow.env)) == 2


def test_the_same_id_with_another_upload_or_another_command_is_a_conflict(flow):
    assert upload(flow.http, flow.key["api_key"], PNG, rid="up-1").status_code == 201
    assert error(upload(flow.http, flow.key["api_key"], JPEG, rid="up-1")) == (409, "IDEMPOTENCY_CONFLICT")
    assert error(upload(flow.http, flow.key["api_key"], PNG, rid="up-1", user="resident-999")) == (409, "IDEMPOTENCY_CONFLICT")
    assert error(upload(flow.http, flow.key["api_key"], PNG, rid="up-1", conv="CHAT-OTHER")) == (409, "IDEMPOTENCY_CONFLICT")
    # one namespace for every command of a client (contract 9.1): a request cannot reuse an upload's id, nor the other way
    assert error(flow.post(flow.start_body(external_request_id="up-1"))) == (409, "IDEMPOTENCY_CONFLICT")
    body, started = flow.begin()
    assert error(upload(flow.http, flow.key["api_key"], PNG, rid=body["external_request_id"])) == (409, "IDEMPOTENCY_CONFLICT")
    assert len(rows(flow.env)) == 1 and len(files(flow.env)) == 1
    # an upload is not a request a partner can read back
    [(rid,)] = flow.env.sql("select id from wf_requests where command_type='attach_asset'")
    assert flow.request(rid).status_code == 404


def test_twins_of_one_upload_sent_at_once_make_one_asset_and_leave_one_object(flow):
    def send(_):
        return upload(flow.http, flow.key["api_key"], PNG + b"twin", rid="up-twin")
    with ThreadPoolExecutor(6) as ex:
        got = list(ex.map(send, range(6)))
    assert [r.status_code for r in got] == [201] * 6, [r.text for r in got]
    assert len({r.json()["asset_id"] for r in got}) == 1
    assert len(rows(flow.env)) == 1 and len(files(flow.env)) == 1  # the losers' objects were taken out again


def test_another_clients_same_request_id_is_its_own(flow):
    other = flow.env.client(name="Other")
    grant(flow.env, other["client_id"])
    okey = flow.env.key(other["client_id"], operations=OPS)
    a = upload(flow.http, flow.key["api_key"], PNG, rid="up-shared").json()
    b = upload(flow.http, okey["api_key"], PNG, rid="up-shared").json()
    assert a["asset_id"] != b["asset_id"]
    keys = {r["client_id"]: r["object_key"] for r in rows(flow.env)}
    assert keys[other["client_id"]].startswith(other["client_id"] + "/") and keys[flow.client["client_id"]].startswith(flow.client["client_id"] + "/")


# ---- messages that carry an image ----------------------------------------------------------------------------------------------
def test_an_image_message_is_unsupported_for_a_client_without_the_capability(flow):
    asset = uploaded(flow, conv="CHAT-A")
    grant(flow.env, flow.client["client_id"], on=False)
    r, _ = flow.start(external_conversation_id="CHAT-A", message=image(asset["asset_id"]))
    assert error(r) == (422, "UNSUPPORTED_MESSAGE_PART") and r.json()["error"]["details"] == {"part_type": "image"}
    assert flow.env.sql("select count(*) from wf_workflows")[0][0] == 0


@pytest.mark.parametrize("part", [{"type": "file", "asset_id": "ast_" + "0" * 32}, {"type": "audio", "text": "x"}, {"type": "url", "url": "http://x"}])
def test_other_kinds_of_part_stay_unsupported_with_the_capability(flow, part):
    r, _ = flow.start(message=part)
    assert error(r) == (422, "UNSUPPORTED_MESSAGE_PART")


def test_an_image_starts_a_workflow_and_every_public_read_names_it_by_id_only(flow):
    asset = uploaded(flow, PNG + b"leak", conv="CHAT-A")
    r, body = flow.start(external_conversation_id="CHAT-A", message=image(asset["asset_id"], "Nước rò ở đây."))
    assert r.status_code == 200, r.text
    started = r.json()
    [(text, ids)] = flow.env.sql("select text, asset_ids from wf_messages where sender='user'")
    assert text == "Nước rò ở đây." and (json.loads(ids) if isinstance(ids, str) else ids) == [asset["asset_id"]]
    [row] = rows(flow.env)
    assert row["conversation_id"] == started["conversation_id"]  # bound, for good
    snap = flow.snapshot(started["conversation_id"]).json()
    mine = [m for m in snap["messages"] if m["sender"] == "user"]
    assert mine == [{"message_id": mine[0]["message_id"], "workflow_id": started["workflow_id"], "sender": "user",
                     "text": "Nước rò ở đây.", "created_at": mine[0]["created_at"], "asset_ids": [asset["asset_id"]]}]
    assert all("asset_ids" not in m for m in snap["messages"] if m["sender"] == "assistant")  # contract v1 messages are as they were
    events = flow.history(started["conversation_id"]).json()["items"]
    accepted = next(e for e in events if e["event_type"] == "request.accepted")
    assert accepted["payload"] == {"request_id": started["request_id"], "asset_ids": [asset["asset_id"]]}
    everything = json.dumps([r.json(), snap, events, flow.request(started["request_id"]).json()])
    assert row["object_key"] not in everything and "object_key" not in everything and "file:" not in everything
    assert str(store_of(flow.env).root.name) + "/" not in everything


def test_an_image_alone_is_a_message_and_a_reply_may_carry_one_too(flow):
    first = uploaded(flow, conv="CHAT-A")
    r, body = flow.start(external_conversation_id="CHAT-A", message=image(first["asset_id"]))
    assert r.status_code == 200, r.text
    second = uploaded(flow, JPEG, conv="CHAT-A")
    r2, _ = flow.reply(body, r.json(), message=image(second["asset_id"], "thêm một ảnh"))
    assert r2.status_code == 200, r2.text
    again, _ = flow.reply(body, r.json(), message=image(first["asset_id"], "ảnh cũ lần nữa"))  # the same image twice: fine
    assert again.status_code == 200, again.text
    sent = [(t, json.loads(a) if isinstance(a, str) else a) for t, a in
            flow.env.sql("select text, asset_ids from wf_messages where sender='user' order by sequence")]
    assert sent == [("", [first["asset_id"]]), ("thêm một ảnh", [second["asset_id"]]), ("ảnh cũ lần nữa", [first["asset_id"]])]
    assert {r_["conversation_id"] for r_ in rows(flow.env)} == {r.json()["conversation_id"]}
    text_only, _ = flow.reply(body, r.json())
    assert text_only.status_code == 200 and "asset_ids" not in json.dumps(
        [m for m in flow.snapshot(r.json()["conversation_id"]).json()["messages"] if m["text"] == "Tôi rảnh từ 14 giờ."])


def test_a_malformed_image_part_is_a_schema_error_and_nothing_is_fetched(flow):
    hits = []

    class Seen(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(PNG)

        def log_message(self, *a):
            pass
    server = HTTPServer(("127.0.0.1", 0), Seen)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    here = f"http://127.0.0.1:{server.server_port}/photo.png"
    try:
        asset = uploaded(flow, conv="CHAT-A")
        for part in ({"type": "image"}, {"type": "image", "asset_id": "photo-1"}, {"type": "image", "asset_id": here},
                     {"type": "image", "url": here}, {"type": "image", "asset_id": asset["asset_id"], "url": here},
                     {"type": "image", "asset_id": asset["asset_id"], "text": "   "},
                     {"type": "image", "asset_ids": [asset["asset_id"]]}):
            r, _ = flow.start(external_conversation_id="CHAT-A", message=part)
            assert error(r) == (422, "VALIDATION_FAILED"), (part, r.text)
        # an address inside the words of a message is words: stored, shown, and never called
        r, _ = flow.start(external_conversation_id="CHAT-A", message=image(asset["asset_id"], f"xem thêm ở {here}"))
        assert r.status_code == 200
        r, _ = flow.start(message={"type": "text", "text": f"ảnh ở đây {here} và {here}?x=1"})
        assert r.status_code == 200
        assert error(upload(flow.http, flow.key["api_key"], here.encode())) == (422, "VALIDATION_FAILED")  # an address is not an image
    finally:
        server.shutdown()
        server.server_close()
    assert hits == []


# ---- whose asset --------------------------------------------------------------------------------------------------------------
def test_an_asset_of_another_user_conversation_or_client_is_no_asset(flow):
    mine = uploaded(flow, user="resident-123", conv="CHAT-A")
    theirs = uploaded(flow, user="resident-999", conv="CHAT-A")
    elsewhere = uploaded(flow, user="resident-123", conv="CHAT-B")
    other = flow.env.client(name="Other")
    grant(flow.env, other["client_id"])
    okey = flow.env.key(other["client_id"], operations=OPS)
    foreign = upload(flow.http, okey["api_key"], PNG, user="resident-123", conv="CHAT-A").json()
    unknown = "ast_" + "0" * 32
    answers = set()
    for asset_id in (theirs["asset_id"], elsewhere["asset_id"], foreign["asset_id"], unknown):
        body = flow.start_body(external_conversation_id="CHAT-A", message=image(asset_id, "xem ảnh"))
        r = flow.post(body)
        assert error(r) == (404, "NOT_FOUND"), r.text
        e = r.json()["error"]
        answers.add((e["message"], json.dumps(e["details"], sort_keys=True)))
        assert flow.env.sql("select count(*) from wf_requests where external_request_id=?", (body["external_request_id"],))[0][0] == 0
    assert len(answers) == 1  # one answer for all four: it says nothing about what exists
    assert flow.env.sql("select count(*) from wf_workflows")[0][0] == 0
    # the other client cannot use this client's asset either, with the right user and conversation
    oroute = flow.env.active_route(other["client_id"], okey["api_key"], ref="BQL-OTHER")
    stolen = flow.start_body(external_management_ref=oroute["external_management_ref"], external_conversation_id="CHAT-A",
                             message=image(mine["asset_id"]))
    assert error(flow.post(stolen, headers=key_headers(okey["api_key"]))) == (404, "NOT_FOUND")
    assert all(r["conversation_id"] is None for r in rows(flow.env))  # no refusal bound anything
    # and the rightful one still works, with the request id of a refusal (a refusal leaves nothing behind)
    r, _ = flow.start(external_conversation_id="CHAT-A", message=image(mine["asset_id"]))
    assert r.status_code == 200, r.text


def test_an_asset_cannot_move_to_another_conversation_once_it_was_sent(flow):
    asset = uploaded(flow, conv="CHAT-A")
    r, body = flow.start(external_conversation_id="CHAT-A", message=image(asset["asset_id"]))
    assert r.status_code == 200
    second, _ = flow.start(external_conversation_id="CHAT-B", message=image(asset["asset_id"]))
    assert error(second) == (404, "NOT_FOUND")
    other_body, other = flow.begin(external_conversation_id="CHAT-C")
    moved, _ = flow.reply(other_body, other, message=image(asset["asset_id"]))  # a reply in another conversation of the same user
    assert error(moved) == (404, "NOT_FOUND")
    [row] = rows(flow.env)
    assert row["conversation_id"] == r.json()["conversation_id"]


def test_the_binding_errors_of_a_request_come_before_the_asset_and_a_replay_returns_the_same_request(flow):
    asset = uploaded(flow, conv="CHAT-A")
    body = flow.start_body(external_conversation_id="CHAT-A", message=image(asset["asset_id"], "ảnh"))
    first = flow.post(body)
    assert first.status_code == 200
    again = flow.post(body)
    assert again.status_code == 200 and again.json() == first.json()
    changed = flow.post({**body, "message": image("ast_" + "1" * 32, "ảnh")})  # the same id with another image
    assert error(changed) == (409, "IDEMPOTENCY_CONFLICT")
    taken = flow.start_body(external_conversation_id="CHAT-A", message=image("ast_" + "2" * 32))  # the conversation is taken
    assert error(flow.post(taken)) == (409, "CONVERSATION_ALREADY_BOUND")


# ---- the operator's switch ----------------------------------------------------------------------------------------------------
def test_only_the_tenants_admin_changes_a_clients_capabilities(flow):
    cid = flow.client["client_id"]
    assert error_code(grant(flow.env, cid, headers=ADM_B)) == 404  # another tenant's admin: no such client
    manager = flow.env.manager_key(flow.env.default_manager(cid))
    assert grant(flow.env, cid, headers=manager).status_code == 403
    assert grant(flow.env, cid, headers=flow.h).status_code == 401  # a partner's key opens no admin API
    bad = flow.env.http.patch(f"/platform/v1/wf/clients/{cid}", json={"capabilities": ["fly"]}, headers=ADM)
    twice = flow.env.http.patch(f"/platform/v1/wf/clients/{cid}", json={"capabilities": ["attach_asset", "attach_asset"]}, headers=ADM)
    extra = flow.env.http.patch(f"/platform/v1/wf/clients/{cid}", json={"capabilities": [], "status": "disabled"}, headers=ADM)
    assert (bad.status_code, twice.status_code, extra.status_code) == (422, 422, 422)
    assert flow.env.http.get(f"/platform/v1/wf/clients/{cid}", headers=ADM).json()["capabilities"] == ["attach_asset"]
    off = grant(flow.env, cid, on=False)
    assert off.status_code == 200 and off.json()["capabilities"] == [] and off.json()["client_id"] == cid


def error_code(r) -> int:
    return r.status_code


def test_a_key_may_be_given_the_operation_and_a_route_confirmation_does_not_list_it(flow):
    assert "attach_asset" in flow.key["operations"]
    route = flow.env.route(flow.client["client_id"], ref="BQL-2")
    confirmed = flow.env.confirm(flow.key["api_key"], route).json()
    assert confirmed["allowed_operations"] == ["submit_request", "reply", "read_result", "receive_events", "submit_consent", "close_workflow"]
    made = flow.env.post(f"/platform/v1/wf/integrations/{_integration(flow)}/keys", {"operations": ["attach_asset"]})
    assert made.status_code == 422  # not an operation of a provider's key


def _integration(flow) -> str:
    return flow.env.post(f"/platform/v1/wf/clients/{flow.client['client_id']}/integrations", {"event_schema": {
        "version": "1", "version_mode": "snapshot", "events": {"x.done": {"status": "completed", "rank": 1}}}}).json()["integration_id"]
