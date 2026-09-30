"""Fixture dùng chung; mỗi testcase có dịch vụ và trạng thái riêng."""

import pytest
from support.harness import Harness


@pytest.fixture
def harness():
    return Harness()
