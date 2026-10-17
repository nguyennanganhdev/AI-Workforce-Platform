"""Test-only controlled faults; reuse the existing C3 SQL consumer seam."""

import asyncio
import unittest

from agentscope.app.workforce.builder import ProposalService, RequirementExtractor
from agentscope.app.workforce.contracts import WorkforceContractError
from tests.workforce.builder.async_capabilities.fakes import Model, Reuse
from tests.workforce.builder.async_capabilities.test_phase_a import FakeDrafts
from tests.workforce.builder.phase_c.test_integration import BuilderProtocolTests


class Gate:
    """Pause a public port call at an observable point, with a bounded wait."""

    def __init__(self):
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def wait(self):
        self.entered.set()
        await asyncio.wait_for(self.release.wait(), 2)

    async def reached(self):
        await asyncio.wait_for(self.entered.wait(), 2)


class GatedModel(Model):
    def __init__(self, outputs, gate):
        super().__init__(outputs)
        self.gate = gate

    async def generate_structured_output(self, *args, **kwargs):
        await self.gate.wait()
        return await super().generate_structured_output(*args, **kwargs)


class ControlledReuse(Reuse):
    """Canonical contract double, never a DB writer or identity reservation."""

    def __init__(self, scope, **kwargs):
        super().__init__(scope, **kwargs)
        self.candidates = None
        self.validations = []
        self.conflict = None
        self.gate = None
        self.find_failure = None

    async def find_candidates(self, scope, business_profile, include_drafts=True):
        if self.find_failure:
            raise self.find_failure
        check = await super().find_candidates(scope, business_profile, include_drafts)
        return (
            check.model_copy(update={"candidates": self.candidates})
            if self.candidates is not None
            else check
        )

    async def validate_decisions(
        self, scope, requirements, reuse_decisions, expected_catalog_revision
    ):
        self.validations.append(
            (scope, requirements, reuse_decisions, expected_catalog_revision)
        )
        if self.gate:
            await self.gate.wait()
        if self.conflict:
            code, self.conflict = self.conflict, None
            raise WorkforceContractError(code, "Controlled canonical conflict")
        await super().validate_decisions(
            scope, requirements, reuse_decisions, expected_catalog_revision
        )


async def write_after_validation(hook, scope, item, manifest, drafts):
    """Example caller in tests only: invalid reports/exceptions stop the handoff."""
    report, evidence = await hook.validate(scope, item, manifest)
    if not report.valid:
        raise ValueError("Draft validation blocked")
    await drafts.create_draft(scope, manifest, item.reuse_decision)
    return evidence


class BuilderCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Compose existing owned test helpers without inheriting their 26 tests.
        self.seam = BuilderProtocolTests()
        self.seam.setUp()
        self.addCleanup(self.seam.doCleanups)
        self.scope = self.seam.scope
        self.fixture = self.seam.fixture
        self.catalog = self.seam.catalog
        self.selector = self.seam.selector
        self.port = self.seam.port
        self.readiness = self.seam.readiness

    def service(self, requirements=None, *, reuse=None, model=None, selector=None):
        return ProposalService(
            RequirementExtractor(
                model
                or Model([self.fixture.build_output(requirements or self.fixture.sync)])
            ),
            selector or self.selector,
            reuse or ControlledReuse(self.scope),
        )

    async def prepare(self, service, message_id="message", **kwargs):
        return await service.prepare(self.scope, "Build agent", message_id, **kwargs)

    async def start(self, coroutine):
        started = asyncio.Event()

        async def run():
            started.set()
            return await coroutine

        task = asyncio.create_task(run())

        async def cleanup():
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        self.addAsyncCleanup(cleanup)
        await asyncio.wait_for(started.wait(), 2)
        return task

    async def finish(self, *tasks):
        return await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 3)

    def drafts(self):
        return FakeDrafts()
