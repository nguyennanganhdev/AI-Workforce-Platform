"""Onboard a partner from its declaration (unified mode, operator tool).

Reads the partner's declaration (e.g. Vinhomes'
``deploy/platform/vinhomes-declaration.json``), posts it to
``/workforce/v1/admin/partner-onboarding`` and writes the keys the partner
needs into ``platform.env``, in the partner's own variable names. Keys are
shown once by the platform; this script never prints them.

    export PARTNER_API_PROVISIONING_SECRET=...      # the platform's .env
    export PARTNER_MCP_TOKEN=...                    # the token the partner sent
    python scripts/workforce/onboard_partner.py \
        --platform http://127.0.0.1:8000 \
        --partner-url http://host.docker.internal:8000 \
        --declaration vinhomes-declaration.json \
        --manager-email quanly.demo@example.com --manager-password-env MANAGER_PASSWORD \
        --mcp-url https://vinhome-platform.duckdns.org/mcp \
        --management-refs local-management \
        --environment sandbox

Run again after the declaration changes: no new keys unless --new-keys.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx


def manager_id(http: httpx.Client, args) -> str:
    if args.manager_account_id:
        return args.manager_account_id
    password = os.environ.get(args.manager_password_env, "")
    if not args.manager_email or not password:
        raise SystemExit("--manager-account-id, or --manager-email with $" + args.manager_password_env)
    login = http.post(
        "/auth/login",
        json={"tenant_id": args.tenant, "identity": args.manager_email, "password": password},
    )
    if login.status_code != 200:
        raise SystemExit(f"manager login failed: HTTP {login.status_code}")
    me = http.get("/auth/me", headers={"Authorization": "Bearer " + login.json()["access_token"]})
    return me.json()["id"]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--platform", required=True, help="the platform as this machine reaches it")
    parser.add_argument("--partner-url", required=True, help="the platform as the partner's containers reach it")
    parser.add_argument("--declaration", required=True)
    parser.add_argument("--manager-account-id")
    parser.add_argument("--manager-email")
    parser.add_argument("--manager-password-env", default="MANAGER_PASSWORD")
    parser.add_argument("--tenant", default="default")
    parser.add_argument("--mcp-url", required=True)
    parser.add_argument("--mcp-token-env", default="PARTNER_MCP_TOKEN")
    parser.add_argument("--management-refs", required=True, help="comma separated")
    parser.add_argument("--environment", choices=("sandbox", "production"), default="sandbox")
    parser.add_argument("--new-keys", action="store_true")
    parser.add_argument("--secret-env", default="PARTNER_API_PROVISIONING_SECRET")
    parser.add_argument("--env-prefix", default="VINHOMES_API_PLATFORM_")
    parser.add_argument("--out", default="platform.env")
    args = parser.parse_args()

    secret = os.environ.get(args.secret_env, "")
    if not secret:
        raise SystemExit(f"${args.secret_env} is empty")
    token = os.environ.get(args.mcp_token_env) or None
    declaration = json.loads(Path(args.declaration).read_text(encoding="utf-8"))
    with httpx.Client(base_url=args.platform.rstrip("/"), timeout=120) as http:
        manager = manager_id(http, args)
        headers = {"X-Provisioning-Secret": secret}
        verified = http.post(
            "/workforce/v1/admin/memberships/verify",
            headers=headers,
            json={"manager_account_id": manager},
        )
        if verified.status_code != 200:
            raise SystemExit(f"manager verification failed: HTTP {verified.status_code} {verified.text[:200]}")
        response = http.post(
            "/workforce/v1/admin/partner-onboarding",
            headers=headers,
            json={
                "declaration": declaration,
                "manager_account_id": manager,
                "mcp_url": args.mcp_url,
                "mcp_token": token,
                "management_refs": [ref.strip() for ref in args.management_refs.split(",") if ref.strip()],
                "environment": args.environment,
                "new_keys": args.new_keys,
            },
        )
    if response.status_code != 200:
        raise SystemExit(f"onboarding failed: HTTP {response.status_code} {response.text[:500]}")
    result = response.json()
    keys = result.pop("keys")
    prefix = args.env_prefix
    lines = [
        "# Written by onboard_partner.py. Secret: do not commit, send over a safe channel.",
        f"{prefix}URL={args.partner_url.rstrip('/')}",
    ]
    names = {
        "customer_key": "CUSTOMER_KEY",
        "provider_key": "PROVIDER_KEY",
        "signing_key_id": "SIGNING_KEY_ID",
        "signing_secret": "SIGNING_SECRET",
    }
    lines += [f"{prefix}{names[key]}={value}" for key, value in keys.items() if key in names]
    if keys:
        Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Keys written to {args.out} ({', '.join(keys)}).")
    else:
        print("No new keys (already onboarded). Use --new-keys to rotate them.")
    Path(".applied.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Leader agent {result['leader_agent_id']} v{result['leader_version']}, "
          f"MCP {result['mcp']['name']} ({result['mcp']['tools']} tools), {len(result['tools'])} tools on the route.")
    pending = [r for r in result["routes"] if r["status"] == "pending_confirmation"]
    for route in result["routes"]:
        print(f"Route {route['management_ref']}: {route['route_id']} v{route['revision']} {route['status']}")
    if pending:
        print("\nThe partner confirms with its customer key, e.g. (Vinhomes):")
        print("  dc exec platform-sync python -m vinhomes_api.platform confirm-routes " + " ".join(
            f"--route {r['management_ref']}={r['route_id']}:{r['revision']}" for r in pending))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
