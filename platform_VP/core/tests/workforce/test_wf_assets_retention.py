"""Retention of image assets (spec A3, contract 12): the images of workflows closed past the window leave the store and
the table; nothing of an open workflow ever does. The clock is in the test's hand, the store is a directory."""
from types import SimpleNamespace

import pytest
from sqlalchemy import insert

from awp.assets import LocalStore, StoreError, new_key
from awp.config import Settings
from awp.workforce import retention, tables as t
from awp.workforce.retention import DAY
from awp.workforce.tables import new_id
from dbkit import Lab

NOW = 1_800_000_000.0
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 30


@pytest.fixture
def lab(tmp_path):
    lab = Lab(tmp_path / "assets.db")
    lab.store = LocalStore(tmp_path / "store")
    yield lab
    lab.close()


def ctx(lab, store="lab", **settings):
    return SimpleNamespace(db=lab.db, settings=Settings(**settings), rt=SimpleNamespace(assets=lab.store if store == "lab" else store))


def asset(lab, seeded=None, days_old=0.0, conv="CHAT-X", client="cl_1") -> dict:
    """An image in the store and its row: sent in `seeded`'s conversation, or (None) uploaded for `conv` and never sent."""
    row = dict(id=new_id("ast"), client_id=client, external_user_id="resident-1",
               external_conversation_id=seeded["conv"]["external_conversation_id"] if seeded else conv,
               conversation_id=seeded["conv"]["id"] if seeded else None, object_key=new_key(client, "image/png"),
               content_type="image/png", size=len(PNG), sha256="0" * 64, created_at=NOW - days_old * DAY)

    async def go():
        await lab.store.put(row["object_key"], PNG, "image/png")
        async with lab.db.engine.begin() as conn:
            await conn.execute(insert(t.assets).values(**row))
    lab.run(go())
    return row


def left(lab) -> set:
    return {r["id"] for r in lab.rows(t.assets)}


def stored(lab, row) -> bool:
    return lab.run(lab.store.head(row["object_key"])) is not None


def purge(lab, days=90, at=NOW, store=None) -> int:
    return lab.run(retention.purge_assets(lab.db, store or lab.store, days, at=at))


def test_the_images_of_a_workflow_closed_past_the_window_leave_the_store_and_the_table(lab):
    old, fresh = lab.seed(state="closed", closed_at=NOW - 91 * DAY), lab.seed(state="closed", closed_at=NOW - 89 * DAY)
    gone = [asset(lab, old), asset(lab, old)]
    kept = asset(lab, fresh)
    assert purge(lab) == 2
    assert left(lab) == {kept["id"]} and stored(lab, kept) and not any(stored(lab, a) for a in gone)
    assert purge(lab) == 0  # again: nothing more


def test_the_boundary_of_the_window_is_exact(lab):
    edge = lab.seed(state="closed", closed_at=NOW - 90 * DAY)
    a = asset(lab, edge)
    assert purge(lab, at=NOW) == 0 and stored(lab, a)  # closed exactly 90 days ago: not yet past
    assert purge(lab, at=NOW + 1) == 1 and not stored(lab, a)


@pytest.mark.parametrize("state", ["active", "accepted", "awaiting_user", "awaiting_approval", "awaiting_confirmation",
                                   "waiting_external_event", "needs_attention", "blocked_authorization"])
def test_an_image_of_an_open_workflow_is_never_removed_however_old(lab, state):
    a = asset(lab, lab.seed(state=state), days_old=5000)
    assert purge(lab, at=NOW + 5000 * DAY) == 0
    assert left(lab) == {a["id"]} and stored(lab, a)


@pytest.mark.parametrize("status", ["intent", "sent", "pending", "unknown"])
def test_a_closed_workflow_with_an_operation_nobody_saw_the_end_of_keeps_its_images(lab, status):
    seeded = lab.seed(state="closed", closed_at=NOW - 400 * DAY)
    a = asset(lab, seeded)

    async def op():
        async with lab.db.engine.begin() as conn:
            await conn.execute(insert(t.operations).values(
                id="op_1", workflow_id=seeded["wf"]["id"], route_id="route_1", tool_name="book", args_hash="h",
                client_reference="cr_1", status=status, created_at=1.0, updated_at=1.0))
    lab.run(op())
    assert purge(lab) == 0 and stored(lab, a)
    lab.run(_set_operation(lab, "completed"))
    assert purge(lab) == 1 and not stored(lab, a)


