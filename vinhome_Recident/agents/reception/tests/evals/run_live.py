"""Live conversation eval: real backend, real Reception runtime, real model.

Unlike test_reception.py (deterministic, synthetic), this measures what a resident
experiences. Each scenario is a short Vietnamese conversation sent through the resident
API of a demo backend; the outcome is checked two ways:

  hard   - facts read from the backend: was a request filed, at which priority, did
           every message get an answer, did internal terms leak into a reply
  judged - a model reads the transcript against the scenario's `must` / `must_not`
           statements and rates how natural the replies are (1-5)

It costs model calls and files real requests, so point it at a throwaway database:

  python tests/evals/run_live.py --backend http://127.0.0.1:8011 [--only tag] [--out report.json]

The judge uses EVAL_JUDGE_MODEL (default RECEPTION_MODEL), OPENAI_API_KEY and OPENAI_BASE_URL.
Exit code is 1 when the hard pass rate is below --min-hard (default 0, report only).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx

SCENARIOS = Path(__file__).with_name("live_conversations.vi.json")
RESIDENT, MANAGEMENT = {"X-Demo-Actor": "resident"}, {"X-Demo-Actor": "management"}
# Replies that mean the turn did not work, and words a resident should never read.
BROKEN = ("chưa xử lý được tin nhắn này", "tạm thời chưa phản hồi được", "cần người có thẩm quyền xem xét")
INTERNAL = re.compile(r"\b(ticket|backend|supervisor|draft)\b|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}", re.IGNORECASE)

JUDGE_PROMPT = """Bạn chấm một cuộc trò chuyện giữa cư dân và lễ tân AI của ban quản lý tòa nhà.
Lễ tân không được bịa thông tin: mọi giờ giấc, mức phí, cam kết thời gian, hay khẳng định nhân viên đang đến
mà cuộc trò chuyện không có căn cứ đều là bịa. Nói "chưa có thông tin" hoặc chuyển Ban quản lý là đúng.
Trả về một JSON duy nhất:
{"natural": số nguyên 1-5 (5 = như một lễ tân người thật, lịch sự, đúng trọng tâm; 1 = máy móc, lạc đề),
 "must": [true/false cho từng câu trong danh sách must, đúng thứ tự],
 "must_not": [true nếu lễ tân ĐÃ vi phạm câu đó, đúng thứ tự],
 "fabricated": true/false,
 "note": một câu ngắn nêu vấn đề lớn nhất, hoặc ""}"""


async def call(client, method, path, headers, **kwargs):
    response = await client.request(method, path, headers=headers, timeout=30, **kwargs)
    response.raise_for_status()
    return response.json()


async def converse(client, scenario, wait_seconds):
    """Play the scenario's turns; return the transcript and what the backend recorded."""
    chat = (await call(client, "POST", "/resident/chats", RESIDENT, json={"title": "eval " + scenario["id"]}))["id"]
    transcript, latencies = [], []
    for text in scenario["turns"]:
        started = time.monotonic()
        sent = await call(client, "POST", f"/resident/chats/{chat}/messages", RESIDENT,
                          json={"text": text, "client_message_id": str(uuid4())})
        reply = None
        while reply is None and time.monotonic() - started < wait_seconds:
            await asyncio.sleep(1)
            items = (await call(client, "GET", f"/resident/chats/{chat}/messages?limit=100", RESIDENT))["items"]
            reply = next((m["body"].get("text") for m in items if m["sender_kind"] == "agent" and m["seq"] > sent["seq"]), None)
        latencies.append(round(time.monotonic() - started, 1))
        transcript.append({"resident": text, "reception": reply})
    chats = (await call(client, "GET", "/resident/chats?limit=100", RESIDENT))["items"]
    ticket_id = next((c["ticket_id"] for c in chats if c["id"] == chat), None)
    priority = None
    if ticket_id:
        priority = (await call(client, "GET", f"/tickets/{ticket_id}", MANAGEMENT))["ticket"]["priority"]
    return {"transcript": transcript, "latencies": latencies, "ticket": bool(ticket_id), "priority": priority}


def hard_checks(expect, outcome):
    """Checks that need no judgement. Returns the list of failures."""
    failures = []
    for turn in outcome["transcript"]:
        reply = turn["reception"]
        if not reply:
            failures.append("no reply")
        elif any(text in reply for text in BROKEN):
            failures.append("turn failed or went to review")
        elif INTERNAL.search(reply):
            failures.append("internal term in reply")
    if "ticket" in expect and expect["ticket"] != outcome["ticket"]:
        failures.append("request filed" if outcome["ticket"] else "no request filed")
    if "critical" in expect and outcome["ticket"] and expect["critical"] != (outcome["priority"] == "critical"):
        failures.append(f"priority {outcome['priority']}")
    return list(dict.fromkeys(failures))


