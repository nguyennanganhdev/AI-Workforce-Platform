"""Seed the platform's standard demo data through its admin APIs (idempotent).

Domains, their areas, one domain admin per domain and one BQL account per
area, the way an operator would set them up in the admin page: the platform
admin adds domains and areas and creates domain admins; each BQL registers
and is approved. Anything that already exists is kept. New passwords are
appended to the access file (git-ignored), never printed.

    PLATFORM_ADMIN_PASSWORD=... python scripts/workforce/seed_platform_data.py \\
        --platform http://127.0.0.1:8000 --access .artifacts/demo-access/ACCESS.md

BQL accounts get the platform's model key on first use when
WORKFORCE_PLATFORM_OPENAI_API_KEY is set (no credential to add by hand).
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from datetime import date
from pathlib import Path

import httpx

STANDARD = {
    "vinhomes": ("Vinhomes", [
        ("ocean-park-1", "Ocean Park 1"),
        ("ocean-park-2", "Ocean Park 2"),
        ("ocean-park-3", "Ocean Park 3"),
        ("smart-city", "Smart City"),
        ("times-city", "Times City"),
    ]),
    "vinpearl": ("Vinpearl", [("vinpearl-phu-quoc", "Vinpearl Phú Quốc"), ("vinpearl-nha-trang", "Vinpearl Nha Trang")]),
    "vinwonders": ("VinWonders", [("vinwonders-phu-quoc", "VinWonders Phú Quốc"), ("vinwonders-nha-trang", "VinWonders Nha Trang")]),
}


def ok(response: httpx.Response, *codes: int) -> dict | list:
    if response.status_code not in codes:
        raise SystemExit(f"{response.request.method} {response.request.url.path} -> {response.status_code} {response.text[:200]}")
    return response.json() if response.content else {}


def password(prefix: str) -> str:
    return f"{prefix}-{secrets.token_urlsafe(12)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--platform", default="http://127.0.0.1:8000")
    parser.add_argument("--admin", default="admin@platform.local", help="platform admin login")
    parser.add_argument("--access", default=".artifacts/demo-access/ACCESS.md")
    parser.add_argument("--tenant", default="default")
    args = parser.parse_args()
    admin_password = os.environ.get("PLATFORM_ADMIN_PASSWORD", "")
    if not admin_password:
        raise SystemExit("set $PLATFORM_ADMIN_PASSWORD")
    created: list[str] = []
    with httpx.Client(base_url=args.platform, timeout=60) as http:
        login = ok(http.post("/auth/login", json={"tenant_id": args.tenant, "identity": args.admin, "password": admin_password}), 200)
        admin = {"Authorization": "Bearer " + login["access_token"]}
        accounts = ok(http.get("/admin/accounts", headers=admin), 200)
        directory = {d["id"]: d for d in ok(http.get("/admin/directory", headers=admin), 200)}
        for domain_id, (domain_name, areas) in STANDARD.items():
            if domain_id not in directory:
                ok(http.put(f"/admin/domains/{domain_id}", headers=admin, json={"name": domain_name, "active": True}), 200)
                print(f"domain {domain_id}: added")
            known = {a["id"]: a for a in (directory.get(domain_id) or {}).get("areas", [])}
            for area_id, area_name in areas:
                if area_id not in known:
                    ok(http.put(f"/admin/domains/{domain_id}/areas/{area_id}", headers=admin,
                                json={"name": area_name, "active": True}), 200)
                    print(f"area {area_id}: added")
            if not any(a["role"] == "DOMAIN_ADMIN" and a["domain_id"] == domain_id for a in accounts):
                secret = password("Dm")
                ok(http.post("/admin/domain-admins", headers=admin, json={
                    "email": f"admin.{domain_id}@example.com", "username": f"{domain_id}_admin",
                    "password": secret, "domain_id": domain_id}), 201)
                created.append(f"- Quản trị domain {domain_name}: `admin.{domain_id}@example.com` / `{secret}`")
                print(f"domain admin {domain_id}: created")
        directory = {d["id"]: d for d in ok(http.get("/admin/directory", headers=admin), 200)}
        for domain_id, (_name, areas) in STANDARD.items():
            by_id = {a["id"]: a for a in directory[domain_id]["areas"]}
            for area_id, area_name in areas:
                if by_id[area_id]["managers"]:
                    continue
                secret, email = password("Bql"), f"bql.{area_id}@example.com"
                ok(http.post("/auth/register", json={
                    "email": email, "username": "bql_" + area_id.replace("-", "_"), "password": secret,
                    "domain_id": domain_id, "area_id": area_id}), 201)
                pending = ok(http.get("/admin/accounts", headers=admin, params={"status_filter": "pending"}), 200)
                account = next(a for a in pending if a["email"] == email)
                ok(http.post(f"/admin/accounts/{account['id']}/approve", headers=admin), 200)
                created.append(f"- BQL {area_name}: `{email}` / `{secret}`")
                print(f"bql {area_id}: registered and approved")
    if created:
        access = Path(args.access)
        access.parent.mkdir(parents=True, exist_ok=True)
        with access.open("a", encoding="utf-8") as file:
            file.write(f"\n## Dữ liệu chuẩn ({date.today().isoformat()})\n" + "\n".join(created) + "\n")
        print(f"{len(created)} new accounts; passwords in {access}")
    else:
        print("nothing to add")
    return 0


if __name__ == "__main__":
    sys.exit(main())
