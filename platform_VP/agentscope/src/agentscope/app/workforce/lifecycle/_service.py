"""Lifecycle composition exposes Draft/Batch/Reuse/PublishedCatalog ports."""

from typing import Any, Callable, Dict, Optional
from copy import deepcopy

from ..contracts import EvaluationRunnerPort, IdentityPort, JobPort
from ._agent_catalog import CatalogMixin
from ._batches import BatchMixin
from ._drafts import DraftMixin
from ._evaluations import EvaluationMixin
from ._judges import QualityJudgePort
from ._release import ReleaseMixin
from ._repository import LifecycleRepository
from ._reuse import ReuseMixin
from ._settings import SettingsMixin
from ._suites import SuiteCatalog
from ._validation import ManifestValidator
from ._versions import VersionMixin, VersionUsagePort


class LifecycleService(
    DraftMixin,
    BatchMixin,
    ReuseMixin,
    CatalogMixin,
    EvaluationMixin,
    ReleaseMixin,
    SettingsMixin,
    VersionMixin,
):
    def __init__(
        self,
        repository: LifecycleRepository,
        validator: ManifestValidator,
        identity: IdentityPort,
        jobs: JobPort,
        runner: EvaluationRunnerPort,
        suites: SuiteCatalog,
        usage: VersionUsagePort,
        runtime_profile: Dict[str, Any],
        peer_fixtures: Dict[str, Any],
        redact: Callable[[Dict[str, Any]], Dict[str, Any]],
        judge: Optional[QualityJudgePort] = None,
    ) -> None:
        self.repository = repository
        self.validator = validator
        self.identity = identity
        self.jobs = jobs
        self.runner = runner
        self.suites = suites
        self.usage = usage
        self.runtime_profile = deepcopy(runtime_profile)
        self.peer_fixtures = deepcopy(peer_fixtures)
        self.redact = redact
        self.judge = judge
