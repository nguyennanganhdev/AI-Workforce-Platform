import asyncio

import httpx

from src.adapters.backend import BackendSessionResolver, SessionResolverConfig


def test_session_resolver_validates_authoritative_snapshot():
    captured = {}

    def handler(request):
        captured["authorization"] = request.headers["Authorization"]
        return httpx.Response(
            200,
            request=request,
            json={
                "channel_id": "channel-1",
                "reception_session_id": "session-1",
                "file_references": [
                    {
                        "file_id": "file-1",
                        "source_message_id": "message-1",
                        "linked_to_ticket": False,
                    }
                ],
            },
        )

    async def scenario():
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://backend.test"
        )
        resolver = BackendSessionResolver(
            SessionResolverConfig(
                base_url="https://backend.test", service_token="service-token"
            ),
            client,
        )
        result = await resolver({"tenantId": "tenant-1"})
        await client.aclose()
        return result

    result = asyncio.run(scenario())
    assert result["file_references"][0]["file_id"] == "file-1"
    assert captured["authorization"] == "Bearer service-token"