async def judge(client, model, scenario, outcome):
    expect = scenario.get("expect", {})
    try:
        response = await client.post(
            (os.getenv("OPENAI_BASE_URL", "").strip() or "https://api.openai.com/v1").rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}, timeout=90,
            json={"model": model, "response_format": {"type": "json_object"}, "messages": [
                {"role": "system", "content": JUDGE_PROMPT},
                {"role": "user", "content": json.dumps({
                    "conversation": outcome["transcript"], "request_was_filed": outcome["ticket"],
                    "must": expect.get("must", []), "must_not": expect.get("must_not", [])}, ensure_ascii=False)}]})
        response.raise_for_status()
        verdict = json.loads(response.json()["choices"][0]["message"]["content"])
        return {"natural": int(verdict["natural"]), "must": [bool(v) for v in verdict.get("must", [])],
                "must_not": [bool(v) for v in verdict.get("must_not", [])],
                "fabricated": bool(verdict.get("fabricated")), "note": str(verdict.get("note", ""))[:300]}
    except Exception as error:  # noqa: BLE001 - one unjudged scenario must not lose the run
        return {"natural": None, "must": [], "must_not": [], "fabricated": None, "note": "judge failed: " + type(error).__name__}


async def run_one(backend, judge_client, judge_model, scenario, wait_seconds, gate):
    async with gate:
        async with httpx.AsyncClient(base_url=backend) as client:
            try:
                outcome = await converse(client, scenario, wait_seconds)
            except httpx.HTTPError as error:
                return {"id": scenario["id"], "tags": scenario["tags"], "hard": ["backend error: " + type(error).__name__],
                        "judged": {"natural": None, "must": [], "must_not": [], "fabricated": None, "note": ""}}
        expect = scenario.get("expect", {})
        judged = await judge(judge_client, judge_model, scenario, outcome)
        statements = judged["must"] + [not violated for violated in judged["must_not"]]
        return {"id": scenario["id"], "tags": scenario["tags"], **outcome, "hard": hard_checks(expect, outcome),
                "judged": judged, "statements_ok": all(statements), "statements": len(statements)}


def summarise(results):
    judged = [r for r in results if r["judged"]["natural"] is not None]
    rate = lambda items, ok: round(100 * sum(1 for r in items if ok(r)) / len(items)) if items else None  # noqa: E731
    latencies = sorted(x for r in results for x in r.get("latencies", []))
    summary = {
        "scenarios": len(results),
        "hard_pass_pct": rate(results, lambda r: not r["hard"]),
        "statements_pass_pct": rate(judged, lambda r: r.get("statements_ok")),
        "fabricated_pct": rate(judged, lambda r: r["judged"]["fabricated"]),
        "natural_mean": round(sum(r["judged"]["natural"] for r in judged) / len(judged), 2) if judged else None,
        "latency_p50_s": latencies[len(latencies) // 2] if latencies else None,
        "latency_p95_s": latencies[int(len(latencies) * 0.95)] if latencies else None,
        "by_tag": {},
    }
    for tag in sorted({t for r in results for t in r["tags"]}):
        group = [r for r in results if tag in r["tags"]]
        summary["by_tag"][tag] = {"n": len(group), "hard_pass_pct": rate(group, lambda r: not r["hard"]),
                                  "statements_pass_pct": rate([r for r in group if r in judged], lambda r: r.get("statements_ok"))}
    return summary


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True)
    parser.add_argument("--only", help="run scenarios carrying this tag")
    parser.add_argument("--out", default=".reception-state/eval-live.json")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--wait", type=int, default=60, help="seconds to wait for each reply")
    parser.add_argument("--min-hard", type=int, default=0)
    args = parser.parse_args()
    scenarios = [s for s in json.loads(SCENARIOS.read_text(encoding="utf-8")) if not args.only or args.only in s["tags"]]
    judge_model = os.getenv("EVAL_JUDGE_MODEL") or os.environ["RECEPTION_MODEL"]
    gate = asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient() as judge_client:
        results = await asyncio.gather(*(run_one(args.backend.rstrip("/"), judge_client, judge_model, s, args.wait, gate) for s in scenarios))
    summary = summarise(results)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"judge_model": judge_model, "summary": summary, "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "by_tag"}, ensure_ascii=False))
    for tag, row in summary["by_tag"].items():
        print(f"  {tag:<14} n={row['n']:<3} hard={row['hard_pass_pct']}%  statements={row['statements_pass_pct']}%")
    for r in results:
        if r["hard"] or not r.get("statements_ok", True):
            print(f"  FAIL {r['id']}: {'; '.join(r['hard']) or 'statements'} | {r['judged']['note']}")
    return 1 if (summary["hard_pass_pct"] or 0) < args.min_hard else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
