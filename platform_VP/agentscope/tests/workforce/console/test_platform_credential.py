import os
import sys
import types
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
    async def test_shared_platform_key_is_never_seeded_into_user_credentials(self):
        from agentscope.app._router._workforce_console import _model_config

        storage = _Storage()
        with mock.patch.dict(os.environ, {"WORKFORCE_PLATFORM_OPENAI_API_KEY": "offline-sentinel-not-a-key", "VIN_PLATFORM_ENABLED": "false"}):
            for _ in range(2):
                with self.assertRaises(HTTPException) as raised:
                    await _model_config(storage, "bql-smart-city")
                self.assertEqual(409, raised.exception.status_code)
        self.assertEqual([], storage.credentials)

    async def test_without_a_platform_key_the_account_is_asked_for_a_credential(self):
        from agentscope.app._router._workforce_console import _model_config

        with mock.patch.dict(os.environ, {"WORKFORCE_PLATFORM_OPENAI_API_KEY": "", "VIN_PLATFORM_ENABLED": "false"}), self.assertRaises(HTTPException) as raised:
            await _model_config(_Storage(), "bql-smart-city")
        self.assertEqual(409, raised.exception.status_code)

    async def test_vin_mode_never_falls_back_to_user_credentials(self):
        from agentscope.app._router._workforce_console import _model_config

        storage = _Storage()
        storage.list_credentials = mock.AsyncMock(side_effect=AssertionError("legacy credential lookup"))
        with mock.patch.dict(os.environ, {"VIN_PLATFORM_ENABLED": "true"}), self.assertRaises(HTTPException) as raised:
            await _model_config(storage, "resident-a")
        self.assertEqual(503, raised.exception.status_code)
        storage.list_credentials.assert_not_awaited()

    async def test_console_consumes_c03_and_propagates_safe_denial_without_writes(self):
        from agentscope.app._router._workforce_console import _model_config
        from agentscope.app.storage import ChatModelConfig

        # Producer interfaces are supplied by the other lane. This consumer
        # fixture exercises forwarding/denial without importing unfinished WIP.
        class PlatformError(Exception):
            def __init__(self, code, status=403):
                self.code, self.status = code, status

        parent = types.ModuleType("agentscope.app.vin_platform")
        parent.__path__ = []
        contracts = types.ModuleType("agentscope.app.vin_platform._contracts")
        contracts.PlatformError = PlatformError
        resources = types.ModuleType("agentscope.app.vin_platform._resources")
        config = ChatModelConfig(type="openai_credential", credential_id="vin-platform-openai", model="entitled-alias", parameters={"max_tokens": 512})
        resources.platform_model_config = mock.AsyncMock(return_value=config)
        modules = {parent.__name__: parent, contracts.__name__: contracts, resources.__name__: resources}
        storage, authority = _Storage(), object()
        with mock.patch.dict(sys.modules, modules):
            self.assertEqual(config, await _model_config(storage, "resident-a", authority=authority))
            resources.platform_model_config.assert_awaited_once_with(authority, "resident-a")
            for code in ("MODEL_NOT_ENTITLED", "QUOTA_EXCEEDED", "QUOTA_POLICY_REQUIRED"):
                resources.platform_model_config.side_effect = PlatformError(code)
                with self.assertRaises(HTTPException) as raised:
                    await _model_config(storage, "resident-a", authority=authority)
                self.assertEqual((403, code), (raised.exception.status_code, raised.exception.detail))
        self.assertEqual([], storage.credentials)


if __name__ == "__main__":
    unittest.main()
