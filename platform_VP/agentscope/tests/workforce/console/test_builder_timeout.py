import os
import unittest
from unittest import mock

from fastapi import HTTPException


class BuilderTimeoutTest(unittest.TestCase):
    def test_a_builder_call_waits_three_minutes_unless_configured(self):
        from agentscope.app._router._workforce_console import _builder_timeout

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WORKFORCE_BUILDER_TIMEOUT_SECONDS", None)
            self.assertEqual(180, _builder_timeout())
        with mock.patch.dict(os.environ, {"WORKFORCE_BUILDER_TIMEOUT_SECONDS": "300"}):
            self.assertEqual(300, _builder_timeout())

    def test_the_timeout_message_names_the_configured_wait(self):
        from agentscope.app._router._workforce_console import _raise_builder_model_error
        from agentscope.app.storage import ChatModelConfig

        config = ChatModelConfig(type="openai_credential", credential_id="c", model="gpt-5.5", parameters={})
        with mock.patch.dict(os.environ, {"WORKFORCE_BUILDER_TIMEOUT_SECONDS": "240"}), self.assertRaises(HTTPException) as raised:
            _raise_builder_model_error(TimeoutError(), config)
        self.assertIn("240 giây", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
