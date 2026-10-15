"""Builder Phase-B public exports; composition stays with Foundation."""

from ._protocol_validation import ProtocolBuildValidator
from ._requirements import (
    AgentBehaviorContract,
    ExtractionError,
    ExtractionResult,
    RequirementExtractor,
)
from ._service import ProposalService
from .async_capabilities._models import BuildProposal, ProtocolReadiness
from .async_capabilities._protocol_adapter import (
    RegistryCapabilitySelector,
    RegistryProtocolReadiness,
)
from .async_capabilities._selector import CapabilitySelector

__all__ = [
    "AgentBehaviorContract",
    "BuildProposal",
    "CapabilitySelector",
    "ExtractionError",
    "ExtractionResult",
    "ProposalService",
    "ProtocolBuildValidator",
    "ProtocolReadiness",
    "RegistryCapabilitySelector",
    "RegistryProtocolReadiness",
    "RequirementExtractor",
]
