"""Offline isolated test loader and test-only dependencies.

Avoid loading agentscope.app's FastAPI bootstrap merely to test pure services.
This is not a production import path or replacement shared contract package.
"""

import asyncio
import importlib.util
import sys
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[3] / "src/agentscope/app/workforce/orchestration"
SPEC = importlib.util.spec_from_file_location(
    "wf_orchestration_under_test", SOURCE / "__init__.py",
    submodule_search_locations=[str(SOURCE)],
)
PACKAGE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PACKAGE
SPEC.loader.exec_module(PACKAGE)

from wf_orchestration_under_test._models import OrchestrationError


SCOPE = dict(tenant_id="tenant", domain_id="domain", area_id="area", manager_account_id="manager")
KEY = tuple(SCOPE.values())


class FakeIdentity:
    revoked = False

    async def check_scope_active(self, scope, uow=None):
        if self.revoked:
            raise OrchestrationError("SCOPE_REVOKED")


class FakeRepository:
    """Test fake with transactional rollback and CAS; not PostgreSQL evidence."""
    def __init__(self):
        self.rows = {}
        self.lock = asyncio.Lock()
        self.in_transaction = False

    @asynccontextmanager
    async def transaction(self):
        async with self.lock:
            before = deepcopy(self.rows)
            self.in_transaction = True
            try:
                yield self
            except BaseException:
                self.rows = before
                raise
            finally:
                self.in_transaction = False

    async def get(self, kind, scope, record_id, uow):
        return deepcopy(self.rows.get((kind, scope, record_id)))

    async def insert(self, kind, record, uow):
        record_id = getattr(record, {"conversation": "conversation_id", "run": "run_id", "workflow": "workflow_id", "command": "request_id"}[kind])
        key = (kind, record.scope, record_id)
        if key in self.rows:
            raise OrchestrationError("DUPLICATE_RECORD")
        self.rows[key] = deepcopy(record)

    async def save(self, kind, record, expected_revision, uow):
        record_id = getattr(record, {"conversation": "conversation_id", "run": "run_id", "workflow": "workflow_id", "command": "request_id"}[kind])
        key = (kind, record.scope, record_id)
        field = "state_revision" if kind == "conversation" else "revision"
        if key not in self.rows or getattr(self.rows[key], field) != expected_revision:
            raise OrchestrationError("REVISION_CONFLICT")
        record = deepcopy(record)
        setattr(record, field, expected_revision + 1)
        self.rows[key] = record
        return deepcopy(record)

    async def find_command(self, tenant_id, partner_client_id, external_request_id, uow):
        matches = [record for (kind, _, _), record in self.rows.items() if kind == "command" and
                   record.scope[0] == tenant_id and record.partner_client_id == partner_client_id and
                   record.external_request_id == external_request_id]
        return deepcopy(matches[0]) if matches else None

    async def find_binding(self, tenant_id, audience, uow):
        matches = [record for (kind, _, _), record in self.rows.items() if kind == "workflow" and
                   record.scope[0] == tenant_id and record.audience["partner_client_id"] == audience["partner_client_id"] and
                   record.audience["external_user_id"] == audience["external_user_id"] and
                   (record.audience["external_ticket_id"] == audience["external_ticket_id"] or
                    record.audience["external_conversation_id"] == audience["external_conversation_id"])]
        if len(matches) > 1:
            raise OrchestrationError("WORKFLOW_BINDING_MISMATCH")
        return deepcopy(matches[0]) if matches else None


class FakeCatalog:
    def __init__(self):
        self.items, self.versions, self.deployments = [], {}, {}
        for name, capability in (("Plan", "plan"), ("Hotel", "hotel"), ("Car", "car"),
                                 ("Calculator", "calculate"), ("Technical", "technical")):
            self.add(name, capability)

    def add(self, name, capability, version="v3", batch="A", scope=KEY):
        version_id = f"{name}-{version}"
        manifest = {"agent": {"name": name, "capabilities": [capability],
                              "system_prompt": f"{name} prompt {version}",
                              "model_config": {"model": f"model-{version}"},
                              "context_config": {"workspace": f"workspace-{name}"}}}
        item = {"agent_id": name, "version_id": version_id, "deployment_id": name,
                "manifest_hash": version_id, "capabilities": [capability], "scope": scope,
                "status": "published", "batch_id": batch, "name": name}
        self.items = [x for x in self.items if x["agent_id"] != name] + [item]
        self.versions[version_id] = {"agent_id": name, "scope": scope, "manifest": manifest,
                                     "manifest_hash": version_id}
        self.deployments[name] = {"agent_id": name, "scope": scope, "status": "active",
                                 "active_version_id": version_id}

    async def list_candidates(self, scope, capabilities):
        return {"items": deepcopy(self.items), "catalog_revision": "revision-1"}

    async def get_version(self, scope, version_id):
        return deepcopy(self.versions.get(version_id))

    async def get_deployment(self, scope, deployment_id):
        return deepcopy(self.deployments.get(deployment_id))


class FakeRuntimeHooks:
    def __init__(self, repository):
        self.repository = repository
        self.groups, self.deliveries = {}, {}
        self.fail = False

    async def provision(self, scope, run, *, idempotency_key):
        assert not self.repository.in_transaction
        binding = {"group_id": run.group_id, "leader_session_id": run.leader_session_id,
                   "members": [{k: m[k] for k in ("agent_id", "version_id", "session_id", "manifest_hash")}
                               for m in run.members]}
        self.groups.setdefault(idempotency_key, deepcopy(binding))
        if self.fail:
            raise TimeoutError("test transport loss after provisioning")
        return deepcopy(self.groups[idempotency_key])

    async def send(self, scope, group_id, session_id, task, *, idempotency_key):
        assert not self.repository.in_transaction
        self.deliveries.setdefault(idempotency_key, (group_id, session_id, deepcopy(task)))
        return {"delivered": True}
