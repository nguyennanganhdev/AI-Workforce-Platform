"""Resident bytes traverse upload/finalize/request with real Domain DB and a strict offline Platform transport."""

import hashlib
import json
from uuid import UUID, uuid4

import httpx
from test_domain_database import operation
from test_platform_bridge import (
    FakePlatform,
    commands,
    hand_over,
    resident,
    retry_now,
    sync,
)
from test_platform_bridge import on as on  # noqa: PLC0414 -- pytest fixture export
from test_platform_bridge import turns as turns  # noqa: PLC0414 -- autouse fixture prevents live Reception calls
from test_resident_contract import CATEGORY, image, key, sql
from test_resident_contract import database as database  # noqa: PLC0414 -- pytest fixture export


def with_photo(c, count=1):
    place = operation(c, "get_verified_resident_context")[0]["residences"][0]
    channel = c.post("/resident/chats", json={"title": "Photo handoff"}).json()["id"]
    file_ids = []
    for _ in range(count):
        photo = c.post(
            f"/resident/chats/{channel}/photos?filename=private-name.png&mimeType=image/png",
            content=image(),
            headers=key(),
        )
        assert photo.status_code == 201, photo.text
        file_ids.append(photo.json()["id"])
    sent = c.post(
        f"/resident/chats/{channel}/messages",
        json={
            "text": "Light is broken",
            "client_message_id": str(uuid4()),
            "file_ids": file_ids,
        },
    )
    assert sent.status_code == 201, sent.text
    draft, _ = operation(
        c,
        "create_ticket_draft",
        {
            "channel_id": channel,
            "domain_id": place["domain_id"],
            "building_id": place["building_id"],
            "unit_id": place["unit_id"],
            "category_id": CATEGORY,
        },
    )
    target = {"channel_id": channel, "draft_id": draft["draftId"]}
    operation(
        c,
        "update_ticket_incident",
        {
            **target,
            "fields": {
                "source_message_id": sent.json()["id"],
                "facts": [
                    {
                        "key": "symptom",
                        "value": "is broken",
                        "source": "customer_report",
                        "source_message_id": sent.json()["id"],
                    },
                    {
                        "key": "item",
                        "value": "Light",
                        "source": "customer_report",
                        "source_message_id": sent.json()["id"],
                    },
                ],
            },
        },
    )
    operation(
        c,
        "submit_ticket_assessment",
        {
            **target,
            "assessment": {
                "priority": "normal",
                "severity": "minor",
                "reason": "Synthetic test",
            },
        },
    )
    handoff, _ = operation(c, "handoff_ticket", {**target, "plan_required": False})
    assert handoff["accepted"], handoff
    return channel, handoff["ticket"]["id"], file_ids[0]


def test_initial_and_image_only_followup_are_uploaded_before_their_requests(
    database, on
):
    fake = FakePlatform()
    with resident(database) as c:
        channel, ticket, file_id = with_photo(c)
        assert commands(database, ticket)[0]["body"]["file_ids"] == [file_id]
        sync(database, fake)
        requests = fake.posts("/partner/requests")
        assert requests, commands(database, ticket)[0]["last_error"]
        assert len(requests[0]["message"]["attachments"]) == 1
        asset = requests[0]["message"]["attachments"][0]["asset_id"]
        digest = sql(
            database,
            "select o.sha256 from files f join file_objects o on o.id=f.accepted_object_id where f.id=$1",
            UUID(file_id),
        )[0]["sha256"]
        assert hashlib.sha256(fake.uploaded[asset]).hexdigest() == digest
        assert fake.assets[asset]["filename"].startswith("resident-")
        assert "private-name" not in json.dumps(fake.assets)
        photo = c.post(
            f"/resident/chats/{channel}/photos?filename=second.png&mimeType=image/png",
            content=image(),
            headers=key(),
        )
        sent = c.post(
            f"/resident/chats/{channel}/messages",
            json={
                "text": "",
                "client_message_id": str(uuid4()),
                "file_ids": [photo.json()["id"]],
            },
        )
        assert sent.status_code == 201, sent.text
        sync(database, fake)
        requests = fake.posts("/partner/requests")
        assert len(requests) == 2 and len(fake.uploaded) == 2
        assert (
            requests[1]["message"]["attachments"]
            != requests[0]["message"]["attachments"]
        )
        assert "url" not in json.dumps([request["message"] for request in requests])
        assert (
            len(
                sql(
                    database,
                    "select * from platform_resident_assets where ticket_id=$1",
                    UUID(ticket),
                )
            )
            == 2
        )


def test_lost_request_reply_reuses_frozen_assets_and_does_not_upload_twice(
    database, on
):
    fake = FakePlatform()
    handle = fake.handle
    lose = True

    def transport(request):
        nonlocal lose
        answer = handle(request)
        if request.url.path.endswith("/partner/requests") and lose:
            lose = False
            raise httpx.ReadError("Synthetic lost acknowledgement", request=request)
        return answer

    fake.handle = transport
    with resident(database) as c:
        _, ticket, _ = with_photo(c)
        sync(database, fake)
        assert commands(database, ticket)[0]["status"] == "pending"
        assert commands(database, ticket)[0]["body"]["asset_attachments"]
        retry_now(database)
        sync(database, fake)
        requests = fake.posts("/partner/requests")
        assert len(requests) == 2 and requests[0] == requests[1]
        assert len(fake.assets) == len(fake.uploaded) == 1
        assert commands(database, ticket)[0]["status"] == "done"


def test_storage_failure_never_degrades_a_photo_request_to_text_only(database, on):
    fake = FakePlatform()
    handle = fake.handle
    failing = True

    def transport(request):
        if request.method == "PUT" and failing:
            return httpx.Response(503)
        return handle(request)

    fake.handle = transport
    with resident(database) as c:
        _, ticket, _ = with_photo(c)
        sync(database, fake)
        assert not fake.posts("/partner/requests")
        assert commands(database, ticket)[0]["status"] == "pending"
        failing = False
        retry_now(database)
        sync(database, fake)
        assert commands(database, ticket)[0]["status"] == "done"
        assert fake.posts("/partner/requests")[0]["message"]["attachments"]


def test_another_tickets_image_is_refused_before_any_upload(database, on):
    fake = FakePlatform()
    with resident(database) as c:
        _, first, file_id = with_photo(c)
        sql(
            database,
            "update platform_commands set status='failed' where ticket_id=$1",
            UUID(first),
        )
        _, second = hand_over(c)
        command = commands(database, second)[0]
        body = {**command["body"], "file_ids": [file_id]}
        sql(
            database,
            "update platform_commands set body=$2::jsonb where id=$1",
            command["id"],
            json.dumps(body),
        )
        sync(database, fake)
        assert not fake.assets and not fake.posts("/partner/requests")
        command = commands(database, second)[0]
        assert (
            command["status"] == "failed"
            and "DOMAIN_IMAGE_SCOPE_FORBIDDEN" in command["last_error"]
        )


def test_more_than_ten_initial_photos_are_split_without_losing_any(database, on):
    fake = FakePlatform()
    with resident(database) as c:
        _, ticket, _ = with_photo(c, count=11)
        queued = commands(database, ticket)
        assert [len(item["body"]["file_ids"]) for item in queued] == [10, 1]
        sync(database, fake)
        sync(database, fake)
        requests = fake.posts("/partner/requests")
        assert [len(item["message"]["attachments"]) for item in requests] == [10, 1]
        assert len(fake.uploaded) == 11
