"""Builder Phase-B public exports; composition stays with Foundation."""

from ._requirements import ExtractionError, ExtractionResult, RequirementExtractor
from ._service import ProposalService
from .async_capabilities._models import BuildProposal, ProtocolReadiness
from .async_capabilities._selector import CapabilitySelector
from .async_capabilities._protocol_adapter import (
    RegistryProtocolReadiness,
    RegistryCapabilitySelector,
)
from ._protocol_validation import ProtocolBuildValidator

__all__ = [
    "BuildProposal",
    "CapabilitySelector",
    "ExtractionError",
    "ExtractionResult",
    "ProposalService",
    "ProtocolReadiness",
    "RequirementExtractor",
    "RegistryProtocolReadiness",
    "RegistryCapabilitySelector",
    "ProtocolBuildValidator",
]
