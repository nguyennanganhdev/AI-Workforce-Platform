"""Recovery acceptance with an in-memory fake mailbox. Never sends email or invokes an Agent."""
import secrets
from urllib.parse import parse_qs, urlsplit

from test_resident_contract import sql, database as database
from test_account_administration import door, sign_in
from test_account_onboarding import admin_login
from vinhomes_api import password_recovery as recovery


def test_fake_mailbox_reset_is_single_use_revokes_sessions_and_hides_unknown_accounts(database,monkeypatch):
    mailbox=[]
    monkeypatch.setenv('VINHOMES_SMTP_HOST','mail.example.invalid')
    monkeypatch.setenv('VINHOMES_SMTP_FROM','support@example.invalid')
    monkeypatch.setenv('VINHOMES_PUBLIC_URL','https://vinhome-platform.duckdns.org')
    monkeypatch.setattr(recovery,'send_reset_email',lambda host,sender,email,link:mailbox.append((email,link)))
    first,new=secrets.token_urlsafe(16),secrets.token_urlsafe(16)
    with door(database) as admin, door(database) as user:
        admin_login(database,admin)
        email='recovery-test@example.invalid'
        response=admin.post('/auth/accounts',json={'name':'Khôi phục kiểm thử','email':email,'password':first,'role':'customer'})
        assert response.status_code==201,response.text
        identity=response.json()['id']
        assert sign_in(user,email,first)==200
        known=user.post('/auth/password-reset/request',json={'email':email})
        unknown=user.post('/auth/password-reset/request',json={'email':'unknown@example.invalid'})
        assert known.status_code==unknown.status_code==200
        assert known.json()==unknown.json() and len(mailbox)==1
        token=parse_qs(urlsplit(mailbox[0][1]).fragment.split('?',1)[1])['token'][0]
        stored=sql(database,'select token_hash from password_reset_tokens where user_id=$1',identity)
        assert token not in str(stored)
        body={'token':token,'new_password':new}
        assert user.post('/auth/password-reset/confirm',json=body).status_code==200
        assert user.get('/auth/session').status_code==401
        assert user.post('/auth/password-reset/confirm',json=body).status_code==400
        assert sign_in(user,email,first)==401 and sign_in(user,email,new)==200
        assert user.post('/auth/password-reset/request',json={'email':email}).status_code==200
        expired=parse_qs(urlsplit(mailbox[-1][1]).fragment.split('?',1)[1])['token'][0]
        sql(database,"update password_reset_tokens set expires_at=now()-interval '1 minute' where user_id=$1 and used_at is null",identity)
        assert user.post('/auth/password-reset/confirm',json={'token':expired,'new_password':first}).status_code==400
        assert user.post('/auth/password-reset/request',json={'email':email}).status_code==200
        pending=parse_qs(urlsplit(mailbox[-1][1]).fragment.split('?',1)[1])['token'][0]
        assert admin.post(f'/auth/accounts/{identity}/password',json={'new_password':first}).status_code==200
        assert user.post('/auth/password-reset/confirm',json={'token':pending,'new_password':new}).status_code==400


def test_missing_smtp_is_explicitly_disabled(database,monkeypatch):
    monkeypatch.delenv('VINHOMES_SMTP_HOST',raising=False)
    with door(database) as user:
        assert user.post('/auth/password-reset/request',json={'email':'any@example.invalid'}).status_code==503
