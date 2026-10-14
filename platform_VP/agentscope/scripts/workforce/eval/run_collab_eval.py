"""Run collaboration scenarios against a running Workforce platform.

This script drives the real platform over HTTP (the same API the web UI
uses): it opens a fresh Leader ticket per scenario, sends each customer turn,
waits until the team is idle, reads the Leader's answer and the ticket's
measured metrics, then scores the run. It spends real model tokens, so it is
started by a person, never by CI.

Usage (from ``platform_VP/agentscope``)::

    python scripts/workforce/eval/run_collab_eval.py \
        --base-url http://127.0.0.1:8000 \
        --identity manager@example.com --password '...' --tenant default

    # Only some scenarios, with an LLM judge (OpenAI-compatible):
    EVAL_JUDGE_MODEL=gpt-5.4 python scripts/workforce/eval/run_collab_eval.py \
        ... --only travel-full-brief resident-pipe-burst --judge

    # Compare two runs (before/after a change):
    python scripts/workforce/eval/run_collab_eval.py \
        --compare .artifacts/collab-eval/A/results.json .artifacts/collab-eval/B/results.json

Without auth (legacy demo mode) pass ``--user-id <id>`` instead of a login.
Results go to ``.artifacts/collab-eval/<timestamp>/`` (``results.json`` and
``REPORT.md``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scoring import (
    CheckResult,
    ScenarioVerdict,
    check_answer,
    check_metrics,
    summarize,
)

HERE = Path(__file__).resolve().parent
DEFAULT_SCENARIOS = HERE / "scenarios.json"


class Platform:
    """Minimal HTTP client for the Workforce console and chat API."""

    def __init__(self, base_url: str, *, user_id: str | None, timeout: float) -> None:
        headers = {"X-User-ID": user_id} if user_id else {}
        self.http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout,
        )
        self._login: dict | None = None

    async def login(self, tenant: str, identity: str, password: str) -> None:
        self._login = {"tenant_id": tenant, "identity": identity, "password": password}
        response = await self.http.post("/auth/login", json=self._login)
        response.raise_for_status()
        self.http.headers["Authorization"] = "Bearer " + response.json()["access_token"]

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        response = await self.http.request(method, url, **kwargs)
        if response.status_code == 401 and self._login is not None:
            refreshed = await self.http.post("/auth/refresh")
            if refreshed.status_code == 200:
                self.http.headers["Authorization"] = (
                    "Bearer " + refreshed.json()["access_token"]
                )
            else:
                await self.login(**self._login)
            response = await self.http.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    async def new_ticket(self) -> dict:
        return (await self._request("POST", "/workforce/console/leader/tickets")).json()

    async def send(self, agent_id: str, session_id: str, text: str) -> str:
        from agentscope.message import TextBlock, UserMsg

        message = UserMsg(name="user", content=[TextBlock(text=text)])
        await self._request(
            "POST",
            "/chat/",
            json={
                "agent_id": agent_id,
                "session_id": session_id,
                "input": message.model_dump(mode="json"),
            },
        )
        return message.id

    async def wait_idle(self, session_id: str, *, timeout: float) -> bool:
        """Wait until the Leader session has been idle for two polls."""

        deadline = time.monotonic() + timeout
        idle_polls = 0
        await asyncio.sleep(2)
        while time.monotonic() < deadline:
            status = (
                await self._request("GET", f"/sessions/{session_id}/status")
            ).json()["status"]
            idle_polls = idle_polls + 1 if status != "running" else 0
            if idle_polls >= 2:
                return True
            await asyncio.sleep(2)
        return False

    async def answer_after(self, session_id: str, user_message_id: str) -> str:
        messages = (
            await self._request(
                "GET",
                f"/sessions/{session_id}/messages",
                params={"limit": 100},
            )
        ).json()["messages"]
        ids = [m.get("id") for m in messages]
        start = ids.index(user_message_id) + 1 if user_message_id in ids else 0
        texts: list[str] = []
        for message in messages[start:]:
            if message.get("role") != "assistant":
                continue
            content = message.get("content")
            if isinstance(content, str):
                texts.append(content)
                continue
            for block in content or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
        return "\n".join(t for t in texts if t).strip()

    async def metrics(self, session_id: str) -> dict:
        return (
            await self._request("GET", f"/workforce/console/tickets/{session_id}/metrics")
        ).json()


async def judge(rubric: str, transcript: list[dict]) -> dict:
    """Optional rubric score from an OpenAI-compatible model (0–5)."""

    from openai import AsyncOpenAI

    model = os.environ["EVAL_JUDGE_MODEL"]
    client = AsyncOpenAI(
        api_key=os.getenv("EVAL_JUDGE_API_KEY") or os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("EVAL_JUDGE_BASE_URL") or os.getenv("OPENAI_BASE_URL") or None,
    )
    conversation = "\n\n".join(
        f"KHÁCH: {turn['user']}\nLEADER: {turn['answer']}" for turn in transcript
    )
    response = await client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Bạn chấm một hội thoại của hệ thống multi-agent theo tiêu chí cho trước. "
                    "Chỉ dựa vào tiêu chí và hội thoại. Trả JSON: "
                    '{"score": 0-5, "pass": true|false, "reason": "<= 3 câu tiếng Việt"}. '
                    "pass=true khi score >= 4."
                ),
            },
            {"role": "user", "content": f"TIÊU CHÍ:\n{rubric}\n\nHỘI THOẠI:\n{conversation}"},
        ],
    )
    try:
        return json.loads(response.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return {"score": 0, "pass": False, "reason": "judge returned invalid JSON"}


async def run_scenario(platform: Platform, scenario: dict, args) -> dict:
    started = time.monotonic()
    ticket = await platform.new_ticket()
    session_id, agent_id = ticket["session_id"], ticket["agent_id"]
    verdict = ScenarioVerdict(scenario["id"])
    transcript: list[dict] = []
    for index, turn in enumerate(scenario["turns"], start=1):
        message_id = await platform.send(agent_id, session_id, turn["user"])
        idle = await platform.wait_idle(session_id, timeout=args.turn_timeout)
        answer = await platform.answer_after(session_id, message_id)
        transcript.append({"user": turn["user"], "answer": answer, "idle": idle})
        verdict.checks.append(
            CheckResult(f"lượt {index}: xong trong {args.turn_timeout:.0f}s", idle)
        )
        for check in check_answer(answer, turn.get("checks", {})):
            check.name = f"lượt {index}: {check.name}"
            verdict.checks.append(check)
    metrics = await platform.metrics(session_id)
    verdict.checks.extend(check_metrics(metrics, scenario.get("metric_checks", {})))
    judged = None
    if args.judge and scenario.get("judge_rubric"):
        judged = await judge(scenario["judge_rubric"], transcript)
    return {
        "id": scenario["id"],
        "title": scenario["title"],
        "domain": scenario["domain"],
        "session_id": session_id,
        "passed": verdict.passed and (judged is None or bool(judged.get("pass"))),
        "check_score": verdict.score,
        "checks": [check.__dict__ for check in verdict.checks],
        "judge": judged,
        "summary": summarize(metrics),
        "seconds": round(time.monotonic() - started, 1),
        "transcript": transcript,
        "metrics": metrics,
    }


def render_report(results: dict) -> str:
    rows = results["scenarios"]
    passed = sum(r["passed"] for r in rows)
    lines = [
        f"# Kết quả đánh giá phối hợp — {results['started_at']}",
        "",
        f"Nền tảng: `{results['base_url']}` · Kịch bản: {len(rows)} · **Đạt: {passed}/{len(rows)}**",
        "",
        "| Kịch bản | Đạt | Điểm check | Judge | Agent | Trao đổi | Bị chặn bằng chứng | Nhánh bị dừng | Token vào | Token cache | % cache | Token ra | Giây |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        s = r["summary"]
        judge_score = r["judge"]["score"] if r.get("judge") else "—"
        lines.append(
            f"| {r['id']} | {'✅' if r['passed'] else '❌'} | {r['check_score']:.2f} | {judge_score} | "
            f"{s['agents']} | {s['exchanges']} | {s['evidence_rejections']} | {s['stopped_branches']} | "
            f"{s['input_tokens']:,} | {s['cached_input_tokens']:,} | {s['cache_hit_ratio']:.0%} | "
            f"{s['output_tokens']:,} | {r['seconds']} |"
        )
    totals = {
        key: sum(r["summary"][key] for r in rows)
        for key in ("input_tokens", "cached_input_tokens", "output_tokens")
    }
    ratio = totals["cached_input_tokens"] / totals["input_tokens"] if totals["input_tokens"] else 0
    lines += [
        "",
        f"Tổng token vào {totals['input_tokens']:,} (cache {ratio:.0%}), ra {totals['output_tokens']:,}.",
        "",
    ]
    for r in rows:
        lines += [f"## {r['id']} — {r['title']}", ""]
        for check in r["checks"]:
            mark = "✅" if check["passed"] else "❌"
            detail = f" ({check['detail']})" if check.get("detail") else ""
            lines.append(f"- {mark} {check['name']}{detail}")
        if r.get("judge"):
            lines.append(f"- Judge: {r['judge'].get('score')}/5 — {r['judge'].get('reason', '')}")
        for index, turn in enumerate(r["transcript"], start=1):
            lines += ["", f"**Lượt {index} — khách:** {turn['user']}", "", "**Leader:**", "", turn["answer"] or "_(không có câu trả lời)_"]
        lines.append("")
    return "\n".join(lines)


def compare(old_path: str, new_path: str) -> str:
    old = {r["id"]: r for r in json.loads(Path(old_path).read_text(encoding="utf-8"))["scenarios"]}
    new = {r["id"]: r for r in json.loads(Path(new_path).read_text(encoding="utf-8"))["scenarios"]}
    lines = [
        "| Kịch bản | Đạt (cũ → mới) | Token vào | % cache | Trao đổi | Bị chặn bằng chứng |",
        "|---|---|---|---|---|---|",
    ]
    for scenario_id in sorted(set(old) | set(new)):
        a, b = old.get(scenario_id), new.get(scenario_id)
        if not a or not b:
            continue
        sa, sb = a["summary"], b["summary"]
        lines.append(
            f"| {scenario_id} | {'✅' if a['passed'] else '❌'} → {'✅' if b['passed'] else '❌'} | "
            f"{sa['input_tokens']:,} → {sb['input_tokens']:,} | "
            f"{sa['cache_hit_ratio']:.0%} → {sb['cache_hit_ratio']:.0%} | "
            f"{sa['exchanges']} → {sb['exchanges']} | "
            f"{sa['evidence_rejections']} → {sb['evidence_rejections']} |"
        )
    return "\n".join(lines)


async def main_async(args) -> int:
    scenarios = json.loads(Path(args.scenarios).read_text(encoding="utf-8"))["scenarios"]
    if args.only:
        scenarios = [s for s in scenarios if s["id"] in set(args.only)]
    platform = Platform(args.base_url, user_id=args.user_id, timeout=60)
    if not args.user_id:
        await platform.login(args.tenant, args.identity, args.password)
    started_at = datetime.now().strftime("%Y%m%d-%H%M%S")
    results = {"started_at": started_at, "base_url": args.base_url, "scenarios": []}
    for scenario in scenarios:
        print(f"→ {scenario['id']} …", flush=True)
        try:
            outcome = await run_scenario(platform, scenario, args)
        except Exception as exc:  # noqa: BLE001 - one failure must not stop the run
            outcome = {
                "id": scenario["id"],
                "title": scenario["title"],
                "domain": scenario["domain"],
                "passed": False,
                "check_score": 0.0,
                "checks": [{"name": "chạy kịch bản", "passed": False, "detail": repr(exc)}],
                "judge": None,
                "summary": summarize({}),
                "seconds": 0,
                "transcript": [],
            }
        print(f"  {'ĐẠT' if outcome['passed'] else 'CHƯA ĐẠT'} ({outcome['check_score']:.2f})", flush=True)
        results["scenarios"].append(outcome)
    out = Path(args.output) / started_at
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "REPORT.md").write_text(render_report(results), encoding="utf-8")
    print(f"Báo cáo: {out / 'REPORT.md'}")
    await platform.http.aclose()
    return 0 if all(r["passed"] for r in results["scenarios"]) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Workforce collaboration evaluation")
    parser.add_argument("--base-url", default=os.getenv("WORKFORCE_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--tenant", default=os.getenv("WORKFORCE_TENANT", "default"))
    parser.add_argument("--identity", default=os.getenv("WORKFORCE_IDENTITY"))
    parser.add_argument("--password", default=os.getenv("WORKFORCE_PASSWORD"))
    parser.add_argument("--user-id", default=os.getenv("WORKFORCE_USER_ID"))
    parser.add_argument("--scenarios", default=str(DEFAULT_SCENARIOS))
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--judge", action="store_true", help="also score with EVAL_JUDGE_MODEL")
    parser.add_argument("--turn-timeout", type=float, default=300.0)
    parser.add_argument("--output", default=".artifacts/collab-eval")
    parser.add_argument("--compare", nargs=2, metavar=("OLD", "NEW"))
    args = parser.parse_args()
    if args.compare:
        print(compare(*args.compare))
        return 0
    if not args.user_id and not (args.identity and args.password):
        parser.error("cần --identity/--password (hoặc --user-id khi platform tắt auth)")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
