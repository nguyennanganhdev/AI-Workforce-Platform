import os
import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi import HTTPException


class _Storage:
    def __init__(self, credentials=()):
        self.credentials = list(credentials)

    async def list_credentials(self, user_id):
        return list(self.credentials)

    async def upsert_credential(self, user_id, credential):
        self.credentials.append(SimpleNamespace(id="cred-platform", data=credential.model_dump(mode="json")))
        return "cred-platform"


class PlatformCredentialTest(unittest.IsolatedAsyncioTestCase):
    async def test_a_new_management_account_uses_the_platform_model_key(self):
        from agentscope.app._router._workforce_console import PLATFORM_CREDENTIAL_NAME, _model_config

        storage = _Storage()
        with mock.patch.dict(os.environ, {"WORKFORCE_PLATFORM_OPENAI_API_KEY": "sk-platform", "WORKFORCE_MODEL_NAME": "gpt-5.4-mini"}):
            config = await _model_config(storage, "bql-smart-city")
            again = await _model_config(storage, "bql-smart-city")
        self.assertEqual("cred-platform", config.credential_id)
        self.assertEqual("gpt-5.4-mini", config.model)
        self.assertEqual(1, len(storage.credentials))  # stored once
        self.assertEqual(config, again)
        self.assertEqual(PLATFORM_CREDENTIAL_NAME, storage.credentials[0].data["name"])

    async def test_without_a_platform_key_the_account_is_asked_for_a_credential(self):
        from agentscope.app._router._workforce_console import _model_config

        with mock.patch.dict(os.environ, {"WORKFORCE_PLATFORM_OPENAI_API_KEY": ""}), self.assertRaises(HTTPException) as raised:
            await _model_config(_Storage(), "bql-smart-city")
        self.assertEqual(409, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
