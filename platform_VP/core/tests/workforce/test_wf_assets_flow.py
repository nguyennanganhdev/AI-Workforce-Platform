"""Image assets on the real engine (spec A3): what the leader is told, the link it may get for a partner tool, and where
that link may and may not go. Scripted model, a real MCP server as the partner, the local store; one walk on a REAL
MinIO when AWP_TEST_S3_ENDPOINT names one."""
import asyncio
import json
import secrets
from types import SimpleNamespace

import httpx
import pytest

from assetkit import ASSET, JPEG, LINK, PNG, S3_ENDPOINT, files, image, minio_settings, rows, store_of, uploaded, with_images
from awp import assets
from awp.protocol.assetlink import CaseAssetLink
from awp.runtime import Binding
from awp.workforce import ledger, retention
from enginekit import evidence_of, world
from fake_llm import CALLS, Call
from partnerkit import Partner
from scripts import say
from t1kit import SETTINGS, TOOLS, configure, ops

LOCAL = dict(asset_backend="local")


@pytest.fixture
def partner():
    with Partner() as p:
        yield p


def seen_by_the_model() -> str:
    return json.dumps([c.get("shape") for c in CALLS], ensure_ascii=False)


def noted(c: Call):
    return say("Noted.", "reply") if c.after_user().called("CaseSay") == 0 else "Said."


def pass_photo(tool: str = "partner_repair"):
    """The leader gets a link to the first image of the message and hands it to the partner's tool, then says so."""
    def script(c: Call):
        turn = c.after_user()
        ids = ASSET.findall(c.last_user)
        if ids and turn.called("CaseAssetLink") == 0:
            return [("CaseAssetLink", {"asset_id": ids[0]})]
        links = turn.results("CaseAssetLink")
        if links and turn.called(tool) == 0:
            return [(tool, {"slot": "mon", "note": links[0].split("\n")[0]})]
        if turn.called("CaseSay") == 0:
            ev = evidence_of(" ".join(turn.results(tool)))
            return say("I passed your photo on; the visit is pending.", "none", ev[:1])
        return "Said."
    return script


def public(w, started: dict) -> str:
    """Everything a partner can read about the conversation."""
    conv = started["conversation_id"]
    return json.dumps([started, w.flow.snapshot(conv).json(), w.flow.history(conv, limit=500).json(),
                       w.flow.request(started["request_id"]).json()], ensure_ascii=False)


def test_the_leader_is_told_how_many_images_came_and_their_ids_and_nothing_of_where_they_are(tmp_path):
    with world(tmp_path, noted, **LOCAL) as w:
        with_images(w.flow)
        asset = uploaded(w.flow, PNG + b"pipe", conv="CHAT-A")
        r, body = w.flow.start(external_conversation_id="CHAT-A", message=image(asset["asset_id"], "The pipe leaks here."))
        assert r.status_code == 200, r.text
        first = next(c for c in CALLS if "<resident-message" in c["last_user"])
        assert "The pipe leaks here." in first["last_user"]
        assert (f"The resident attached 1 image(s): {asset['asset_id']} (image/png, {asset['size']} bytes). You are given "
                "references only") in first["last_user"]
        assert "CaseAssetLink" in first["tools"]
        [row] = rows(w.env)
        told = seen_by_the_model()
        assert row["object_key"] not in told and not LINK.search(told) and "file:" not in told
        # the case file keeps it too (the context may be compacted away)
        case = w.sql("select case_id from wf_workflows")[0][0]
        [said] = [i for i in w.run(lambda: w.rt.cases.items(case, kinds=("evidence",))) if i.author == "resident"]
        assert said.data["text"] == f"The pipe leaks here.\n[attached image(s): {asset['asset_id']}]"
        # a later turn's state block still says that the message had an image
        r2, _ = w.flow.reply(body, r.json())
        assert r2.status_code == 200
        later = [c for c in CALLS if "<resident-message" in c["last_user"]][-1]
        assert f"(with 1 image(s): {asset['asset_id']})" in json.dumps(later["shape"])


def test_an_image_with_no_words_still_reaches_the_leader(tmp_path):
    with world(tmp_path, noted, **LOCAL) as w:
        with_images(w.flow)
        asset = uploaded(w.flow, JPEG, conv="CHAT-A")
        r, _ = w.flow.start(external_conversation_id="CHAT-A", message=image(asset["asset_id"]))
        assert r.status_code == 200 and r.json()["request_status"] == "completed", r.text
        first = next(c for c in CALLS if "<resident-message" in c["last_user"])
        assert f"attached 1 image(s): {asset['asset_id']} (image/jpeg, {len(JPEG)} bytes)" in first["last_user"]


