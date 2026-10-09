"""Snapshot provider outbox. State observation and event insertion commit together."""
import json
from datetime import UTC, datetime

from sqlalchemy import text

from .resident_contract import TENANT
from .workforce import fingerprint, transaction


async def collect(engine, tenant):
    async with transaction(engine, tenant) as db:
        jobs = (await db.execute(text(f"select * from vh_workforce_provider_jobs where tenant_id={TENANT} "
            "order by external_job_id for update skip locked limit 100"))).mappings().all()
        for job in jobs:
            kind, identifier = job["external_job_id"].split(":", 1)
            if kind == "plan":
                record = (await db.execute(text(f"select status,version from vh_ticket_plans where tenant_id={TENANT} and id=cast(:id as uuid)"), {"id": identifier})).mappings().first()
                completed, failed, cancelled = {"approved"}, {"rejected", "revision_requested"}, {"cancelled"}
            elif kind == "work_order":
                record = (await db.execute(text(f"select status,version from work_orders where tenant_id={TENANT} and id=cast(:id as uuid)"), {"id": identifier})).mappings().first()
                completed, failed, cancelled = {"completed"}, {"rejected"}, {"cancelled"}
            else:
                continue
            if not record:
                continue
            signature = f"{record['status']}:{record['version']}"
            if signature == job["last_status"]:
                continue
            version = job["provider_version"] + 1
            event_type = "job.completed" if record["status"] in completed else "job.failed" if record["status"] in failed else "job.cancelled" if record["status"] in cancelled else "job.progress"
            event_id = "vh:" + job["external_job_id"] + ":" + str(version)
            body = {"external_event_id": event_id, "external_job_id": job["external_job_id"],
                "client_reference": job["client_reference"], "event_type": event_type, "provider_version": version,
                "occurred_at": datetime.now(UTC).isoformat(), "data": {"business_status": record["status"], "business_version": record["version"]}}
            await db.execute(text(f"""insert into vh_workforce_outbox(tenant_id,kind,external_id,payload_hash,body)
                values({TENANT},'provider',:id,:hash,cast(:body as jsonb)) on conflict do nothing"""),
                {"id": event_id, "hash": fingerprint(body), "body": json.dumps(body)})
            await db.execute(text(f"""update vh_workforce_provider_jobs set last_status=:status,provider_version=:version
                where tenant_id={TENANT} and external_job_id=:id"""),
                {"status": signature, "version": version, "id": job["external_job_id"]})
