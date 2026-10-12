"""First passwords for people already in the database, the first administrator, and the phone number typed at sign-in
(`python -m vinhomes_api.database accounts`, deploy/README.md)."""
import asyncio
import secrets

import pytest
from test_account_administration import door, sign_in
from test_resident_contract import sql
from test_resident_contract import database as database  # noqa: F401 -- pytest fixture export

from vinhomes_api import database as tool
from vinhomes_api.password_auth import sign_in_name


def test_a_first_password_is_given_once_and_never_replaced(database):
    first, later = secrets.token_urlsafe(16), secrets.token_urlsafe(16)
    people = ["local-v3-resident", "management@example.invalid"]            # by id and by email
    assert asyncio.run(tool.accounts(database["admin"], people, first)) == (people, [])
    stored = sql(database, "select password from accounts where user_id='local-v3-resident' and provider_id='vinhomes-password-v1'")
    assert len(stored) == 1 and stored[0]["password"].startswith("scrypt-v1$") and first not in stored[0]["password"]
    # again, with another password: nobody new, and the first password still opens the door
    assert asyncio.run(tool.accounts(database["admin"], people, later)) == ([], people)
    with door(database) as c:
        assert sign_in(c, "resident@example.invalid", later) == 401
        assert sign_in(c, "resident@example.invalid", first) == 200
        assert sign_in(c, "management@example.invalid", first) == 200
    # one unknown name stops the whole run
    with pytest.raises(SystemExit, match="nobody-here"):
        asyncio.run(tool.accounts(database["admin"], ["local-v3-technical", "nobody-here"], first))
    assert not sql(database, "select 1 from accounts where user_id='local-v3-technical'")
    with pytest.raises(SystemExit, match="12 to 128"):
        asyncio.run(tool.accounts(database["admin"], ["local-v3-technical"], "short"))


def test_the_first_administrator_is_created_from_nothing(database):
    email, password = f"Chief-{secrets.token_hex(4)}@Example.com", secrets.token_urlsafe(16)
    assert asyncio.run(tool.accounts(database["admin"], [], password, admin_email=email)) == ([email.lower()], [])
    assert asyncio.run(tool.accounts(database["admin"], [], secrets.token_urlsafe(16), admin_email=email)) == ([], [email.lower()])
    assert sql(database, "select count(*) as n from users where lower(email)=$1", email.lower())[0]["n"] == 1
    with door(database) as c:
        assert sign_in(c, email, password) == 200
        session = c.get("/auth/session").json()
        assert session["administrator"] is True and session["operationsRole"] == "admin"
        assert c.get("/auth/accounts").status_code == 200
    # an email that belongs to an ordinary person is not turned into an administrator
    with pytest.raises(SystemExit, match="not an administrator"):
        asyncio.run(tool.accounts(database["admin"], [], password, admin_email="technical@example.invalid"))
    assert not sql(database, "select 1 from platform_admins where user_id='local-v3-technical'")


def test_a_phone_number_signs_in_however_it_is_typed(database):
    password = secrets.token_urlsafe(16)
    asyncio.run(tool.accounts(database["admin"], ["local-v3-security"], password))
    sql(database, "update users set phone_e164='+84902345678' where id='local-v3-security' returning id")
    with door(database) as c:
        for typed in ("0902345678", " 0902 345 678 ", "0902.345.678", "+84902345678", "+84 902 345 678", "Security@example.invalid"):
            assert sign_in(c, typed, password) == 200, typed
        assert sign_in(c, "902345678", password) == 401
    assert sign_in_name("An.Nguyen@Example.com ") == "an.nguyen@example.com"     # an email keeps its dots
