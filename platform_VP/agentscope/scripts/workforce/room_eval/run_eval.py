"""Room evaluation: each scenario k times through the real platform, pass^k.

A partner declaration (default: the Vinhomes one) is onboarded for a fresh
manager against fixture_mcp.py, so the room, its prompts and the model are
real while the partner's data comes from scenarios.json. A scenario passes
only when all k runs pass (pass^k): what the end user received, the state,
the partner actions that ran, refused messages and cost.

    python fixture_mcp.py scenarios.json ../../../.artifacts/room-eval/calls.jsonl 18766 &
    python run_eval.py --k 3 --declaration <vinhomes-declaration.json> [--fake-model]

Real models cost money: run it on purpose (``--fake-model`` uses the scripted
model of ../offline_partner_e2e for a free dry run of the harness).
"""

import argparse
import json
import re
import sys
import time
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ENV = dict(re.findall(r"^([A-Z0-9_]+)=(.*)$", (ROOT / ".env").read_text(encoding="utf-8"), re.M))
SECRET = {"X-Provisioning-Secret": ENV["PARTNER_API_PROVISIONING_SECRET"]}


def fold(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text.casefold()).replace("đ", "d")
    return "".join(c for c in plain if not unicodedata.combining(c))


def check(response, *ok):
    if response.status_code not in ok:
        raise SystemExit(f"{response.request.method} {response.request.url.path} -> {response.status_code} {response.text[:300]}")
    return response.json() if response.content else {}


