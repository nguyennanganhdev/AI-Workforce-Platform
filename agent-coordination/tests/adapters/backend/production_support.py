"""Synthetic authority/transport/proofs; never production integration evidence."""
import base64
import copy
import hashlib
import hmac
import json

from adapters.backend.client import BackendClient, HttpResponse
from adapters.backend.messages import fingerprint
from adapters.reception.authentication import HmacSourceAuthentication, SourceProof
from backend.support import CONTEXT, Headers, Validator

KEY = b"test-only-key-not-for-production-12345"


def proof(message, *, purpose="reception", **changes):
    scope = message.get("context", message)
    keys = (("tenant_id", "aggregate_id") if purpose == "event"
            else ("tenant_id", "workspace_id", "ticket_id", "ticket_generation"))
    claims = dict(version="1", issuer="test-issuer", audience="coordination", purpose=purpose,
                  subject="test-subject", issued_at=1000, expires_at=1100,
                  fingerprint=fingerprint(message), scope={key: scope[key] for key in keys})
    claims.update(changes)
    encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    signature = hmac.new(KEY, encoded.encode(), hashlib.sha256).hexdigest()
    return SourceProof(encoded + "." + signature)


def authentication():
    return HmacSourceAuthentication(keys={"test-issuer": KEY}, audience="coordination",
        header="X-Test-Source-Proof", purposes={"reception", "event", "tool"}, clock=lambda: 1050)


class ContractTransport:
    def __init__(self, response):
        self.response, self.calls, self.failure = response, [], None

    async def post(self, url, *, headers, body, timeout):
        wire = json.loads(body)
        self.calls.append((url, dict(headers), copy.deepcopy(wire)))
        if self.failure:
            raise self.failure
        data = self.response(wire)
        identity = next(key for key in ("request_id", "message_id", "event_id") if key in wire)
        return HttpResponse(200, json.dumps({identity: wire[identity], "status": "completed", "data": data}).encode())


def contract_client(transport, *, validator=None, observer=None):
    operations = {"authority.inspect", "authority.authorize", "operation.lookup", "event.verify",
                  "tool.grant.verify", "tool.execute", "business.contribution"}
    return BackendClient(base_url="https://test.invalid", routes={op: "/test/" + op for op in operations},
        transport=transport, headers=Headers(), validator=validator or Validator(), observer=observer)


def callback():
    return dict(request_id="tool-1", idempotency_key="tool-1", correlation_id="conversation-1",
                context=dict(CONTEXT), tool="work_order.lookup", input={"id": "work-1"},
                agent_version_id="agent-v1", task_id="task-1", run_id="agent-run-1")
