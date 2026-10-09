"""Each front door keeps its own sign-in, and the two staff doors each take their own roles."""
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from vinhomes_api.password_auth import cookie, surface
from vinhomes_api.v3_operations import wrong_door


def arriving(door: str | None) -> Request:
    headers = [] if door is None else [(b"x-vinhomes-surface", door.encode())]
    return Request({"type": "http", "headers": headers})


def test_each_door_has_its_own_cookie_and_operations_keeps_the_default_one():
    assert cookie(arriving(None)) == cookie(arriving("operations")) == "vinhomes_session"
    assert cookie(arriving("field")) == "vinhomes_staff_session"
    assert cookie(arriving("resident")) == "vinhomes_resident_session"
    assert surface(arriving("field")) == "field"


def test_a_door_the_api_does_not_know_is_refused():
    with pytest.raises(HTTPException) as refused:
        cookie(arriving("somewhere"))
    assert refused.value.status_code == 400


def test_the_field_door_takes_staff_and_the_operations_door_takes_the_others():
    assert wrong_door("field", "staff") is None
    assert "nhân viên hiện trường" in wrong_door("field", "management")
    assert wrong_door("field", "admin")
    assert "Ban quản lý" in wrong_door("operations", "staff")
    assert wrong_door("operations", "management") is None and wrong_door("operations", "admin") is None
    # A stack with a single door serves every role there, as before.
    assert [wrong_door("", role) for role in ("staff", "management", "admin")] == [None, None, None]
