"""DEV-1 Authority implementation over explicitly configured service contracts.

The peer, not this adapter, implements business policy and atomic remote fences.
Room terminal reconciliation remains DEV-2's responsibility.
"""
from __future__ import annotations

import json

from .client import BackendClient
from .errors import AdapterError
from .messages import fingerprint, snapshot


class BackendAuthority:
    def __init__(self, backend: BackendClient) -> None:
        self._backend = backend

    @staticmethod
    def _request(state, action=None):
        state_wire = state.model_dump(mode="json", exclude_none=True)
        body = {"context": state_wire["context"], "state_version": state.version,
                "state_fingerprint": fingerprint(state_wire), "state": state_wire}
        if action is not None:
            action_wire = action.model_dump(mode="json", exclude_none=True)
            if action_wire["wire"].get("context", body["context"]) != body["context"]:
                raise AdapterError("scope_mismatch")
            body.update(action=action_wire, action_fingerprint=fingerprint(action_wire))
        # Deterministic identity for this READ/authorization lookup, not a new
        # mutation ID. The action and its original wire/key are never changed.
        body["request_id"] = "authority-" + fingerprint(body)
        return body

    @staticmethod
    def _bound(data, request):
        return (data.get("state_fingerprint") == request["state_fingerprint"]
                and ("action_fingerprint" not in request
                     or data.get("action_fingerprint") == request["action_fingerprint"]))

    async def inspect(self, state):
        from supervisor.models import AuthorityView, SupervisorError
        request = self._request(state)
        try:
            data = await self._backend.call_contract("authority.inspect", request,
                request_schema="authority_inspect_request", response_schema="authority_inspect_response")
            if set(data) != {"state_fingerprint", "view"} or not self._bound(data, request):
                raise ValueError()
            view = AuthorityView.model_validate_json(json.dumps(data["view"]), strict=True)
            if view.context != state.context or view.state_version != state.version:
                raise ValueError()
            return view
        except AdapterError as error:
            raise SupervisorError(error.code) from None
        except Exception:
            raise SupervisorError("invalid_authority_response") from None

    async def authorize_action(self, state, action) -> None:
        from supervisor.models import SupervisorError
        try:
            request = self._request(state, action)
            data = await self._backend.call_contract("authority.authorize", request,
                request_schema="authority_action_request", response_schema="authority_authorize_response")
            if (set(data) != {"state_fingerprint", "action_fingerprint", "allowed"}
                    or not self._bound(data, request) or data["allowed"] is not True):
                raise SupervisorError("action_not_authorized")
        except AdapterError as error:
            raise SupervisorError(error.code) from None

    async def reconcile(self, state, action):
        from supervisor.models import Reconciliation, SupervisorError
        if action.channel == "room":
            return Reconciliation(outcome="unknown")
        try:
            request = self._request(state, action)
            data = await self._backend.call_contract("operation.lookup", request,
                request_schema="authority_action_request", response_schema="operation_lookup_response")
            if not self._bound(data, request):
                raise ValueError()
            required = {"state_fingerprint", "action_fingerprint", "outcome"}
            outcome = data.get("outcome")
            if outcome == "unknown" and set(data) == required:
                return Reconciliation(outcome="unknown")
            if outcome == "not_applied" and set(data) == required | {"fenced", "fenced_action_id"}:
                if data["fenced"] is not True or data["fenced_action_id"] != action.action_id:
                    raise ValueError()
                return Reconciliation(outcome="not_applied")
            if outcome == "receipt" and set(data) == required | {"receipt", "wire_fingerprint"}:
                if data["wire_fingerprint"] != fingerprint(action.wire):
                    raise ValueError()
                reception = action.channel == "reception"
                identity, schema = (("message_id", "reception_response") if reception
                                    else ("request_id", "response"))
                # Canonical schema, identity and success/error guards are shared
                # with actual dispatch receipts; a lookup ACK is not the receipt.
                receipt = self._backend._receipt(snapshot(data["receipt"]), identity,
                                                action.action_id, schema)
                return Reconciliation(outcome="receipt", receipt=receipt)
            raise ValueError()
        except AdapterError as error:
            if error.code in {"timeout", "unavailable", "operation_not_configured", "not_found"}:
                return Reconciliation(outcome="unknown")
            raise SupervisorError(error.code) from None
        except Exception:
            raise SupervisorError("invalid_reconciliation") from None
