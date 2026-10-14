"""Make a fresh Docker stack ready to use, without calling any model.

Creates (each step is skipped when it already exists):

1. an area-manager account (domain ``vinhomes``, area ``ocean-park-1``) and
   verifies its Workforce membership;
2. an OpenAI credential from ``OPENAI_API_KEY`` for that account;
3. the DEMO MCP server (``--profile demo``) in that account's MCP list;
4. a partner API key, a route ``tower-a`` granted by the manager and
   confirmed by the partner (only when ``WORKFORCE_PARTNER_API=true``).

Secrets go to ``.artifacts/demo-access/ACCESS.md`` (git-ignored), never to
stdout. Usage::

    python scripts/workforce/bootstrap_demo.py --env-file .env
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
from pathlib import Path

import httpx

DOMAIN, AREA, REF = "vinhomes", "ocean-park-1", "tower-a"
OUT = Path(".artifacts/demo-access")


def read_env(path: str) -> dict[str, str]:
    text = Path(path).read_text(encoding="utf-8")
    return dict(re.findall(r"^([A-Z0-9_]+)=(.*)$", text, re.M))


def saved() -> dict:
    file = OUT / "state.json"
    return json.loads(file.read_text(encoding="utf-8")) if file.exists() else {}


def save(state: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def check(response: httpx.Response, *ok: int) -> dict:
    if response.status_code not in ok:
        raise SystemExit(f"{response.request.method} {response.request.url.path}: HTTP {response.status_code} {response.text[:300]}")
    return response.json() if response.content else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--email", default="quanly.demo@example.com")
    parser.add_argument("--username", default="quanly_demo")
    parser.add_argument("--mcp-url", default="http://demo-mcp:8765/mcp")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    env = read_env(args.env_file)
    base = args.base_url or f"http://localhost:{env.get('AGENTSCOPE_PORT', '8000')}"
    state = saved()
    password = state.get("password") or "Demo-" + secrets.token_urlsafe(12)
    provisioning = {"X-Provisioning-Secret": env["PARTNER_API_PROVISIONING_SECRET"]}
    save({**state, "password": password})

    with httpx.Client(base_url=base, timeout=60) as http:
        check(http.get("/health"), 200)

        registered = http.post(
            "/auth/register",
            json={"email": args.email, "username": args.username, "password": password, "domain_id": DOMAIN, "area_id": AREA},
        )
        check(registered, 201, 409)
        print("Tài khoản quản lý:", "đã tạo" if registered.status_code == 201 else "đã có")
        if registered.status_code == 201:
            # A new BQL account waits for approval; the operator's verification approves it.
            check(http.post("/workforce/v1/admin/memberships/verify", headers=provisioning,
                            json={"manager_account_id": registered.json()["id"]}), 200, 404)
        token = check(
            http.post("/auth/login", json={"tenant_id": env.get("AUTH_DEFAULT_TENANT_ID", "default"), "identity": args.email, "password": password}),
            200,
        )["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        me = check(http.get("/auth/me", headers=auth), 200)
        check(http.post("/workforce/v1/admin/memberships/verify", headers=provisioning, json={"manager_account_id": me["id"]}), 200, 404)
        print("Xác minh quản lý: xong")

        credentials = check(http.get("/credential/", headers=auth), 200)["credentials"]
        if not any(c["data"].get("name") == "OpenAI" for c in credentials):
            if not env.get("OPENAI_API_KEY"):
                raise SystemExit("OPENAI_API_KEY is empty in the env file")
            data = {"type": "openai_credential", "name": "OpenAI", "api_key": env["OPENAI_API_KEY"]}
            check(http.post("/credential/", headers=auth, json={"data": data}), 201)
        print("Credential OpenAI: xong")

        mcps = check(http.get("/mcp", headers=auth), 200)
        if not any(m["name"] == "demo_workforce" for m in mcps):
            installed = http.post(
                "/mcp",
                headers=auth,
                json={"name": "demo_workforce", "display_name": "DEMO du lịch + toà nhà", "url": args.mcp_url},
            )
            if installed.status_code == 201:
                print("MCP demo: đã thêm", len(installed.json().get("tools", [])), "tool")
            else:
                print(f"MCP demo: chưa thêm được (HTTP {installed.status_code}); chạy compose với --profile demo")
        else:
            print("MCP demo: đã có")

        partner = state.get("partner")
        if env.get("WORKFORCE_PARTNER_API", "").lower() in {"1", "true", "yes"}:
            if not partner:
                partner = check(http.post("/integrations/api-keys", headers=provisioning, json={"domain_id": DOMAIN, "name": "Đối tác demo"}), 201)
            routes = check(http.get("/workforce/v1/manager/partner-routes", headers=auth), 200)
            route = next((r for r in routes if r["partner_client_id"] == partner["client_id"] and r["status"] != "revoked"), None)
            if route is None:
                route = check(
                    http.post("/workforce/v1/manager/partner-routes", headers=auth, json={"partner_client_id": partner["client_id"], "external_management_ref": REF}),
                    201,
                )
            if route["status"] == "pending_confirmation":
                route = check(
                    http.post(
                        f"/workforce/v1/partner/routes/{route['route_id']}/confirm",
                        headers={"Authorization": f"ApiKey {partner['api_key']}"},
                        json={"expected_revision": route["revision"]},
                    ),
                    200,
                )
            print("Đối tác demo: tuyến", REF, route["status"])

    save({"password": password, "partner": partner})
    web = f"http://localhost:{env.get('WEB_PORT', '5173')}"
    lines = [
        "# Truy cập stack demo (bí mật — không commit, không gửi đi)",
        "",
        f"- Web: {web}",
        f"- API: {base}",
        f"- Tenant: `{env.get('AUTH_DEFAULT_TENANT_ID', 'default')}`",
        f"- Quản lý khu vực: `{args.email}` / `{password}` (domain `{DOMAIN}`, khu `{AREA}`)",
        "- Credential: OpenAI (key từ `.env`)",
        f"- Model: mặc định `{env.get('WORKFORCE_MODEL_NAME', '')}`, model cao `{env.get('WORKFORCE_LEADER_MODEL_NAME', '')}`",
        f"- MCP demo (trong Docker): {args.mcp_url}",
    ]
    if partner:
        lines += [
            f"- Đối tác demo: client `{partner['client_id']}`, key `{partner['api_key']}`, mã toà `{REF}`",
            f"- Kiểm hợp đồng: `python scripts/workforce/partner_sandbox_check.py --base-url {base} --api-key <key> --management-ref {REF}`",
        ]
    (OUT / "ACCESS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nThông tin đăng nhập: {OUT / 'ACCESS.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
