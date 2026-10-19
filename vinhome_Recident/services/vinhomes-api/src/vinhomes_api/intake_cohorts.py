"""M2 preparation: server-owned resident cohorts; disabled unless explicitly enabled."""

import json
import os
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text


def configuration():
    if os.getenv("VINHOMES_CHATBOT_COHORT_CUTOVER_ENABLED", "false").strip().lower() != "true":
        return []
    try:
        cohorts = json.loads(os.environ["VINHOMES_CHATBOT_PLATFORM_COHORTS"])
        if not isinstance(cohorts, list) or not cohorts:
            raise ValueError("Explicit cohorts required")
        seen = set()
        for cohort in cohorts:
            if set(cohort) != {"id", "tenant_id", "resident_ids", "platform_url"}:
                raise ValueError("Invalid cohort fields")
            if not isinstance(cohort["tenant_id"], str):
                raise ValueError("Tenant UUID string required")
            cohort["tenant_id"] = str(UUID(cohort["tenant_id"]))
            if not isinstance(cohort["id"], str) or not 1 <= len(cohort["id"]) <= 100:
                raise ValueError("Cohort ID required")
            ids = cohort["resident_ids"]
            if not isinstance(ids, list) or not ids or any(not isinstance(user, str) or not 1 <= len(user) <= 255 for user in ids):
                raise ValueError("Explicit resident IDs required")
            url = urlsplit(cohort["platform_url"])
            if (url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"})) or not url.netloc or url.username or url.password or url.query or url.fragment:
                raise ValueError("Trusted HTTPS/loopback Platform URL required")
            for user in ids:
                key = (cohort["tenant_id"], user)
                if key in seen:
                    raise ValueError("Resident appears in multiple cohorts")
                seen.add(key)
        return cohorts
    except (KeyError, TypeError, ValueError) as exc:
        # Never silently reopen legacy intake on malformed enabled config.
        raise HTTPException(503, detail={"code": "INTAKE_COHORT_CONFIG_INVALID"}) from exc


async def policy(db, actor_id):
    cohorts = configuration()
    if cohorts:
        tenant = (await db.execute(text("SELECT current_setting('app.tenant_id', true)"))).scalar_one()
        for cohort in cohorts:
            if cohort["tenant_id"] == tenant and actor_id in cohort["resident_ids"]:
                return {"mode": "platform", "cohort_id": cohort["id"], "platform_url": cohort["platform_url"],
                        "legacy_new_intake": False}
    return {"mode": "legacy", "cohort_id": None, "platform_url": None, "legacy_new_intake": True}


async def require_legacy_intake(db, actor_id):
    current = await policy(db, actor_id)
    if not current["legacy_new_intake"]:
        raise HTTPException(409, detail={"code": "INTAKE_MOVED_TO_PLATFORM", **current,
            "message": "Vui lòng tạo yêu cầu mới trên Platform. Lịch sử và tiến độ công việc vẫn được giữ."})
