import unittest
from unittest import mock

from fastapi import HTTPException


class BuilderTimeoutTest(unittest.TestCase):
    def test_invalid_api_key_is_reported_as_authentication_not_model_permission(self):
        import httpx
        from openai import AuthenticationError

        from agentscope.app._router._workforce_console import _raise_builder_model_error
        from agentscope.app.storage import ChatModelConfig

        config = ChatModelConfig(type="openai_credential", credential_id="c", model="gpt-4o-mini", parameters={})
        response = httpx.Response(401, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
        error = AuthenticationError("invalid key", response=response, body={"code": "invalid_api_key"})
        with mock.patch("agentscope.app._router._workforce_console.logger.exception"), self.assertRaises(HTTPException) as raised:
            _raise_builder_model_error(error, config)
        self.assertIn("API key", raised.exception.detail)
        self.assertNotIn("quyền sử dụng model", raised.exception.detail)

    def test_denied_model_permission_is_distinct_from_invalid_authentication(self):
        import httpx
        from openai import PermissionDeniedError

        from agentscope.app._router._workforce_console import _raise_builder_model_error
        from agentscope.app.storage import ChatModelConfig

        config = ChatModelConfig(type="openai_credential", credential_id="c", model="gpt-4o-mini", parameters={})
        response = httpx.Response(403, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
        error = PermissionDeniedError("denied", response=response, body={})
        with mock.patch("agentscope.app._router._workforce_console.logger.exception"), self.assertRaises(HTTPException) as raised:
            _raise_builder_model_error(error, config)
        self.assertIn("quyền sử dụng model", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
