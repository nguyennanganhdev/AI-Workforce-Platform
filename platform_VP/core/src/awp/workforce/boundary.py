"""Bound JSON ingress before parsing; never log machine secrets or raw provider data."""
import json


class WorkforceBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/workforce/v1/") or scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            msg = await receive()
            if msg["type"] == "http.disconnect":
                return
            if msg["type"] != "http.request":
                continue
            size += len(msg.get("body", b""))
            if size > 262144:
                raw = json.dumps({"error": {"code": "PAYLOAD_TOO_LARGE", "message": "Payload exceeds 256 KiB",
                    "details": {}, "request_id": None, "retryable": False}}).encode()
                await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json")]})
                return await send({"type": "http.response.body", "body": raw})
            chunks.append(msg.get("body", b""))
            if not msg.get("more_body"):
                break
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()
        return await self.app(scope, replay, send)
