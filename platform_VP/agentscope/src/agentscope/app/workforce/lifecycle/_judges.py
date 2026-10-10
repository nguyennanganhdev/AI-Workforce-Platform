"""Optional answer-quality judge runs only after deterministic gates pass."""

from typing import Any, Dict, Mapping, Protocol

from ..contracts import EvaluationCaseResult, EvaluationSnapshot, Scope


class QualityJudgePort(Protocol):
    async def judge(
        self,
        scope: Scope,
        snapshot: EvaluationSnapshot,
        golden_case: Mapping[str, Any],
        result: EvaluationCaseResult,
    ) -> Dict[str, Any]: ...
