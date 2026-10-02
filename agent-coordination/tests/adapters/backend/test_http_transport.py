"""Real loopback HTTP only; no real backend, external network or credentials."""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from adapters.backend.client import BackendClient
from adapters.backend.errors import AdapterError
from adapters.backend.http_transport import UrllibTransport
from tests.adapters.backend.support import Headers, Validator, request


class TransportTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.received = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                cls.received.append((self.path, dict(self.headers), body))
                if self.path == "/redirect":
                    self.send_response(307)
                    self.send_header("Location", "/should-not-receive-credentials")
                    self.end_headers()
                    return
                if self.path == "/large":
                    result = b"x" * 2048
                else:
                    result = json.dumps({"request_id": json.loads(body)["request_id"],
                                         "status": "accepted", "data": {}}).encode()
                self.send_response(202)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(result)))
                self.end_headers()
                self.wfile.write(result)

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=lambda: cls.server.serve_forever(poll_interval=0.01),
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.received.clear()

    def make_client(self, path, limit=1_048_576):
        return BackendClient(
            base_url=f"http://127.0.0.1:{self.server.server_port}", allow_http=True,
            routes={"test": path}, transport=UrllibTransport(max_response_bytes=limit),
            headers=Headers(), validator=Validator(), max_response_bytes=limit,
        )

    async def test_real_http_json_unicode_and_headers(self):
        wire = request()
        result = await self.make_client("/receive").call("test", wire)
        path, headers, body = self.received[0]
        self.assertEqual(path, "/receive")
        self.assertEqual(json.loads(body), wire)
        normalized = {key.lower(): value for key, value in headers.items()}
        self.assertEqual(normalized["authorization"], "Bearer test-credential")
        self.assertEqual(normalized["idempotency-key"], "command-1")
        self.assertEqual(result.status, "accepted")

    async def test_real_redirect_does_not_resend_body_or_credentials(self):
        with self.assertRaisesRegex(AdapterError, "unexpected_http_status"):
            await self.make_client("/redirect").call("test", request())
        self.assertEqual([item[0] for item in self.received], ["/redirect"])

    async def test_bounded_response_read(self):
        with self.assertRaisesRegex(AdapterError, "invalid_backend_response"):
            await self.make_client("/large", limit=100).call("test", request())
