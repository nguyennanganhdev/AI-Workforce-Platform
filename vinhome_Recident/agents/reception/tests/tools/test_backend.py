import asyncio

import httpx
import pytest
from src.tools.backend import BackendToolConfig, BackendToolPort, ToolContractError
from tool_fixtures import case, request


def run(coro):
    return asyncio.run(coro)


def config(**changes):
    return BackendToolConfig(
        base_url="https://backend.test",
        service_token="service-test",
        **changes,
    )


def test_update_incident_deduplicates_files_and_retries_same_request():
    captured = []
    value, output = case("update_ticket_incident")
    value["incident"]["file_ids"] = ["file-1", "file-1", "file-2"]

    def handler(req):
        captured.append((req.headers["Idempotency-Key"], req.content))
        if len(captured) == 1:
            return httpx.Response(503, request=req)
        return httpx.Response(
            200,
            request=req,
            json={
                "kind": "success",
                "value": output,
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://backend.test"
    )
    port = BackendToolPort(config(), client)
    result = run(
        port.invoke(
            request(
                "update_ticket_incident",
                value,
            )
        )
    )
    run(client.aclose())
    assert result["kind"] == "success"
    assert len(captured) == 2
    assert captured[0] == captured[1]


def test_append_requires_backend_file_link_confirmation():
    value, output = case("append_ticket_information")
    output["linked_file_ids"] = []

    def handler(req):
        return httpx.Response(
            200,
            request=req,
            json={"kind": "success", "value": output},
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://backend.test"
    )
    port = BackendToolPort(config(), client)
    with pytest.raises(ToolContractError, match="FILE_LINK_CONFIRMATION_MISSING"):
        run(port.invoke(request("append_ticket_information", value)))
    run(client.aclose())


def test_timeout_returns_unknown_without_changing_idempotency_key():
    keys = []

    def handler(req):
        keys.append(req.headers["Idempotency-Key"])
        raise httpx.ReadTimeout("timeout", request=req)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://backend.test"
    )
    port = BackendToolPort(config(max_attempts=2), client)
    result = run(port.invoke(request("append_ticket_information")))
    run(client.aclose())
    assert result == {
        "kind": "failure",
        "code": "BACKEND_RESPONSE_UNKNOWN",
        "retryable": False,
        "outcome": "unknown",
    }
    assert keys == ["stable-key", "stable-key"]
