"""Take an agent definition through the platform's own flow: draft, evaluation, admin review.

    python -m vinhomes.publish <definition.json> --room <management room> [--demo] [--approve]

1. Management creates the draft agent in its room and stores the configuration.
2. Every evaluation case runs on OpenBot exactly as a room turn runs (same instructions, same
   reply format, same tool descriptions) and is judged by the case's `must` / `must_not` patterns
   and, for an agent with tools, `must_call` / `must_not_call`. A tool the agent calls is answered
   from the case's `tool_results`, so a case states what the tool said and what the agent must
   then say.
3. Only when all cases pass is the record submitted for admin review.
4. With --approve the admin decision is recorded too, which publishes the version.

The definition names the instructions file and the cases; see docs/teams/quang/agent/.
Settings: COORDINATION_BACKEND_URL, COORDINATION_OPENBOT_URL, MANAGED_AGENT_TOKEN, and either
--demo (the backend's demo actors) or PUBLISH_MANAGEMENT_EMAIL/_PASSWORD and, for --approve,
PUBLISH_ADMIN_EMAIL/_PASSWORD. A definition with `tools` also needs COORDINATION_TOOLS_URL and
COORDINATION_TOOLS_TOKEN, to read the tools' descriptions from the tool host.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import ValidationError

from adapters.backend.errors import AdapterError
from adapters.openbot import RunStream, SSEDecoder
from groupchat.models import AgentOutput

from .ports import InstructedClient

EVALUATOR = "vinhomes.publish: must/must_not patterns over the room reply, must_call over the tools used"
TOOL_SERVER = "technical-tools"
TOOL_ROUNDS = 6  # an agent that is still calling tools after this many rounds has not answered


def dotted(name: str) -> str:
    """A tool's catalogue name from the name a model calls it by."""
    return name.replace("__", ".")


async def answer(client: httpx.AsyncClient, instructions: str, case: dict, tools: list[dict],
                 defaults: dict, *, endpoint: str | None = None, token: str | None = None,
                 invoke_tool=None) -> tuple[str, list[str]]:
    """One room turn for an evaluation case: the agent's `content` and the tools it called."""
    thread = f"evaluation:{case['name']}"
    # `messages` is what the room already holds for the agent: empty for a first task, the agent's
    # earlier answer for a follow-up question.
    asked = {"instruction": case["instruction"], "tasks": [], "messages": case.get("messages", []),
             "context": [{"item_id": "reception-v2-ticket", "content": json.dumps(case["ticket"], ensure_ascii=False)}]}
    messages = [{"id": "context", "role": "user", "content": json.dumps(asked, ensure_ascii=False)}]
    headers = {"x-openbot-agent-token": token or os.environ["MANAGED_AGENT_TOKEN"], "Accept": "text/event-stream"}
    # The same client the room's adapter sends through: same instructions, same reply handling.
    room, called = InstructedClient(client, {thread: instructions}), []
    for _ in range(TOOL_ROUNDS):
        run = str(uuid4())
        wire = {"threadId": thread, "runId": run, "state": {}, "tools": tools, "forwardedProps": {}, "context": [],
                "messages": messages}
        stream, decoder = RunStream(thread, run), SSEDecoder()
        async with room.stream("POST", endpoint or os.environ["COORDINATION_OPENBOT_URL"], headers=headers, json=wire) as response:
            if response.status_code != 200:
                raise AdapterError(f"openbot_status_{response.status_code}")
            async for chunk in response.aiter_bytes():
                for event in decoder.feed(chunk):
                    stream.consume(event)
            for event in decoder.feed(b"", final=True):
                stream.consume(event)
        said = "".join(m["content"] for m in stream.messages.values())
        if not stream.calls:
            return AgentOutput.model_validate_json(said).content, called
        messages.append({"id": f"assistant-{run}", "role": "assistant", "content": said, "toolCalls": [
            {"id": call_id, "type": "function", "function": {"name": call["name"], "arguments": call["args"]}}
            for call_id, call in stream.calls.items()]})
        for call_id, call in stream.calls.items():
            name = dotted(call["name"])
            if call['name'] not in {t['name'] for t in tools}:
                raise AdapterError('tool_not_granted')
            called.append(name)
            # What the tool says in this case; a tool the case is silent about answers the
            # definition's default for it (found nothing).
            result = (await invoke_tool(name, json.loads(call['args'])) if invoke_tool else
                      case.get("tool_results", {}).get(name) or defaults.get(name, {"status": "OK", "data": {}, "errors": []}))
            messages.append({"id": f"result-{call_id}", "role": "tool", "toolCallId": call_id,
                             "content": json.dumps({"tool": call["name"], "result": result}, ensure_ascii=False)})
    raise AdapterError("continuation_limit")


