"""Take an agent definition through the platform's own flow: draft, evaluation, admin review.

    python -m vinhomes.publish <definition.json> --room <management room> [--demo] [--approve]

1. Management creates the draft agent in its room and stores the configuration.
2. Every evaluation case runs on OpenBot exactly as a room turn runs (same instructions, same
   reply format) and is judged by the case's `must` / `must_not` patterns.
3. Only when all cases pass is the record submitted for admin review.
4. With --approve the admin decision is recorded too, which publishes the version.

The definition names the instructions file and the cases; see docs/teams/quang/agent/.
Settings: COORDINATION_BACKEND_URL, COORDINATION_OPENBOT_URL, MANAGED_AGENT_TOKEN, and either
--demo (the backend's demo actors) or PUBLISH_MANAGEMENT_EMAIL/_PASSWORD and, for --approve,
PUBLISH_ADMIN_EMAIL/_PASSWORD.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import ValidationError

from adapters.backend.errors import AdapterError
from adapters.openbot import RunStream, SSEDecoder
from groupchat.models import AgentOutput

from .ports import InstructedClient

EVALUATOR = "vinhomes.publish: must/must_not patterns over the room reply"


async def answer(client: httpx.AsyncClient, instructions: str, case: dict) -> str:
    """One room turn for an evaluation case: what the agent's `content` is, or why there is none."""
    thread, run = f"evaluation:{case['name']}", str(uuid4())
    asked = {"instruction": case["instruction"], "tasks": [], "messages": [],
             "context": [{"item_id": "reception-v2-ticket", "content": json.dumps(case["ticket"], ensure_ascii=False)}]}
    wire = {"threadId": thread, "runId": run, "state": {}, "tools": [], "forwardedProps": {}, "context": [],
            "messages": [{"id": "context", "role": "user", "content": json.dumps(asked, ensure_ascii=False)}]}
    stream, decoder = RunStream(thread, run), SSEDecoder()
    headers = {"x-openbot-agent-token": os.environ["MANAGED_AGENT_TOKEN"], "Accept": "text/event-stream"}
    # The same client the room's adapter sends through: same instructions, same reply handling.
    room = InstructedClient(client, {thread: instructions})
    async with room.stream("POST", os.environ["COORDINATION_OPENBOT_URL"], headers=headers, json=wire) as response:
        if response.status_code != 200:
            raise AdapterError(f"openbot_status_{response.status_code}")
        async for chunk in response.aiter_bytes():
            for event in decoder.feed(chunk):
                stream.consume(event)
        for event in decoder.feed(b"", final=True):
            stream.consume(event)
    return AgentOutput.model_validate_json("".join(m["content"] for m in stream.messages.values())).content


def judge(case: dict, content: str) -> list[str]:
    """Why the reply fails this case; empty when it passes."""
    missing = [p for p in case.get("must", []) if not re.search(p, content, re.IGNORECASE)]
    forbidden = [p for p in case.get("must_not", []) if re.search(p, content, re.IGNORECASE)]
    return [f"thiếu: {p}" for p in missing] + [f"có nội dung bị cấm: {p}" for p in forbidden]


async def evaluate(client: httpx.AsyncClient, instructions: str, cases: list[dict]) -> list[dict]:
    records = []
    for case in cases:
        try:
            content = await answer(client, instructions, case)
            problems = judge(case, content)
        except (AdapterError, ValidationError, httpx.HTTPError) as error:
            reason = getattr(error, "code", None) or type(error).__name__
            content, problems = f"(không có câu trả lời hợp lệ: {reason})", [f"lượt chạy thất bại: {reason}"]
        print(f"  {'PASS' if not problems else 'FAIL'}  {case['name']}" + ("" if not problems else "  " + "; ".join(problems)))
        records.append({"name": case["name"], "expected": case["expected"], "actual": content[:5000],
                        "input": json.dumps({"instruction": case["instruction"], "ticket": case["ticket"]},
                                            ensure_ascii=False)[:5000],
                        "passed": not problems,
                        "explanation": "Khớp mọi mẫu bắt buộc, không có nội dung bị cấm." if not problems else "; ".join(problems)})
    return records


