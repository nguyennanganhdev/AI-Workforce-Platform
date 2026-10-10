"""PTA-16 published versions survive deployment changes and waiting/restart."""

from agentscope.app.workforce.lifecycle._models import (
    AgentDefinition,
    LifecycleError,
)
from tests.workforce.lifecycle._fakes import Harness, scope
from tests.workforce.lifecycle.test_lifecycle import SQLLifecycleCase


class VersionPinTests(SQLLifecycleCase):
    async def test_waiting_pin_rejects_policy_or_resource_reference_drift(
        self,
    ) -> None:
        from tests.workforce.lifecycle._fakes import manifest
        from agentscope.app.workforce.contracts import ToolEffect

        self.harness.registry.effect = ToolEffect.EXTERNAL_OPERATION
        version, _ = await self.publish_draft(
            await self.harness.draft(manifest(external=True))
        )
        self.harness.policies.policy["timeout_behavior"] = "needs_attention"
        with self.assertRaisesRegex(LifecycleError, "AGENT_INCOMPATIBLE"):
            await self.service.check_continuation(scope(), version.version_id)
        self.assertEqual(await self.service.list_candidates(scope(), []), ())
        self.assertEqual(
            await self.service.get_version(scope(), version.version_id),
            version,
        )
        self.harness.policies.policy["timeout_behavior"] = "status_query"
        self.harness.resources.revision = 2
        with self.assertRaisesRegex(LifecycleError, "AGENT_INCOMPATIBLE"):
            await self.service.check_continuation(scope(), version.version_id)

    async def test_publish_and_rollback_do_not_change_existing_pin(
        self,
    ) -> None:
        first, _ = await self.publish_draft(await self.harness.draft())
        pinned = first.version_id
        fork = await self.service.fork_version(scope(), first.version_id)
        manifest = fork.manifest.model_copy(
            update={
                "spec": fork.manifest.spec.model_copy(
                    update={"system_prompt": "Version two prompt"}
                )
            }
        )
        changed = await self.service.update_draft(
            scope(),
            fork.draft_id,
            fork.revision,
            manifest,
            fork.reuse_decision,
        )
        second, _ = await self.publish_draft(changed)
        self.assertEqual(
            (await self.service.check_continuation(scope(), pinned)), first
        )
        self.assertNotEqual(second.version_id, first.version_id)
        deployment = await self.service.get_deployment(scope(), first.agent_id)
        await self.service.rollback(
            scope(),
            deployment.deployment_id,
            first.version_id,
            deployment.revision,
        )
        restarted = Harness(self.factory)
        self.assertEqual(
            (
                await restarted.service.check_continuation(
                    scope(), second.version_id
                )
            ),
            second,
        )
        self.assertEqual(
            (await restarted.service.list_candidates(scope(), []))[
                0
            ].version_id,
            first.version_id,
        )
        retention = await restarted.service.retention_info(
            scope(), second.version_id
        )
        self.assertFalse(retention["hard_delete_allowed"])
        self.assertEqual(
            retention["references"][0]["version_id"], second.version_id
        )
        diff = await self.service.diff_draft(scope(), fork.draft_id)
        self.assertEqual(diff[0]["path"], "/spec/system_prompt")

    async def test_archive_allows_pins_disable_and_revoke_block_resume(
        self,
    ) -> None:
        version, _ = await self.publish_draft(await self.harness.draft())
        agent = AgentDefinition.model_validate(
            await self.service.repository.get(
                scope(), "agents", version.agent_id
            )
        )
        archived = await self.service.set_availability(
            scope(), agent.agent_id, "archived", agent.revision
        )
        self.assertEqual(await self.service.list_candidates(scope(), []), ())
        self.assertEqual(
            await self.service.check_continuation(scope(), version.version_id),
            version,
        )
        disabled = await self.service.set_availability(
            scope(), agent.agent_id, "disabled", archived.revision
        )
        with self.assertRaisesRegex(LifecycleError, "CONTINUATION_BLOCKED"):
            await self.service.check_continuation(scope(), version.version_id)
        await self.service.set_availability(
            scope(), agent.agent_id, "revoked", disabled.revision
        )
        with self.assertRaisesRegex(LifecycleError, "CONTINUATION_BLOCKED"):
            await self.service.check_continuation(scope(), version.version_id)
        self.assertEqual(
            await self.service.get_version(scope(), version.version_id),
            version,
        )

    async def test_resume_revalidates_tool_and_manager(self) -> None:
        version, _ = await self.publish_draft(await self.harness.draft())
        self.harness.registry.available = False
        with self.assertRaisesRegex(LifecycleError, "AGENT_INCOMPATIBLE"):
            await self.service.check_continuation(scope(), version.version_id)
        self.harness.registry.available = True
        self.harness.identity.active = False
        with self.assertRaisesRegex(LifecycleError, "MANAGER_INACTIVE"):
            await self.service.check_continuation(scope(), version.version_id)

    async def test_rollback_rejects_other_identity_and_stale_revision(
        self,
    ) -> None:
        first, _ = await self.publish_draft(await self.harness.draft())
        from tests.workforce.lifecycle._fakes import manifest

        second, _ = await self.publish_draft(
            await self.harness.draft(manifest("Car", "car"))
        )
        with self.assertRaisesRegex(LifecycleError, "VERSION_OWNER_MISMATCH"):
            await self.service.rollback(
                scope(), first.agent_id, second.version_id, 1
            )
        with self.assertRaisesRegex(LifecycleError, "REVISION_CONFLICT"):
            await self.service.rollback(
                scope(), first.agent_id, first.version_id, 999
            )
