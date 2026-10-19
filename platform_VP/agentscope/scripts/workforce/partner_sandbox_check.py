"""Partner-side contract check against a deployed platform (sandbox/UAT).

Plays the partner's role through the public ``/workforce/v1`` contract with a
real partner API key and records every request/response as evidence:

1. start a workflow (``start_workflow``) and read its result (bounded wait,
   then polling);
2. read the conversation snapshot and event history, open the SSE stream and
   resume it with ``Last-Event-ID`` (replay check);
3. send one ``workflow_reply`` if the Leader asked a question;
4. close the workflow when it reaches ``awaiting_confirmation``.

It writes ``.artifacts/partner-sandbox/<time>/evidence.json`` and
``EVIDENCE.md`` and prints one line to use as ``WORKFORCE_SANDBOX_EVIDENCE``
in CI. It never marks anything verified by itself: a person reviews the
evidence and decides. Uses real model tokens on the target platform.

Usage::

    python scripts/workforce/partner_sandbox_check.py \
        --base-url https://sandbox.example.com \
        --api-key "<partner key>" --management-ref tower-a \
        --external-user-id resident-sandbox-1 \
        --message "Căn hộ của tôi bị rò nước ở bồn rửa" \
        --reply "Căn S1-1205, tầng 12"
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx

TERMINAL = {"completed", "failed", "blocked"}

class Recorder:
    def __init__(self) -> None:
        self.steps: list[dict] = []

    def add(self, name: str, response: httpx.Response, ok: bool, note: str = "") -> dict:
        try:
            body = response.json()
        except ValueError:
            body = response.text[:2000]
        step = {
            "step": name,
            "method": response.request.method,
            "url": str(response.request.url),
            "status": response.status_code,
            "ok": ok,
            "note": note,
            "body": body,
            "at": datetime.now().isoformat(timespec="seconds"),
        }
        self.steps.append(step)
        print(f"{'OK ' if ok else 'ERR'} {name}: HTTP {response.status_code} {note}", flush=True)
        return step


async def wait_result(client, request_id, user, deadline) -> dict:
    while True:
        response = await client.get(
            f"/workforce/v1/partner/requests/{request_id}",
            params={"external_user_id": user},
        )
        body = response.json()
        done = response.status_code == 200 and body.get("request_status") in TERMINAL
        if done or response.status_code >= 400 or time.monotonic() > deadline:
            return {"response": response, "body": body}
        await asyncio.sleep(3)


async def read_sse(client, conversation_id, user, last_event_id=None, seconds=8) -> list[str]:
    ids: list[str] = []
    headers = {"Last-Event-ID": last_event_id} if last_event_id else {}
    try:
        async with asyncio.timeout(seconds):
            async with client.stream(
                "GET",
                f"/workforce/v1/partner/conversations/{conversation_id}/events",
                params={"external_user_id": user},
                headers=headers,
            ) as stream:
                async for line in stream.aiter_lines():
                    if line.startswith("id:"):
                        ids.append(line[3:].strip())
    except TimeoutError:
        pass
    return ids


async def run(args, transport: httpx.AsyncBaseTransport | None = None) -> int:
    if not getattr(args, "stop_tracking_only", False) and not getattr(args, "ticket_id", None):
        raise ValueError("Business acceptance requires --ticket-id from the isolated Domain fixture")
    recorder = Recorder()
    run_id = uuid.uuid4().hex[:8]
    headers = {"Authorization": f"ApiKey {args.api_key}"}
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"),
        headers=headers,
        timeout=60,
        transport=transport,
    ) as client:
        envelope = {
            "schema_version": "1",
            "command_type": "start_workflow",
            "external_request_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"sandbox/{run_id}/start")),
            "external_management_ref": args.management_ref,
            "external_user_id": args.external_user_id,
            "external_ticket_id": str(uuid.UUID(getattr(args, "ticket_id", None))) if getattr(args, "ticket_id", None) else str(uuid.uuid4()),
            "external_conversation_id": f"sandbox-chat-{run_id}",
            "message": {"type": "text", "text": args.message},
        }
        started = await client.post("/workforce/v1/partner/requests", json=envelope)
        recorder.add("start_workflow", started, started.status_code in (200, 202))
        if started.status_code not in (200, 202):
            return finish(recorder, args, run_id)
        first = started.json()
        result = await wait_result(client, first["request_id"], args.external_user_id, time.monotonic() + args.timeout)
        state = result["body"].get("workflow_state")
        recorder.add(
            "read_result",
            result["response"],
            result["body"].get("request_status") == "completed" and state not in {"needs_attention", "blocked", "failed"},
            f"state={state}",
        )

        retry = await client.post("/workforce/v1/partner/requests", json=envelope)
        recorder.add(
            "idempotent_retry",
            retry,
            retry.status_code in (200, 202) and retry.json().get("request_id") == first["request_id"],
            "same external_request_id must return the same request",
        )

        history = await client.get(
            f"/workforce/v1/partner/conversations/{first['conversation_id']}/event-history",
            params={"external_user_id": args.external_user_id},
        )
        recorder.add("event_history", history, history.status_code == 200)
        sse_ids = await read_sse(client, first["conversation_id"], args.external_user_id)
        replay_ids = (
            await read_sse(client, first["conversation_id"], args.external_user_id, sse_ids[0])
            if sse_ids
            else []
        )
        recorder.steps.append(
            {
                "step": "sse_replay",
                "ok": bool(sse_ids) and replay_ids == sse_ids[1:len(replay_ids) + 1],
                "note": f"stream ids={len(sse_ids)}, after Last-Event-ID={len(replay_ids)}",
                "at": datetime.now().isoformat(timespec="seconds"),
            },
        )

        revision = result["body"].get("workflow_revision")
        if state == "awaiting_user" and args.reply:
            reply_envelope = {
                **envelope,
                "command_type": "workflow_reply",
                "external_request_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"sandbox/{run_id}/reply")),
                "workflow_id": first["workflow_id"],
                "message": {"type": "text", "text": args.reply},
            }
            replied = await client.post("/workforce/v1/partner/requests", json=reply_envelope)
            recorder.add("workflow_reply", replied, replied.status_code in (200, 202))
            if replied.status_code in (200, 202):
                second = await wait_result(
                    client,
                    replied.json()["request_id"],
                    args.external_user_id,
                    time.monotonic() + args.timeout,
                )
                state = second["body"].get("workflow_state")
                revision = second["body"].get("workflow_revision")
                recorder.add(
                    "read_reply_result",
                    second["response"],
                    second["body"].get("request_status") == "completed",
                    f"state={state}",
                )

        closed_ok = False
        if state == "awaiting_confirmation" and revision:
            closed = await client.post(
                f"/workforce/v1/partner/workflows/{first['workflow_id']}/close",
                json={
                    "schema_version": "1",
                    "external_request_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"sandbox/{run_id}/close")),
                    "external_user_id": args.external_user_id,
                    "external_ticket_id": envelope["external_ticket_id"],
                    "external_conversation_id": envelope["external_conversation_id"],
                    "expected_revision": revision,
                    "reason": "resident_requested_stop_tracking" if getattr(args, "stop_tracking_only", False) else "resident_confirmed",
                    "stop_tracking_only": bool(getattr(args, "stop_tracking_only", False)),
                    **({"domain_acceptance": json.loads(Path(args.acceptance_json).read_text(encoding="utf-8"))}
                       if getattr(args, "acceptance_json", None) else {}),
                },
            )
            recorder.add("close_workflow", closed, closed.status_code == 200, closed.json().get("workflow_state", ""))
            closed_ok = closed.status_code == 200 and closed.json().get("workflow_state") == "closed"
        if not getattr(args, "stop_tracking_only", False):
            recorder.steps.append({"step": "business_completion", "ok": closed_ok,
                "note": "Requires terminal work and Domain resident acceptance; an unfinished state cannot be skipped."})
    return finish(recorder, args, run_id)


def finish(recorder: Recorder, args, run_id: str) -> int:
    out = Path(args.output) / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    data = {"base_url": args.base_url, "run_id": run_id,
            "mode": "transport_stop_tracking" if getattr(args, "stop_tracking_only", False) else "business_completion",
            "steps": recorder.steps}
    raw = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    (out / "evidence.json").write_text(raw, encoding="utf-8")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    passed = sum(1 for step in recorder.steps if step.get("ok"))
    lines = [
        f"# Partner sandbox evidence — {args.base_url}",
        "",
        f"Run `{run_id}` · {passed}/{len(recorder.steps)} steps OK · evidence sha256 `{digest}`",
        "",
        "| Step | OK | HTTP | Note |",
        "|---|---|---|---|",
        *[
            f"| {s['step']} | {'✅' if s.get('ok') else '❌'} | {s.get('status', '')} | {s.get('note', '')} |"
            for s in recorder.steps
        ],
        "",
        "Reviewed by: ______  Date: ______  Decision: VERIFIED / NOT_VERIFIED",
    ]
    (out / "EVIDENCE.md").write_text("\n".join(lines), encoding="utf-8")
    summary = (
        f"Sandbox {args.base_url} run {run_id}: {passed}/{len(recorder.steps)} steps OK, "
        f"evidence sha256 {digest} (pending human review)"
    )
    print(f"\nEvidence: {out}\nWORKFORCE_SANDBOX_EVIDENCE candidate: {summary}")
    return 0 if passed == len(recorder.steps) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Partner contract check against a deployed platform")
    parser.add_argument("--base-url", default=os.getenv("PARTNER_SANDBOX_BASE_URL"), required=os.getenv("PARTNER_SANDBOX_BASE_URL") is None)
    parser.add_argument("--api-key", default=os.getenv("PARTNER_SANDBOX_API_KEY"), required=os.getenv("PARTNER_SANDBOX_API_KEY") is None)
    parser.add_argument("--management-ref", default=os.getenv("PARTNER_SANDBOX_MANAGEMENT_REF", "tower-a"))
    parser.add_argument("--external-user-id", default=os.getenv("PARTNER_SANDBOX_USER", "resident-sandbox-1"))
    parser.add_argument("--ticket-id", help="Actual UUID from the isolated Domain fixture, required for business acceptance")
    parser.add_argument("--message", default="Căn hộ của tôi bị rò nước ở bồn rửa, xử lý giúp với.")
    parser.add_argument("--reply", default="Căn S1-1205, tầng 12.")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--output", default=".artifacts/partner-sandbox")
    parser.add_argument("--stop-tracking-only", action="store_true", help="Stop observation; does not certify business completion")
    parser.add_argument("--acceptance-json", help="DB-backed Domain resident acceptance for completion close")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
