# -*- coding: utf-8 -*-
"""Remove one PHH workflow guard at a time in memory; require a test witness.

No source files, shared classes or services are modified by this experiment.
Only ValueError guards are mutated, not every possible implementation defect.
"""

import ast
from copy import deepcopy
from pathlib import Path
import sys
import types
from typing import Any

from pydantic import ValidationError

from fixtures import phase_a_samples
from test_phase_a import NEGATIVE_CASES, MODELS, mutate


SOURCE = (
    Path(__file__).resolve().parents[4]
    / "src/agentscope/app/workforce/orchestration/workflows/phase_a.py"
)


def witnesses() -> list[tuple[str, str, dict[str, Any]]]:
    cases = []
    for case in NEGATIVE_CASES:
        if case["model"] not in {
            "WorkflowTrigger",
            "WorkflowCheckpoint",
            "CommandClaimResult",
            "PinnedRuntimeContext",
            "RuntimeTurnResult",
        }:
            continue
        sample = deepcopy(phase_a_samples()["models"][case["model"]])
        mutate(sample, case)
        cases.append((case["id"], case["model"], sample))
    for label, model, path in (
        ("duplicate-messages", "RuntimeTurnResult", ("result", "messages")),
        ("duplicate-protocol", "WorkflowCheckpoint", ("protocol_pins",)),
        (
            "duplicate-workflow-pins",
            "PinnedRuntimeContext",
            ("workflow", "version_pins"),
        ),
    ):
        sample = deepcopy(phase_a_samples()["models"][model])
        node = sample
        for field in path[:-1]:
            node = node[field]
        node[path[-1]] *= 2
        cases.append((label, model, sample))
    return cases


class RemoveGuard(ast.NodeTransformer):
    def __init__(self, line: int) -> None:
        self.line = line

    def visit_Raise(self, node: ast.Raise) -> ast.AST:
        if node.lineno == self.line:
            return ast.copy_location(ast.Pass(), node)
        return node


def run_mutation_checks() -> dict[str, Any]:
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
        and node.exc.func.id == "ValueError"
    ]
    cases = witnesses()
    for label, model, sample in cases:
        try:
            MODELS[model].model_validate(deepcopy(sample))
        except ValidationError:
            continue
        raise AssertionError(f"Invalid baseline witness: {label}")
    outcomes = []
    for index, line in enumerate(sorted(lines)):
        name = (
            "agentscope.app.workforce.orchestration.workflows."
            f"_phase_a_guard_mutant_{index}"
        )
        module = types.ModuleType(name)
        module.__package__ = "agentscope.app.workforce.orchestration.workflows"
        sys.modules[name] = module
        try:
            mutant = RemoveGuard(line).visit(deepcopy(tree))
            ast.fix_missing_locations(mutant)
            exec(compile(mutant, str(SOURCE), "exec"), module.__dict__)
            detected = []
            for label, model, sample in cases:
                try:
                    getattr(module, model).model_validate(deepcopy(sample))
                except ValidationError:
                    continue
                detected.append(label)
            outcomes.append(
                dict(
                    mutation=f"remove-guard-{index + 1}",
                    line=line,
                    detected_by=detected,
                    survived=not bool(detected),
                )
            )
        finally:
            del sys.modules[name]
    return dict(
        scope="PHH workflow ValueError guards only; in-memory mutations",
        count=len(outcomes),
        killed=sum(not item["survived"] for item in outcomes),
        survivors=[item for item in outcomes if item["survived"]],
        outcomes=outcomes,
    )
