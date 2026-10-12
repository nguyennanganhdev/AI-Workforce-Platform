"""D4 composition boundaries owned by the final integration lane."""

import json
import unittest
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from agentscope.app.workforce.contracts import Scope
from agentscope.app.workforce.integrations.async_runtime import (
    PublishedLeaderBootstrapResolver,
    ReleaseAwareEvaluationJobService,
    SqlWorkflowVersionUsageReader,
    TransactionalReleaseValidator,
    create_release_router,
)
from agentscope.app.workforce.lifecycle.async_evaluation import lifecycle_suite
from agentscope.app.workforce.lifecycle.releases import ReleaseContext
from tests.workforce.lifecycle.async_evaluation.test_phase_b import (
    fixture as evaluation_fixture,
)
from tests.workforce.lifecycle.async_evaluation.test_phase_b import (
    seal as seal_evaluation,
)

SCOPE = Scope(
    tenant_id="tenant-1",
    domain_id="domain-1",
    area_id="area-1",
    manager_account_id="manager-1",
)


class _Identity:
    def __init__(self) -> None:
        self.principals = []

    async def resolve_manager(self, principal):
        self.principals.append(principal)
        return SCOPE


class _Releases:
    def __init__(self) -> None:
        self.publishes = []
        self.rollbacks = []
        self.availability_changes = []

    async def publish_selected(self, scope, selections, context, command_id):
        self.publishes.append((scope, selections, context, command_id))
        return ("version-1",)

    async def rollback(
        self,
        scope,
        agent_id,
        version_id,
        expected_revision,
        context,
        command_id,
    ):
        self.rollbacks.append(
            (
                scope,
                agent_id,
                version_id,
                expected_revision,
                context,
                command_id,
            )
        )
        return version_id

    async def set_availability(
        self, scope, agent_id, expected_revision, *, archived, enabled
    ):
        self.availability_changes.append(
            (scope, agent_id, expected_revision, archived, enabled)
        )
        return expected_revision + 1

    async def list_candidates(self, scope, capabilities):
        del scope, capabilities
        return ()

    async def get_version(self, scope, version_id):
        del scope
        return _Dumpable({"version_id": version_id})

    async def get_deployment(self, scope, agent_id):
        del scope
        return {"deployment_id": agent_id, "active_version_id": "version-1"}

    async def retention_references(self, scope, version_id, usage):
        return await usage.references(scope, version_id)


class _Dumpable:
    def __init__(self, value) -> None:
        self.value = value

    def model_dump(self, *, mode):
        del mode
        return self.value


class _Usage:
    async def references(self, scope, version_id):
        del scope
        return ("workflow:workflow-1", f"version:{version_id}")


class ReleaseRouterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.identity = _Identity()
        self.releases = _Releases()

        async def manager():
            return {"verified_principal": "manager-token"}

        self.context = ReleaseContext(
            runtime_profile={"model_ref": "server-model"},
            test_context={"audience": "server-suite"},
            suite=lifecycle_suite(),
        )
        app = FastAPI()
        app.include_router(
            create_release_router(
                self.releases,
                self.identity,
                manager,
                lambda scope: self.context,
                _Usage(),
            )
        )
        self.client = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_publish_resolves_scope_and_context_on_server(self) -> None:
        response = await self.client.post(
            "/workforce/v1/manager/agent-releases/publish",
            json={
                "command_id": "publish-1",
                "selections": [
                    {
                        "draft_id": "draft-1",
                        "draft_revision": 1,
                        "evaluation_id": "evaluation-1",
                        "deployment_revision": 0,
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"version_ids": ["version-1"]})
        scope, _, context, command_id = self.releases.publishes[0]
        self.assertEqual(scope, SCOPE)
        self.assertEqual(context, self.context)
        self.assertEqual(command_id, "publish-1")
        self.assertEqual(
            self.identity.principals,
            [{"verified_principal": "manager-token"}],
        )

    async def test_publish_rejects_client_scope_or_context(self) -> None:
        response = await self.client.post(
            "/workforce/v1/manager/agent-releases/publish",
            json={
                "command_id": "publish-2",
                "selections": [
                    {
                        "draft_id": "draft-1",
                        "draft_revision": 1,
                        "evaluation_id": "evaluation-1",
                        "deployment_revision": 0,
                    }
                ],
                "scope": SCOPE.model_dump(mode="json"),
                "context": self.context.model_dump(mode="json"),
            },
        )
        self.assertEqual(response.status_code, 422, response.text)
        self.assertFalse(self.releases.publishes)

    async def test_control_and_read_routes_use_manager_scope(self) -> None:
        rollback = await self.client.post(
            "/workforce/v1/manager/agent-releases/agent-1/rollback",
            json={
                "command_id": "rollback-1",
                "version_id": "version-0",
                "expected_revision": 2,
            },
        )
        availability = await self.client.patch(
            "/workforce/v1/manager/agent-releases/agent-1/availability",
            json={
                "expected_revision": 3,
                "archived": True,
                "enabled": False,
            },
        )
        catalog = await self.client.get(
            "/workforce/v1/manager/agent-releases",
            params=[("capability", "hotel"), ("capability", "booking")],
        )
        version = await self.client.get(
            "/workforce/v1/manager/agent-releases/versions/version-1"
        )
        deployment = await self.client.get(
            "/workforce/v1/manager/agent-releases/deployments/agent-1"
        )
        references = await self.client.get(
            "/workforce/v1/manager/agent-releases/versions/version-1/references"
        )

        self.assertEqual(rollback.json(), {"version_id": "version-0"})
        self.assertEqual(availability.json(), {"agent_id": "agent-1", "revision": 4})
        self.assertEqual(catalog.json(), {"items": []})
        self.assertEqual(version.json(), {"version_id": "version-1"})
        self.assertEqual(deployment.json()["deployment_id"], "agent-1")
        self.assertEqual(
            references.json()["references"],
            ["workflow:workflow-1", "version:version-1"],
        )
        self.assertEqual(self.releases.rollbacks[0][0], SCOPE)
        self.assertEqual(self.releases.rollbacks[0][4], self.context)
        self.assertEqual(
            self.releases.availability_changes,
            [(SCOPE, "agent-1", 3, True, False)],
        )


class _SeedResolver:
    async def resolve(self, scope, actor, audience, uow):
        del scope, actor, audience, uow
        return {
            "leader_agent_id": "leader-1",
            "leader_version_id": "version-1",
            "group_id": "group-1",
            "session_ref": "session-1",
            "shared_state_ref": "state-1",
            "pattern": "interactive",
            "published_read_only": False,
        }


class _Catalog:
    def __init__(self, active_version_id="version-1") -> None:
        self.active_version_id = active_version_id

    async def get_deployment(self, scope, agent_id, uow=None):
        del scope, agent_id, uow
        return {
            "active_version_id": self.active_version_id,
            "archived": False,
            "enabled": True,
        }

    async def get_version(self, scope, version_id, uow=None):
        del scope, version_id, uow
        return type("Version", (), {"agent_id": "leader-1"})()


class PublishedBootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def test_current_published_leader_is_accepted(self) -> None:
        resolver = PublishedLeaderBootstrapResolver(_SeedResolver(), _Catalog())
        seed = await resolver.resolve(SCOPE, object(), object(), object())
        self.assertEqual(seed["leader_version_id"], "version-1")

    async def test_stale_leader_head_is_rejected(self) -> None:
        resolver = PublishedLeaderBootstrapResolver(
            _SeedResolver(), _Catalog("version-2")
        )
        with self.assertRaisesRegex(PermissionError, "NOT_CURRENT"):
            await resolver.resolve(SCOPE, object(), object(), object())


class _Protocols:
    def __init__(self, protocol) -> None:
        self.protocol = protocol
        self.calls = []

    async def get_current(self, scope, tool_version_id, uow=None, *, for_update=False):
        self.calls.append((scope, tool_version_id, uow, for_update))
        return self.protocol, True


class TransactionalValidatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_release_dependencies_share_the_publish_uow(self) -> None:
        sample = evaluation_fixture()
        uow = object()
        calls = []

        async def tool_resolver(scope, tool_version_id, received_uow):
            calls.append(("tool", scope, tool_version_id, received_uow))
            return sample["tools"][0]

        async def policy_resolver(scope, policy_ref, received_uow):
            calls.append(("policy", scope, policy_ref, received_uow))
            return scope, policy_ref, "pta-phase-a-1", sample["policy"]

        protocols = _Protocols(sample["protocols"][0])
        validator = TransactionalReleaseValidator(
            protocols,
            tool_resolver,
            policy_resolver,
        )
        report, dependencies = await validator.validate(
            sample["scope"], sample["manifest"], uow
        )

        self.assertTrue(report.valid)
        self.assertEqual(
            calls,
            [
                ("tool", sample["scope"], "repair-v1", uow),
                ("policy", sample["scope"], "policy-v1", uow),
            ],
        )
        self.assertEqual(
            protocols.calls,
            [(sample["scope"], "repair-v1", uow, True)],
        )
        self.assertEqual(dependencies["policy_ref"], "policy-v1")


class _AtomicUow:
    def __init__(self) -> None:
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        del exc_type, exc, traceback

    async def commit(self):
        self.commits += 1


class _EvaluationRepository:
    def __init__(self, uow) -> None:
        self.uow = uow
        self.registrations = []

    def uows(self):
        return self.uow

    async def register(self, scope, evaluation_id, frozen, uow):
        self.registrations.append((scope, evaluation_id, frozen, uow))


class _CandidateStager:
    def __init__(self) -> None:
        self.calls = []

    async def stage_candidate(self, scope, frozen, expected_revision=None, uow=None):
        self.calls.append((scope, frozen, expected_revision, uow))


class _EvaluationJobs:
    def __init__(self) -> None:
        self.calls = []

    async def enqueue(self, scope, job_type, payload, key, uow):
        self.calls.append((scope, job_type, payload, key, uow))
        return "job-1"


class ReleaseAwareEvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def test_evaluation_candidate_and_job_share_one_uow(self) -> None:
        sample = evaluation_fixture()
        frozen = seal_evaluation(sample)
        uow = _AtomicUow()
        repository = _EvaluationRepository(uow)
        jobs = _EvaluationJobs()
        releases = _CandidateStager()
        service = ReleaseAwareEvaluationJobService(repository, jobs, releases)

        job_id = await service.enqueue(
            sample["scope"],
            "evaluation-1",
            frozen,
            expected_candidate_revision=2,
        )

        self.assertEqual(job_id, "job-1")
        self.assertEqual(repository.registrations[0][3], uow)
        self.assertEqual(releases.calls[0][2:], (2, uow))
        self.assertEqual(jobs.calls[0][4], uow)
        self.assertEqual(uow.commits, 1)


class _Rows:
    def __init__(self, rows) -> None:
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class _UsageUow:
    def __init__(self, batches) -> None:
        self.batches = list(batches)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        del exc_type, exc, traceback

    async def execute(self, statement):
        del statement
        return _Rows(self.batches.pop(0))


class VersionUsageTests(unittest.IsolatedAsyncioTestCase):
    async def test_reader_reports_exact_workflow_and_checkpoint_pins(self) -> None:
        root = Path(__file__).resolve().parents[3]
        samples = json.loads(
            (
                root / "docs/workforce/handoffs/phan-huy-hoang/phase_a/samples.json"
            ).read_text(encoding="utf-8")
        )["models"]
        aggregate = {
            "workflow": samples["WorkflowRecord"],
            "checkpoint": samples["WorkflowCheckpoint"],
            "pattern": "interactive",
            "published_read_only": False,
        }
        batches = [
            [{"id": "workflow-A", "payload": aggregate}],
            [{"id": "checkpoint-A-1", "payload": samples["WorkflowCheckpoint"]}],
            [
                {
                    "id": "call-A",
                    "payload": {"request": {"version_id": "agent-version-1"}},
                }
            ],
        ]
        reader = SqlWorkflowVersionUsageReader(lambda: _UsageUow(batches))

        references = await reader.references(SCOPE, "agent-version-1")

        self.assertEqual(
            references,
            (
                "checkpoint:checkpoint-A-1",
                "tool_call:call-A",
                "workflow:workflow-A",
            ),
        )


if __name__ == "__main__":
    unittest.main()
