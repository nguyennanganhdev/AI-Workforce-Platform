"""Export owned schema/demo fixtures from real proposal logic and test adapters."""

import asyncio
import json
from pathlib import Path

from agentscope.app.workforce.builder import ProposalService, RequirementExtractor
from agentscope.app.workforce.builder.async_capabilities import BuildRequirements
from tests.workforce.builder.async_capabilities.fakes import Model, Reuse, tool
from tests.workforce.builder.async_capabilities.test_phase_b import PhaseBTests


async def main():
    suite = PhaseBTests()
    suite.setUp()
    fixtures = {}
    for name, requirements, selector, reuse in (
        ("ready", suite.sync, suite.selector(), Reuse(suite.scope)),
        (
            "reused",
            suite.sync,
            suite.selector(),
            Reuse(suite.scope, match="same_business"),
        ),
        (
            "missing",
            suite.sync,
            suite.selector(tools=(tool(available=False),)),
            Reuse(suite.scope),
        ),
        (
            "tracking",
            suite.tracking,
            suite.selector(suite.protocol()),
            Reuse(suite.scope, match="same_business", fully_covered=False),
        ),
        (
            "query_only",
            suite.tracking,
            suite.selector(
                suite.protocol(events=False, query=True),
                tools=(
                    tool("create", "external_operation"),
                    tool("status_query", version="query-v1"),
                ),
            ),
            Reuse(suite.scope),
        ),
    ):
        model = Model([suite.build_output(requirements)])
        service = ProposalService(RequirementExtractor(model), selector, reuse)
        result = await service.prepare(
            suite.scope, "TEST ONLY tạo agent", "fixture-message"
        )
        fixtures[name] = result.model_dump(mode="json")
    root = Path(__file__).resolve().parents[4]
    handoff = root / "docs/workforce/handoffs/bui-huu-nghia"
    (handoff / "phase-a.schema.json").write_text(
        json.dumps(BuildRequirements.model_json_schema(), indent=2) + "\n",
        encoding="utf-8",
    )
    fixture_path = (
        root
        / "examples/web_ui/frontend/src/features/workforce/builder/tests/proposals.json"
    )
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(
        json.dumps(fixtures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Exported Builder schema and five TEST ONLY proposal fixtures")


if __name__ == "__main__":
    asyncio.run(main())
