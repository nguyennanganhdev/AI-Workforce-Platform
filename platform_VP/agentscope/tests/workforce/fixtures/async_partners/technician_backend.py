"""
TEST ONLY provider backend with retryable event IDs and injected transport.
"""


class ProviderBackend:
    """Credential purpose/namespace is separate from CustomerBackend."""

    def __init__(self, client, headers):
        self.client, self.headers = client, headers
        self.receipts = {}

    async def send(self, envelope):
        response = await self.client.post(
            "/workforce/v1/provider/job-events",
            headers=self.headers,
            json=envelope,
        )
        response.raise_for_status()
        assert response.status_code == 202
        receipt = response.json()
        self.receipts[envelope["external_event_id"]] = receipt["receipt_id"]
        return receipt

    async def receipt(self, event_id):
        response = await self.client.get(
            f"/workforce/v1/provider/event-receipts/{self.receipts[event_id]}",
            headers=self.headers,
        )
        response.raise_for_status()
        return response.json()