def judge(case: dict, content: str, called: list[str]) -> list[str]:
    """Why the reply fails this case; empty when it passes."""
    missing = [p for p in case.get("must", []) if not re.search(p, content, re.IGNORECASE)]
    forbidden = [p for p in case.get("must_not", []) if re.search(p, content, re.IGNORECASE)]
    uncalled = [t for t in case.get("must_call", []) if t not in called]
    miscalled = [t for t in case.get("must_not_call", []) if t in called]
    return ([f"thiếu: {p}" for p in missing] + [f"có nội dung bị cấm: {p}" for p in forbidden]
            + [f"không gọi tool: {t}" for t in uncalled] + [f"gọi tool không được gọi: {t}" for t in miscalled])


async def evaluate(client: httpx.AsyncClient, instructions: str, cases: list[dict], tools: list[dict],
                   defaults: dict) -> list[dict]:
    records = []
    for case in cases:
        called: list[str] = []
        try:
            content, called = await answer(client, instructions, case, tools, defaults)
            problems = judge(case, content, called)
        except (AdapterError, ValidationError, httpx.HTTPError) as error:
            reason = getattr(error, "code", None) or type(error).__name__
            content, problems = f"(không có câu trả lời hợp lệ: {reason})", [f"lượt chạy thất bại: {reason}"]
        used = f"  [tool: {', '.join(called)}]" if called else ""
        print(f"  {'PASS' if not problems else 'FAIL'}  {case['name']}{used}" + ("" if not problems else "  " + "; ".join(problems)))
        if problems:
            # What the agent actually said, so the author can tell a wrong answer from a strict pattern.
            print("\n".join("        | " + line for line in content[:1200].splitlines()))
        records.append({"name": case["name"], "expected": case["expected"], "actual": content[:5000],
                        "input": json.dumps({"instruction": case["instruction"], "ticket": case["ticket"],
                                             **({"tool_results": case["tool_results"]} if case.get("tool_results") else {})},
                                            ensure_ascii=False)[:5000],
                        "passed": not problems,
                        "explanation": ("Khớp mọi mẫu bắt buộc, không có nội dung bị cấm."
                                        + (f" Tool đã gọi: {', '.join(called)}." if called else "")
                                        if not problems else "; ".join(problems))[:2000]})
    return records


async def tool_descriptions(client: httpx.AsyncClient, names: list[str]) -> list[dict]:
    """The granted tools as the tool host describes them: what a room turn offers the model."""
    if not names:
        return []
    response = await client.get(os.environ["COORDINATION_TOOLS_URL"].rstrip("/") + "/tools",
                                headers={"Authorization": "Bearer " + os.environ["COORDINATION_TOOLS_TOKEN"]})
    known = {tool["name"]: tool for tool in must(response, "Reading the tool catalogue")["tools"]}
    unknown = [name for name in names if name not in known or known[name]["side_effect"] != "read"]
    if unknown:
        raise SystemExit(f"Not a read tool of the tool host: {', '.join(unknown)}")
    return [{"name": known[name]["model_name"], "description": known[name]["description"],
             "parameters": known[name]["input_schema"]} for name in names]


