"""Durable recovery handlers. They only read partner state; no write is retried."""

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from .....message import TextBlock
from ...contracts import Scope
from ...orchestration._tables import workflows
from ._case import _Case
from ._contract import route_for_workflow
from ._tables import approvals, operations, receipts


class UnifiedRecovery:
    def __init__(self, store, case_runtime, provider, approvals, workflow_service, requests, jobs, identity):
        self.store = store
        self.case = case_runtime
        self.provider = provider
        self.approvals = approvals
        self.workflows = workflow_service
        self.requests = requests
        self.jobs = jobs
        self.identity = identity

    def handlers(self):
        return {"workforce.unified.reconcile": self.reconcile,
                "workforce.unified.receipt": self.receipt,
                "workforce.unified.projection": self.projection,
                "workforce.unified.approval_expiry": self.approval_expiry}

    async def resume_pending(self):
        """Schedule legacy pending records at startup, using durable dedup keys."""
        async with self.store._uows() as uow:
            rows = (await uow.execute(select(workflows).where(workflows.c.state != "closed"))).mappings().all()
            for workflow in rows:
                scope = Scope(**{key: workflow[key] for key in ("tenant_id", "domain_id", "area_id", "manager_account_id")})
                pending = (await uow.execute(select(operations.c.client_reference).where(
                    operations.c.workflow_id == workflow["id"], operations.c.terminal.is_(False),
                ))).scalars().all()
                for reference in pending:
                    await self.jobs.enqueue(scope, "workforce.unified.reconcile",
                        {"client_reference": reference, "generation": 0}, "unified-reconcile:" + reference + ":0", uow)
                waiting = (await uow.execute(select(approvals).where(
                    approvals.c.workflow_id == workflow["id"], approvals.c.status == "pending",
                ))).mappings().all()
                for approval in waiting:
                    await self.jobs.enqueue(scope, "workforce.unified.approval_expiry",
                        {"approval_id": approval["approval_id"]}, "unified-approval-expiry:" + approval["approval_id"],
                        uow, not_before=approval["expires_at"])
                unprojected = (await uow.execute(select(receipts.c.receipt_id).join(
                    operations, operations.c.operation_id == receipts.c.operation_id,
                ).where(operations.c.workflow_id == workflow["id"], receipts.c.projection_text.is_not(None),
                        receipts.c.projected_at.is_(None)))).scalars().all()
                for receipt_id in unprojected:
                    await self.jobs.enqueue(scope, "workforce.unified.projection", {"receipt_id": receipt_id},
                        "unified-projection:" + receipt_id, uow)
            pending_receipts = (await uow.execute(select(receipts).where(
                receipts.c.ingestion_status == "quarantined", receipts.c.envelope.is_not(None),
            ))).mappings().all()
            from ._tables import integrations
            for receipt in pending_receipts:
                tenant_id = await uow.scalar(select(integrations.c.tenant_id).where(
                    integrations.c.integration_id == receipt["integration_id"]))
                await self.jobs.enqueue_provider({"tenant_id": tenant_id, "provider_integration_id": receipt["integration_id"]},
                    "workforce.unified.receipt", {"receipt_id": receipt["receipt_id"], "generation": 0},
                    "unified-receipt:" + receipt["receipt_id"] + ":0", uow)
            await uow.commit()

    async def reconcile(self, job):
        reference = job.payload["client_reference"]
        operation = await self.store.operation(reference)
        if operation is None or operation["terminal"]:
            return {"status": "settled"}
        async with self.store._uows() as uow:
            workflow = (await uow.execute(select(workflows).where(
                workflows.c.id == operation["workflow_id"],
            ))).mappings().one()
        scope = Scope(**{key: workflow[key] for key in ("tenant_id", "domain_id", "area_id", "manager_account_id")})
        if job.scope != scope:
            raise PermissionError("reconciliation job scope mismatch")
        await self.identity.check_scope_active(scope)
        if workflow["state"] == "closed":
            return {"status": "closed"}
        session = await self.store.session_of_workflow(operation["workflow_id"])
        route = await route_for_workflow(self.store, operation["workflow_id"], session["route_id"] if session else None)
        lookup_name = next((item.get("reconcile_tool") for item in (route or {}).get("tools") or []
                            if item.get("name") == operation["tool_name"]), None)
        lookup_spec = next((item for item in (route or {}).get("tools") or []
                            if item.get("name") == lookup_name and item.get("read_only")
                            and not item.get("client_reference_arg")), None)
        # No lookup configured: keep the unknown outcome visible and retry persisted events.
        # A missing operation is never permission to dispatch again.
        if session and lookup_spec and self.case._storage is not None:
            server = await self.case._storage.get_mcp(scope.manager_account_id, lookup_spec.get("mcp_id"))
            current = next((item for item in (getattr(server, "discovered_tools", None) or [])
                            if item.get("name") == lookup_spec.get("mcp_tool")), None)
            if (server is None or not server.enabled or current is None or current.get("read_only") is not True
                    or lookup_spec.get("mcp_tool") in (server.client.confirm_tools or [])):
                raise PermissionError("Reconciliation requires a currently approved read-only connector")
            tools = await self.case._tools(scope.manager_account_id, _Case(self.store, session, route), route,
                                          only={lookup_name})
            if tools:
                context = await self.store.grant_context(operation["workflow_id"])
                import asyncio
                chunk = await asyncio.wait_for(tools[0]._mcp.call(
                    ticket_id=context["ticket_id"], client_reference=reference), timeout=30)
                raw = "\n".join(part.text for part in chunk.content if isinstance(part, TextBlock))
                result = json.loads(raw)
                if result.get("found") is True and isinstance(result.get("result"), dict):
                    answer = result["result"]
                    await self.store.settle_operation(reference, str(answer.get("status") or "unknown"),
                        str(answer.get("external_job_id") or "") or None)
                    await self.store.save_call_result(reference, {"text": json.dumps(answer, ensure_ascii=False),
                        "state": "success"})
        async with self.store._uows() as uow:
            pending = (await uow.execute(select(receipts.c.receipt_id).where(
                receipts.c.integration_id == operation["integration_id"],
                receipts.c.ingestion_status == "quarantined",
            ))).scalars().all()
        for receipt_id in pending:
            await self.provider.reprocess(receipt_id)
        operation = await self.store.operation(reference)
        if not operation["terminal"]:
            generation = int(job.payload.get("generation", 0)) + 1
            await self.jobs.enqueue(scope, job.job_type,
                {"client_reference": reference, "generation": generation},
                f"unified-reconcile:{reference}:{generation}",
                not_before=datetime.now(UTC) + timedelta(seconds=30))
        return {"status": operation["status"], "client_reference": reference}

    async def receipt(self, job):
        receipt_id = job.payload["receipt_id"]
        async with self.store._uows() as uow:
            row = (await uow.execute(select(receipts).where(receipts.c.receipt_id == receipt_id))).mappings().one()
        if job.provider_integration_id != row["integration_id"]:
            raise PermissionError("receipt job integration mismatch")
        answer = await self.provider.reprocess(receipt_id)
        if answer["ingestion_status"] == "quarantined" and row["envelope"] is not None:
            generation = int(job.payload.get("generation", 0)) + 1
            await self.jobs.enqueue_provider(
                {"tenant_id": job.tenant_id, "provider_integration_id": row["integration_id"]}, job.job_type,
                {"receipt_id": receipt_id, "generation": generation},
                f"unified-receipt:{receipt_id}:{generation}",
                not_before=datetime.now(UTC) + timedelta(seconds=30))
        return {"status": answer["ingestion_status"]}

    async def projection(self, job):
        if not await self.provider.replay_projection(job.payload["receipt_id"]):
            raise RuntimeError("Ticket room is not ready for persisted progress projection")
        return {"status": "projected"}

    async def approval_expiry(self, job):
        expired = await self.approvals.expire(job.payload["approval_id"], self.workflows, self.requests)
        return {"status": "expired" if expired else "already_resolved"}
