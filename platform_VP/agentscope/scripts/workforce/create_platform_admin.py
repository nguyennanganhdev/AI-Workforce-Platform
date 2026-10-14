"""Create the platform's administrator (one-time setup, run where the database is reachable).

    docker compose exec -e ADMIN_PASSWORD='...' app \\
        python scripts/workforce/create_platform_admin.py --email admin@example.com --username admin

The password is read from $ADMIN_PASSWORD (never a command-line argument). The
platform admin approves management board (BQL) registrations, adds integrated
domains and their areas, and creates each domain's admin in the web UI (Quản trị).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from agentscope.app.auth import PLATFORM_ADMIN, AuthService, UserAlreadyExistsError


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="ADMIN_PASSWORD")
    args = parser.parse_args()
    password = os.environ.get(args.password_env, "")
    if len(password) < 12:
        raise SystemExit(f"${args.password_env} must hold a password of at least 12 characters")
    service = AuthService(
        database_url=os.environ["AGENTSCOPE_SQL_URL"],
        jwt_secret=os.environ["AUTH_JWT_SECRET"],
        refresh_pepper=os.environ["AUTH_REFRESH_PEPPER"],
        default_tenant_id=os.getenv("AUTH_DEFAULT_TENANT_ID", "default"),
    )
    async with service:
        try:
            user = await service.create_admin(
                tenant_id=service.default_tenant_id,
                email=args.email,
                username=args.username,
                password=password,
                role=PLATFORM_ADMIN,
            )
        except UserAlreadyExistsError:
            print("An account with this email or username already exists.")
            return 1
    print(f"Platform admin {user.username} created ({user.id}).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
