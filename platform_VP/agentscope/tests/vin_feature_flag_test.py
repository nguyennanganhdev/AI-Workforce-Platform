import pytest

from agentscope.app.vin_platform import enabled


@pytest.mark.parametrize("value,expected", [(None, False), ("false", False), ("1", False), ("yes", False),
    ("true", True), (" TRUE ", True), ("TrUe", True), ("", False)])
def test_shared_feature_flag_parser(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("VIN_PLATFORM_ENABLED", raising=False)
    else:
        monkeypatch.setenv("VIN_PLATFORM_ENABLED", value)
    assert enabled() is expected