async def signed_in(backend: str, role: str, demo: bool) -> httpx.AsyncClient:
    if demo:
        return httpx.AsyncClient(base_url=backend, headers={"X-Demo-Actor": role}, timeout=30)
    client = httpx.AsyncClient(base_url=backend, timeout=30)
    prefix = f"PUBLISH_{role.upper()}_"
    response = await client.post("/auth/login", json={"email": os.environ[prefix + "EMAIL"],
                                                      "password": os.environ[prefix + "PASSWORD"]})
    if response.status_code != 200:
        raise SystemExit(f"Sign-in as {role} failed ({response.status_code})")
    return client


def must(response: httpx.Response, step: str) -> dict:
    if response.status_code >= 400:
        raise SystemExit(f"{step} was refused ({response.status_code}): {response.text[:300]}")
    return response.json()


async def main() -> int:
    parser = argparse.ArgumentParser(description="Draft, evaluate and submit an agent for admin review")
    parser.add_argument("definition", type=Path)
    parser.add_argument("--room", required=True, help="the management room that owns the agent")
    parser.add_argument("--demo", action="store_true", help="the backend runs with demo actors")
    parser.add_argument("--approve", action="store_true", help="also record the admin's approval")
    args = parser.parse_args()
    definition = json.loads(args.definition.read_text(encoding="utf-8"))
    instructions = (args.definition.parent / definition["instructions_file"]).read_text(encoding="utf-8").strip()
    backend = os.environ["COORDINATION_BACKEND_URL"]
    # A changed definition is a new draft: an approved agent's configuration is immutable.
    key = hashlib.sha256(json.dumps([definition, instructions], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    base = f"/rooms/{args.room}/agents"
    async with await signed_in(backend, "management", args.demo) as management:
        configuration = {"instructions": instructions, "description": definition["description"],
                         "service_categories": definition["service_categories"]}
        # A draft of this name is continued: an earlier run may have stopped at a failed case.
        # Only a draft accepts a configuration, so the first one that does is the draft.
        agent = configured = None
        for known in must(await management.get(base), "Reading the room's agents")["items"]:
            if known["name"] == definition["name"] and agent is None:
                stored = await management.put(f"{base}/{known['id']}/configuration", json=configuration)
                if stored.status_code == 200:
                    agent, configured = known, stored.json()
        if agent is None:
            created = await management.post(base, json={
                "name": definition["name"], "purpose": definition["purpose"], "instructions": instructions[:5000],
                "idempotency_key": f"{definition['name']}:{key}"})
            if created.status_code == 409:
                print("an agent from this exact definition exists and is no longer a draft; change the definition to publish a new one")
                return 0
            agent = must(created, "Creating the draft")
            configured = must(await management.put(f"{base}/{agent['id']}/configuration", json=configuration),
                              "Storing the configuration")
        print(f"draft agent {agent['id']}")
        print(f"evaluating {len(definition['cases'])} cases on {os.environ['COORDINATION_OPENBOT_URL']}")
        async with httpx.AsyncClient(timeout=120) as bot:
            cases = await evaluate(bot, instructions, definition["cases"])
        if not all(c["passed"] for c in cases):
            print("not submitted: every case must pass")
            return 1
        review = must(await management.post(f"{base}/{agent['id']}/review-submissions", json={
            "configuration_hash": configured["configurationHash"], "evaluator": EVALUATOR, "round": 1,
            "cases": cases}), "Submitting for review")
        print(f"review {review['id']} is pending an admin decision")
    if not args.approve:
        return 0
    async with await signed_in(backend, "admin", args.demo) as admin:
        decided = must(await admin.post(f"/admin/agent-reviews/{review['id']}/decision", json={
            "decision": "approve", "version": review["version"],
            "note": f"Đạt {len(cases)}/{len(cases)} ca đánh giá."}), "Recording the decision")
        print(f"approved and published: version {decided['versionId']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