def test_a_client_without_the_capability_gives_its_leader_no_link_tool(tmp_path):
    with world(tmp_path, noted, **LOCAL) as w:
        _, first = w.flow.begin()
        assert first["request_status"] == "completed"
        offered = {name for c in CALLS for name in c["tools"]}
        assert "CaseSay" in offered and "CaseAssetLink" not in offered
    CALLS.clear()


def test_without_a_store_no_leader_has_the_link_tool(tmp_path):
    with world(tmp_path, noted) as w:
        with_images(w.flow)
        _, first = w.flow.begin()
        assert first["request_status"] == "completed"
        assert "CaseAssetLink" not in {name for c in CALLS for name in c["tools"]}


def test_a_link_goes_into_the_partners_tool_and_nowhere_a_resident_or_a_record_could_show_it(tmp_path, partner):
    with world(tmp_path, pass_photo(), **LOCAL, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        with_images(w.flow)
        asset = uploaded(w.flow, PNG + b"pipe", conv="CHAT-A")
        r, _ = w.flow.start(external_conversation_id="CHAT-A", message=image(asset["asset_id"], "Please send someone."))
        assert r.status_code == 200, r.text
        started = r.json()
        assert started["workflow_state"] == "waiting_external_event"
        [call] = partner.of("book_repair")
        link = call["args"]["note"]
        [row] = rows(w.env)
        assert LINK.search(link) and assets.SIGNED.fullmatch(link) and row["object_key"] in link  # the partner got a signed link
        assert store_of(w.env).mine(link)
        # the resident and the partner's reads: no link, no address, no key
        out = public(w, started)
        assert not LINK.search(out) and row["object_key"] not in out and "file:" not in out
        assert [m["text"] for m in started["result"]["messages"]] == ["I passed your photo on; the visit is pending."]
        # the case file: that a link was made and to what, without the signature; the partner call's own record likewise
        case = w.sql("select case_id from wf_workflows")[0][0]
        evidence = w.run(lambda: w.rt.cases.items(case, kinds=("evidence",)))
        [made] = [i for i in evidence if i.data.get("tool") == "CaseAssetLink"]
        assert made.data["asset"] == asset["asset_id"] and assets.unsigned(link) in made.data["text"]
        assert "valid for 900 seconds" in made.data["text"] and "image/png" in made.data["text"]
        everything = json.dumps([i.data for i in evidence])
        assert not LINK.search(everything)
        [sent] = [i for i in evidence if i.data.get("tool") == "partner_repair"]
        assert assets.unsigned(link) in sent.data["input"]
        # one operation, and it is found again under a link signed at another moment
        [op] = ops(w, started["workflow_id"])
        assert op["status"] == "pending"
        later = store_of(w.env).link(row["object_key"], 900, at=4_000_000_000.0)
        assert later != link and ledger.hash_of({"slot": "mon", "note": later}) == op["args_hash"]
        assert ledger.hash_of({"slot": "mon", "note": link.replace(row["object_key"], "client_x/other.png")}) != op["args_hash"]


def test_the_leader_cannot_show_a_link_or_the_stores_address_to_the_resident(tmp_path):
    tried = []

    def script(c: Call):
        turn = c.after_user()
        ids = ASSET.findall(c.last_user)
        if turn.called("CaseAssetLink") == 0:
            return [("CaseAssetLink", {"asset_id": ids[0]})]
        link = turn.results("CaseAssetLink")[0].split("\n")[0]
        ev = evidence_of(" ".join(turn.results("CaseAssetLink")))
        step = turn.called("CaseSay") + turn.called("CaseFinalize")
        if step == 0:
            return say(f"Here is your photo: {link}", "none", ev)
        if step == 1:
            return say(f"Your photo is at {assets.unsigned(link)}", "none", ev)
        if step == 2:  # not a claim of success: the platform sends its safe words in place of the answer
            tried[:] = turn.results("CaseSay")
            return [("CaseFinalize", {"answer": f"A person will look at {link}", "outcome": "needs_human", "cites": ev})]
        return "Said."

    with world(tmp_path, script, **LOCAL) as w:
        with_images(w.flow)
        asset = uploaded(w.flow, conv="CHAT-A")
        r, _ = w.flow.start(external_conversation_id="CHAT-A", message=image(asset["asset_id"], "my photo"))
        assert r.status_code == 200, r.text
        assert len(tried) == 2 and all("a link to an image" in t and "resident has seen nothing" in t for t in tried), tried
        out = public(w, r.json())
        [row] = rows(w.env)
        assert not LINK.search(out) and row["object_key"] not in out and "file:" not in out
        texts = [m[1] for m in w.messages(r.json()["workflow_id"]) if m[0] == "assistant"]
        assert all("file:" not in t and "photo" not in t and "look at" not in t for t in texts), texts


def test_only_an_image_sent_in_this_workflow_can_be_linked(tmp_path):
    answers: dict[str, str] = {}

    def script(c: Call):
        turn = c.after_user()
        said = c.last_user.split("</resident-message>")[0]  # the resident's own words: the ids to try, in order
        wanted = list(dict.fromkeys(ASSET.findall(said.split("LINK", 1)[1]))) if "LINK" in said else []
        if wanted and turn.called("CaseAssetLink") < len(wanted):
            return [("CaseAssetLink", {"asset_id": wanted[turn.called("CaseAssetLink")]})]
        for asset_id, text in zip(wanted, turn.results("CaseAssetLink")):
            answers[asset_id] = text
        return say("Noted.", "reply") if turn.called("CaseSay") == 0 else "Said."

    with world(tmp_path, script, **LOCAL) as w:
        with_images(w.flow)
        mine = uploaded(w.flow, conv="CHAT-A")
        other = uploaded(w.flow, conv="CHAT-B")  # the same resident, another conversation
        unsent = uploaded(w.flow, conv="CHAT-A")  # uploaded for this conversation, never sent in a message
        theirs = uploaded(w.flow, user="resident-999", conv="CHAT-Z")
        rb, _ = w.flow.start(external_conversation_id="CHAT-B", message=image(other["asset_id"], "B"))
        assert rb.status_code == 200
        unknown = "ast_" + "0" * 32
        ask = " ".join([other["asset_id"], unsent["asset_id"], theirs["asset_id"], unknown, "not-an-id"])
        ra, _ = w.flow.start(external_conversation_id="CHAT-A", message=image(mine["asset_id"], f"LINK {mine['asset_id']} {ask}"))
        assert ra.status_code == 200, ra.text
        assert LINK.search(answers[mine["asset_id"]])
        for asset_id in (other["asset_id"], unsent["asset_id"], theirs["asset_id"], unknown):
            assert answers[asset_id].startswith("No such image in this workflow"), answers
            assert not LINK.search(answers[asset_id])
        case = w.sql("select case_id from wf_workflows where id=?", (ra.json()["workflow_id"],))[0][0]
        made = [i.data["asset"] for i in w.run(lambda: w.rt.cases.items(case, kinds=("evidence",))) if i.data.get("tool") == "CaseAssetLink"]
        assert made == [mine["asset_id"]]


def test_a_consent_shows_that_a_photo_goes_along_and_no_address_and_the_partner_gets_the_link(tmp_path, partner):
    with world(tmp_path, pass_photo("partner_repair_consent"), **LOCAL, **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        with_images(w.flow)
        asset = uploaded(w.flow, conv="CHAT-A")
        r, body = w.flow.start(external_conversation_id="CHAT-A", message=image(asset["asset_id"], "Please send someone."))
        assert r.status_code == 200 and r.json()["workflow_state"] == "awaiting_approval", r.text
        started = r.json()
        [approval] = w.flow.approvals(started["conversation_id"])
        assert approval["summary"] == {"text": "Book a repair visit for mon", "tool": "partner_repair_consent",
                                       "arguments": {"slot": "mon", "note": "[image link]"}}
        [row] = rows(w.env)
        out = public(w, started)
        assert not LINK.search(out) and row["object_key"] not in out and "file:" not in out
        assert partner.of("book_repair") == []
        d = w.flow.decide(approval["approval_id"], w.flow.decide_body(body, started, approval))
        assert d.status_code == 202, d.text
        w.wait_state(started["workflow_id"], "waiting_external_event")
        [call] = partner.of("book_repair")
        assert assets.SIGNED.fullmatch(call["args"]["note"]) and row["object_key"] in call["args"]["note"]
        out = public(w, started)
        assert not LINK.search(out) and row["object_key"] not in out


def test_the_link_tool_is_the_leaders_and_needs_a_store():
    async def go():
        cases = SimpleNamespace(get_case=lambda case_id: _async({"status": "open"}))
        worker = CaseAssetLink(SimpleNamespace(cases=cases, assets=object()), Binding("c1", "s1", "a1", "tech", "worker", "u"))
        assert (await worker.call(asset_id="ast_" + "0" * 32)).content[0].text == "Only the leader can do this."
    asyncio.run(go())


async def _async(value):
    return value


def test_two_links_to_one_image_are_one_request_and_links_to_two_images_are_two():
    store = assets.S3Store("http://minio:9000", "b", "ak", "sk", clock=lambda: 1_800_000_000.0)
    a1, a2 = store.link("client_1/a.png", 900), store.link("client_1/a.png", 900, at=1_800_000_777.0)
    b1 = store.link("client_1/b.png", 900)
    assert a1 != a2
    assert ledger.hash_of({"note": a1, "slot": "mon"}) == ledger.hash_of({"note": a2, "slot": "mon"})
    assert ledger.hash_of({"note": a1, "slot": "mon"}) != ledger.hash_of({"note": b1, "slot": "mon"})
    assert ledger.hash_of({"photos": [a1], "slot": "mon"}) == ledger.hash_of({"photos": [a2], "slot": "mon"})
    assert ledger.hash_of({"slot": "mon"}) == ledger.hash_of({"slot": "mon"}) != ledger.hash_of({"slot": "tue"})


# ---- a real MinIO ---------------------------------------------------------------------------------------------------------
needs_minio = pytest.mark.skipif(not S3_ENDPOINT, reason="a real S3 needs AWP_TEST_S3_ENDPOINT (and AWP_TEST_S3_ACCESS_KEY, "
                                                         "AWP_TEST_S3_SECRET_KEY): a MinIO the tests may write to")


@needs_minio
def test_minio_an_image_goes_from_the_upload_to_the_partners_tool_and_is_gone_after_retention(tmp_path, partner):
    bucket = "awpt-" + secrets.token_hex(6)
    with world(tmp_path, pass_photo(), **minio_settings(bucket), **TOOLS, **SETTINGS) as w:
        configure(w, partner)
        with_images(w.flow)
        store = store_of(w.env)
        assert w.rt.assets_ready  # the bucket did not exist: the start made it
        data = PNG + secrets.token_bytes(50_000)
        asset = uploaded(w.flow, data, conv="CHAT-A")
        again = uploaded(w.flow, data, conv="CHAT-A", rid="up-again")  # another upload of the same bytes, never sent
        [row, spare] = rows(w.env)
        assert w.run(lambda: store.get(row["object_key"])) == data and w.run(lambda: store.head(spare["object_key"])) == len(data)
        r, start = w.flow.start(external_conversation_id="CHAT-A", message=image(asset["asset_id"], "Please send someone."))
        assert r.status_code == 200 and r.json()["workflow_state"] == "waiting_external_event", r.text
        started = r.json()
        [call] = partner.of("book_repair")
        link = call["args"]["note"]
        assert link.startswith(f"{S3_ENDPOINT}/{bucket}/{row['object_key']}?X-Amz-Algorithm=AWS4-HMAC-SHA256")
        got = httpx.get(link)  # as the partner's people would: the link and nothing else
        assert got.status_code == 200 and got.content == data and got.headers["content-type"] == "image/png"
        assert httpx.get(assets.unsigned(link)).status_code == 403
        out = public(w, started)
        assert "X-Amz" not in out and bucket not in out and row["object_key"] not in out
        # retention: nothing while the workflow is open, however old; both objects once it has been closed long enough
        year, t0, ctx = 365 * retention.DAY, started_at(w), w.env.app.state.wf
        assert w.run(lambda: retention.run(ctx, at=t0 + 10 * year))["assets"] == 0
        assert w.run(lambda: store.head(row["object_key"])) == len(data)
        wf = w.flow.snapshot(started["conversation_id"]).json()["workflows"][0]
        closed, _ = w.flow.close({"workflow_id": wf["workflow_id"], "workflow_revision": wf["revision"]}, start,
                                 reason="resident_requested_stop_tracking", stop_tracking_only=True)
        assert closed.status_code == 200, closed.text
        assert w.run(lambda: retention.run(ctx, at=t0 + 30 * retention.DAY))["assets"] == 0
        # closed for a year, but its operation is not over: the image that was sent stays; the one never sent goes
        assert w.run(lambda: retention.run(ctx, at=t0 + year))["assets"] == 1
        assert [r_["id"] for r_ in rows(w.env)] == [asset["asset_id"]] and again["asset_id"] == spare["id"]
        assert w.run(lambda: store.head(row["object_key"])) == len(data) and w.run(lambda: store.head(spare["object_key"])) is None
        w.sql("update wf_operations set status='completed'")
        assert w.run(lambda: retention.run(ctx, at=t0 + year))["assets"] == 1
        assert rows(w.env) == []
        assert w.run(lambda: store.head(row["object_key"])) is None
        assert httpx.get(link).status_code in (403, 404)
        assert (w.run(lambda: store._call("DELETE", None))).status_code == 204  # the bucket is empty: it can go


def started_at(w) -> float:
    return w.sql("select max(created_at) from wf_workflows")[0][0]