async def _set_operation(lab, status):
    from sqlalchemy import update
    async with lab.db.engine.begin() as conn:
        await conn.execute(update(t.operations).values(status=status))


def test_an_image_that_was_never_sent_goes_after_the_window_unless_its_conversation_is_still_open(lab):
    orphan, young = asset(lab, None, days_old=91, conv="CHAT-NEVER"), asset(lab, None, days_old=89, conv="CHAT-NEVER")
    open_wf = lab.seed(state="awaiting_user")
    waiting = asset(lab, None, days_old=400, conv=open_wf["conv"]["external_conversation_id"])  # its chat is still going
    other_client = asset(lab, None, days_old=400, conv=open_wf["conv"]["external_conversation_id"], client="cl_2")
    closed = lab.seed(state="closed", closed_at=NOW - 1 * DAY)
    after = asset(lab, None, days_old=400, conv=closed["conv"]["external_conversation_id"])  # its chat ended: nobody will send it
    assert purge(lab) == 3
    assert left(lab) == {young["id"], waiting["id"]}
    assert stored(lab, young) and stored(lab, waiting) and not any(stored(lab, a) for a in (orphan, other_client, after))


def test_a_store_that_fails_keeps_the_row_and_the_next_run_finishes_the_job(lab):
    a = asset(lab, lab.seed(state="closed", closed_at=NOW - 200 * DAY))
    b = asset(lab, lab.seed(state="closed", closed_at=NOW - 200 * DAY))

    class Down:
        async def delete(self, key):
            if key == a["object_key"]:
                raise StoreError("the asset store did not answer (ConnectError)")
            await lab.store.delete(key)
    assert purge(lab, store=Down()) == 1  # the other one went; this one is as it was
    assert left(lab) == {a["id"]} and stored(lab, a) and not stored(lab, b)
    assert purge(lab) == 1 and left(lab) == set() and not stored(lab, a)


def test_an_object_that_is_already_gone_does_not_keep_its_row(lab):
    a = asset(lab, lab.seed(state="closed", closed_at=NOW - 200 * DAY))
    lab.run(lab.store.delete(a["object_key"]))
    assert purge(lab) == 1 and left(lab) == set()


def test_the_scheduled_run_removes_images_with_the_period_of_closed_workflows_and_zero_keeps_them(lab):
    a = asset(lab, lab.seed(state="closed", closed_at=NOW - 100 * DAY))
    off = lab.run(retention.run(ctx(lab, closed_retention_days=0), at=NOW))
    assert off["assets"] == 0 and stored(lab, a)
    longer = lab.run(retention.run(ctx(lab, closed_retention_days=120), at=NOW))
    assert longer["assets"] == 0 and stored(lab, a)
    on = lab.run(retention.run(ctx(lab), at=NOW))  # the default: 90 days
    assert on["assets"] == 1 and not stored(lab, a) and left(lab) == set()
    assert lab.run(retention.run(ctx(lab), at=NOW))["assets"] == 0


def test_without_a_store_retention_does_not_touch_the_asset_rows(lab):
    seeded = lab.seed(state="closed", closed_at=NOW - 100 * DAY)
    a = asset(lab, seeded)
    out = lab.run(retention.run(ctx(lab, store=None), at=NOW))
    assert "assets" not in out and left(lab) == {a["id"]}
    assert lab.run(retention.purge_assets(lab.db, None, 90, at=NOW)) == 0


def test_the_message_keeps_the_id_of_an_image_that_retention_removed(lab):
    """The audit trail (messages) is not retention's to remove: it still says that an image was sent, by its id."""
    seeded = lab.seed(state="closed", closed_at=NOW - 100 * DAY)
    a = asset(lab, seeded)

    async def message():
        async with lab.db.engine.begin() as conn:
            await conn.execute(insert(t.messages).values(
                id="msg_1", conversation_id=seeded["conv"]["id"], workflow_id=seeded["wf"]["id"], request_id=None, sender="user",
                text="see the photo", asset_ids=[a["id"]], sequence=1, created_at=NOW - 101 * DAY))
    lab.run(message())
    assert purge(lab) == 1
    assert lab.one(t.messages, id="msg_1")["asset_ids"] == [a["id"]]