@asynccontextmanager
async def signed_in(backend: str, role: str, demo: bool):
    """An HTTP client acting as this role: a demo actor, or a signed-in account."""
    async with httpx.AsyncClient(base_url=backend, headers={"X-Demo-Actor": role} if demo else {}, timeout=30) as client:
        if not demo:
            prefix = f"PUBLISH_{role.upper()}_"
            response = await client.post("/auth/login", json={"identifier": os.environ[prefix + "EMAIL"],
                                                              "password": os.environ[prefix + "PASSWORD"]})
            if response.status_code != 200:
                raise SystemExit(f"Sign-in as {role} failed ({response.status_code})")
        yield client


def must(response: httpx.Response, step: str) -> dict:
    if response.status_code >= 400:
        raise SystemExit(f"{step} was refused ({response.status_code}): {response.text[:300]}")
    return response.json()


async def main() -> int:
    parser = argparse.ArgumentParser(description="Draft, evaluate and submit an agent for admin review")
    parser.add_argument("definition", type=Path)
    parser.add_argument("--room", help="the management room that owns the agent")
    parser.add_argument("--demo", action="store_true", help="the backend runs with demo actors")
    parser.add_argument("--approve", action="store_true", help="also record the admin's approval")
    parser.add_argument("--check", action="store_true", help="only run the evaluation; nothing is stored")
    args = parser.parse_args()
    definition = json.loads(args.definition.read_text(encoding="utf-8"))
    instructions = (args.definition.parent / definition["instructions_file"]).read_text(encoding="utf-8").strip()
    if args.check:
        async with httpx.AsyncClient(timeout=120) as bot:
            cases = await evaluate(bot, instructions, definition["cases"],
                                   await tool_descriptions(bot, definition.get("tools", [])),
                                   definition.get("tool_defaults", {}))
        print(f"{sum(c['passed'] for c in cases)}/{len(cases)} cases passed")
        return 0 if all(c["passed"] for c in cases) else 1
    if not args.room:
        parser.error("--room is required unless --check is given")
    backend = os.environ["COORDINATION_BACKEND_URL"]
    # A changed definition is a new draft: an approved agent's configuration is immutable.
    key = hashlib.sha256(json.dumps([definition, instructions], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    base = f"/rooms/{args.room}/agents"
    async with signed_in(backend, "management", args.demo) as management:
        granted = definition.get("tools", [])
        configuration = {"instructions": instructions, "description": definition["description"],
                         "service_categories": definition["service_categories"],
                         "mcp_tools": [{"server_id": TOOL_SERVER, "name": name} for name in granted]}
        # A draft of this name is continued: an earlier run may have stopped at a failed case.
        # Only a draft accepts a configuration, so the first one that does is the draft.
        agent = configured = None
        namesakes = [a for a in must(await management.get(base), "Reading the room's agents")["items"]
                     if a["name"] == definition["name"]]
        for known in namesakes:
            if agent is None:
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
            cases = await evaluate(bot, instructions, definition["cases"], await tool_descriptions(bot, granted),
                                   definition.get("tool_defaults", {}))
        if not all(c["passed"] for c in cases):
            print("not submitted: every case must pass")
            return 1
        review = must(await management.post(f"{base}/{agent['id']}/review-submissions", json={
            "configuration_hash": configured["configurationHash"], "evaluator": EVALUATOR, "round": 1,
            "cases": cases}), "Submitting for review")
        print(f"review {review['id']} is pending an admin decision")
    if not args.approve:
        return 0
    async with signed_in(backend, "admin", args.demo) as admin:
        decided = must(await admin.post(f"/admin/agent-reviews/{review['id']}/decision", json={
            "decision": "approve", "version": review["version"],
            "note": f"Đạt {len(cases)}/{len(cases)} ca đánh giá."}), "Recording the decision")
        print(f"approved and published: version {decided['versionId']}")
        # The room keeps one published agent of this name: the one just approved.
        for earlier in namesakes:
            if earlier["id"] != agent["id"]:
                revoked = await admin.post(f"/admin/agents/{earlier['id']}/release/revoke",
                                           json={"note": f"Thay bằng phiên bản {decided['versionId']}"})
                if revoked.status_code == 200:
                    print(f"revoked the earlier published agent {earlier['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
