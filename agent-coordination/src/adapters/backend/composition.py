"""DEV-3 adapter factory with explicit capabilities, not a server."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping

from .approval_client import ApprovalClient
from .authority_client import BackendAuthority
from .business_client import BusinessClient, BusinessOperation
from .client import BackendClient, HeaderProvider, HttpTransport
from .contract_validator import PinnedContractValidator, SchemaPin
from .documented_contracts import AugmentedContractValidator, DocumentedContractValidator
from .event_verifier import BackendEventVerifier
from .http_transport import UrllibTransport
from .messages import ContractValidator
from .routes import operation_routes

if TYPE_CHECKING:
    from adapters.reception.reception_gateway import ReceptionGateway
    from adapters.tools.tool_client import ToolClient

# Validation dispatch keys, not fourteen wire schemas to publish.
FEATURES = {
    "reception": ({"reception.verify", "reception.send"},
                  {"reception_input", "reception_output", "reception_delivery", "reception_response", "reception_verified"}),
    "workflow": ({"approval.request", "approval.respond", "assignment.offer", "assignment.respond", "work.complete"},
                 {"request", "response"}),
    "events": ({"event.verify"}, {"event", "event_verification_response"}),
    "authority": ({"authority.inspect", "authority.authorize", "operation.lookup"},
                  {"authority_inspect_request", "authority_inspect_response", "authority_action_request",
                   "authority_authorize_response", "operation_lookup_response"}),
    "legacy": ({"reception.ticket", "reception.message", "reception.question", "reception.update",
                "completion.request", "completion.respond"}, {"request", "response"}),
}


@dataclass(frozen=True)
class AdapterBundle:
    backend: BackendClient
    gateway: ReceptionGateway | None
    approvals: ApprovalClient | None
    tools: ToolClient | None
    authority: BackendAuthority | None
    event_verifier: BackendEventVerifier | None
    business: BusinessClient


def build_adapters(*, origin: str, routes: Mapping[str, str], credentials: HeaderProvider,
                   reception_authentication=None, event_authentication=None,
                   validator: ContractValidator | None = None,
                   schema_pins: Mapping[str, SchemaPin] | None = None,
                   features: frozenset[str] = frozenset({"reception", "workflow"}),
                   transport: HttpTransport | None = None, timeout: float = 15,
                   business_operations: Mapping[str, BusinessOperation] | None = None,
                   legacy: bool = False, allow_http: bool = False, observer=None) -> AdapterBundle:
    from adapters.reception.reception_gateway import ReceptionGateway
    from adapters.tools.tool_client import ToolClient

    enabled = set(features)
    if legacy:
        enabled.add("legacy")
    if not enabled or not enabled <= FEATURES.keys():
        raise ValueError("unknown or empty adapter features")
    if "legacy" in enabled and not {"reception", "workflow"} <= enabled:
        raise ValueError("legacy requires reception and workflow")
    if "reception" in enabled and reception_authentication is None:
        raise ValueError("reception source authentication required")
    if "events" in enabled and event_authentication is None:
        raise ValueError("event source authentication required")
    if validator is not None and schema_pins is not None:
        raise ValueError("choose injected validator or schema pins")
    if validator is None:
        validator = DocumentedContractValidator()
        if schema_pins is not None:
            validator = AugmentedContractValidator(validator,
                PinnedContractValidator(schema_pins, required=set(schema_pins)))
    required_operations, required_kinds = set(), set()
    for feature in enabled:
        operations, kinds = FEATURES[feature]
        required_operations.update(operations)
        required_kinds.update(kinds)
    for spec in (business_operations or {}).values():
        required_operations.add(spec.operation)
        required_kinds.update({spec.request_schema, spec.response_schema})
    available = getattr(validator, "supported_kinds", None)
    if available is not None and not required_kinds <= available:
        raise ValueError("missing validators for enabled adapter features")
    backend = BackendClient(base_url=origin, routes=operation_routes(routes, required=required_operations),
        transport=transport or UrllibTransport(), headers=credentials, validator=validator,
        timeout=timeout, allow_http=allow_http, observer=observer)
    return AdapterBundle(
        backend,
        ReceptionGateway(backend, authentication=reception_authentication, timeout=timeout)
        if "reception" in enabled else None,
        ApprovalClient(backend) if "workflow" in enabled else None,
        ToolClient(backend) if "workflow" in enabled else None,
        BackendAuthority(backend) if "authority" in enabled else None,
        BackendEventVerifier(backend, authentication=event_authentication, timeout=timeout)
        if "events" in enabled else None,
        BusinessClient(backend, operations=business_operations or {}),
    )
