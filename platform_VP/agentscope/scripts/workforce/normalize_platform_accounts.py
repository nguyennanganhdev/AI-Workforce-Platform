"""Apply a private, reviewed login-rotation plan without changing identity scope.

Run as a deployment operator against a backed-up database. The plan contains
old/new login names and new passwords; never include it in source or an image.
This does not rotate partner keys. The operator separately rotates the JWT
signing key and recreates the app so existing access tokens stop working.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from argon2 import PasswordHasher
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from agentscope.app.auth import AuthService


async def apply_plan(plan_path: Path) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    accounts = plan["accounts"]
    ids = [a["id"] for a in accounts]
    if len(ids) != len(set(ids)) or not accounts:
        raise ValueError("account plan must contain distinct existing IDs")
    for account in accounts:
        AuthService._validate_registration(
            plan["tenant_id"], account["email"], account["username"], account["password"],
        )
    engine = create_async_engine(os.environ["AGENTSCOPE_SQL_URL"])
    hasher = PasswordHasher()
    try:
        async with engine.begin() as db:
            rows = (await db.execute(text(
                "SELECT id,email,username,role,domain_id,area_id FROM auth_users "
                "WHERE tenant_id=:tenant FOR UPDATE"
            ), {"tenant": plan["tenant_id"]})).mappings().all()
            if {row["id"] for row in rows} != set(ids):
                raise ValueError("live account inventory changed; rebuild the plan")
            live = {row["id"]: row for row in rows}
            for account in accounts:
                current = live[account["id"]]
                expected = {
                    "email": account["old_email"], "username": account["old_username"],
                    "role": account["role"], "domain_id": account["domain_id"], "area_id": account["area_id"],
                }
                if any(current[key] != value for key, value in expected.items()):
                    raise ValueError("account changed since the plan was reviewed")
            for account in accounts:
                await db.execute(text(
                    "UPDATE auth_users SET username=:username,email=:email,password_hash=:hash,updated_at=now() "
                    "WHERE id=:id AND tenant_id=:tenant"
                ), {
                    "username": account["username"], "email": account["email"],
                    "hash": hasher.hash(account["password"]), "id": account["id"], "tenant": plan["tenant_id"],
                })
            revoked = await db.execute(text(
                "UPDATE auth_sessions SET revoked_at=now(),revoked_reason='credentials_rotated' "
                "WHERE user_id=ANY(:ids) AND revoked_at IS NULL"
            ), {"ids": ids})
            for area in plan.get("area_names", []):
                await db.execute(text(
                    "UPDATE areas SET name=:name WHERE id=:id AND domain_id=:domain_id"
                ), area)
        print(json.dumps({"accounts_rotated": len(accounts), "refresh_sessions_revoked": revoked.rowcount,
                          "account_ids_and_scopes_preserved": True, "partner_keys_changed": False}))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plan", required=True, type=Path)
    args = parser.parse_args()
    asyncio.run(apply_plan(args.plan))