def judge(scenario: dict, state: str, texts: list[str], calls: list[dict], refused: int) -> list[str]:
    """Why this run fails its scenario (empty: it passes)."""
    expect, problems = scenario["expect"], []
    said = fold(" ".join(texts))
    if not texts:
        problems.append("no message reached the user")
    if state not in expect.get("states", [state]):
        problems.append(f"state {state} not in {expect['states']}")
    called = {call["tool"] for call in calls}
    problems += [f"{tool} not called" for tool in expect.get("tools_called", []) if tool not in called]
    problems += [f"{tool} called" for tool in expect.get("tools_not_called", []) if tool in called]
    problems += [f'says "{p}"' for p in expect.get("must_not_include", []) if fold(p) in said]
    if expect.get("must_include_any") and not any(fold(p) in said for p in expect["must_include_any"]):
        problems.append(f"says none of {expect['must_include_any']}")
    if refused > expect.get("max_refused", 0):
        problems.append(f"{refused} messages refused by the evidence check")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--declaration", required=True)
    parser.add_argument("--scenarios", default=str(HERE / "scenarios.json"))
    parser.add_argument("--calls", default=str(ROOT / ".artifacts" / "room-eval" / "calls.jsonl"))
    parser.add_argument("--platform", default="http://127.0.0.1:8000")
    parser.add_argument("--mcp-url", default="http://host.docker.internal:18766/mcp")
    parser.add_argument("--fake-model", action="store_true")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--out", default=str(ROOT / ".artifacts" / "room-eval"))
    args = parser.parse_args()

    scenarios = json.loads(Path(args.scenarios).read_text(encoding="utf-8"))["scenarios"]
    if args.only:
        scenarios = [s for s in scenarios if s["id"] in args.only]
    run = uuid.uuid4().hex[:6]
    declaration = json.loads(Path(args.declaration).read_text(encoding="utf-8"))
    declaration["client"]["name"] = f"Room eval {run}"
    # Grants are issued by the partner's own server; the fixture MCP needs none.
    declaration["route"]["config"].pop("mcp_grants", None)

    with httpx.Client(base_url=args.platform, timeout=180) as http:
        area, email, password = f"eval-{run}", f"room.eval.{run}@example.com", "Room-eval-" + run
        check(http.post("/workforce/v1/admin/areas", headers=SECRET,
                        json={"domain_id": declaration["client"]["domain"], "area_id": area, "name": f"Eval {run}"}), 201)
        me = check(http.post("/auth/register", json={"email": email, "username": f"eval_{run}", "password": password,
                                                     "domain_id": declaration["client"]["domain"], "area_id": area}), 201)
        check(http.post("/workforce/v1/admin/memberships/verify", headers=SECRET, json={"manager_account_id": me["id"]}), 200)
        token = check(http.post("/auth/login", json={"tenant_id": "default", "identity": email, "password": password}), 200)
        auth = {"Authorization": "Bearer " + token["access_token"]}
        credential = {"type": "openai_credential", "name": "Room eval", "api_key": ENV.get("OPENAI_API_KEY", "")}
        if args.fake_model:
            credential.update(api_key="fake-key", base_url="http://host.docker.internal:18080/v1")
        check(http.post("/credential/", headers=auth, json={"data": credential}), 201)
        onboarded = check(http.post("/workforce/v1/admin/partner-onboarding", headers=SECRET, json={
            "declaration": declaration, "manager_account_id": me["id"], "mcp_url": args.mcp_url, "mcp_token": "t" * 40,
            "management_refs": ["eval-ref"], "environment": "sandbox"}), 200)
        customer = {"Authorization": "ApiKey " + onboarded["keys"]["customer_key"]}
        route = onboarded["routes"][0]
        check(http.post(f"/workforce/v1/partner/routes/{route['route_id']}/confirm", headers=customer, json={
            "schema_version": "1", "external_management_ref": "eval-ref", "expected_revision": route["revision"]}), 200)

        def quality():
            return check(http.get("/workforce/console/studio/quality", headers=auth, params={"days": "1"}), 200)

        report = []
        for scenario in scenarios:
            runs = []
            for index in range(args.k):
                ticket = f"{scenario['id']}--{run}{index}"
                lines = [f"ticket_id: {ticket}", "handover_version: v1.1", "Cư dân: Nguyễn Văn An",
                         "Quan hệ cư trú: chủ hộ", "Căn: S1.01-1201", "Tòa: Sapphire 1",
                         *(f"{key}: {value}" for key, value in scenario["handover"].items())]
                before = quality()
                started = time.monotonic()
                accepted = check(http.post("/workforce/v1/partner/requests", headers=customer, json={
                    "schema_version": "1", "command_type": "start_workflow", "external_request_id": f"{ticket}-start",
                    "external_management_ref": "eval-ref", "external_user_id": f"resident-{ticket}",
                    "external_ticket_id": ticket, "external_conversation_id": f"chat-{ticket}",
                    "timezone": "Asia/Ho_Chi_Minh", "message": {"type": "text", "text": "\n".join(lines)}}), 200, 202)
                deadline = time.time() + 300
                while True:
                    result = check(http.get(f"/workforce/v1/partner/requests/{accepted['request_id']}", headers=customer,
                                            params={"external_user_id": f"resident-{ticket}"}), 200)
                    if result["request_status"] in ("completed", "failed", "blocked") or time.time() > deadline:
                        break
                    time.sleep(3)
                after = quality()
                texts = [m["text"] for m in (result.get("result") or {}).get("messages") or []]
                calls = [json.loads(line) for line in Path(args.calls).read_text(encoding="utf-8").splitlines()
                         if line.strip() and json.loads(line)["ticket_id"] == ticket] if Path(args.calls).exists() else []
                refused = after["messages_refused"] - before["messages_refused"]
                cost = None
                if after["est_cost_usd"] is not None and before["est_cost_usd"] is not None:
                    cost = round(after["est_cost_usd"] - before["est_cost_usd"], 4)
                problems = judge(scenario, result.get("workflow_state", ""), texts, calls, refused)
                runs.append({"ticket": ticket, "passed": not problems, "problems": problems, "state": result.get("workflow_state"),
                             "messages": texts, "tools": [c["tool"] for c in calls], "refused": refused, "cost_usd": cost,
                             "seconds": round(time.monotonic() - started, 1)})
                print(f"{scenario['id']:<16} run {index + 1}/{args.k}: {'PASS' if not problems else 'FAIL ' + '; '.join(problems)}"
                      f"  ${cost}  {runs[-1]['seconds']}s", flush=True)
            costs = [r["cost_usd"] for r in runs if r["cost_usd"] is not None]
            report.append({"scenario": scenario["id"], "title": scenario["title"], "pass_k": all(r["passed"] for r in runs),
                           "passed_runs": sum(r["passed"] for r in runs), "k": args.k,
                           "avg_cost_usd": round(sum(costs) / len(costs), 4) if costs else None, "runs": runs})

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"room-eval-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{run}.json"
    path.write_text(json.dumps({"k": args.k, "fake_model": args.fake_model, "scenarios": report}, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    passed = sum(item["pass_k"] for item in report)
    print(f"\npass^{args.k}: {passed}/{len(report)} scenarios  ->  {path}")
    for item in report:
        print(f"  {'PASS' if item['pass_k'] else 'FAIL'}  {item['scenario']:<16} {item['passed_runs']}/{item['k']}  avg ${item['avg_cost_usd']}")


if __name__ == "__main__":
    main()
