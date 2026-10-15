"""Offline DNS hook contract; never contacts DuckDNS or Let's Encrypt."""
import importlib.util
import os
from pathlib import Path
import pytest


@pytest.fixture
def hook(monkeypatch,tmp_path):
    path=Path(os.getenv('VINHOMES_TEST_DUCKDNS_HOOK',str(Path(__file__).resolve().parents[3]/'deploy/duckdns-acme-hook.py')))
    spec=importlib.util.spec_from_file_location('duckdns_acme_hook',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    token=tmp_path/'token.secret';token.write_text('offline-fixture-token');token.chmod(0o600)
    monkeypatch.setenv('DUCKDNS_TOKEN_FILE',str(token));monkeypatch.setenv('DUCKDNS_DOMAIN','vinhome-platform.duckdns.org')
    monkeypatch.setenv('CERTBOT_DOMAIN','vinhome-platform.duckdns.org');monkeypatch.setenv('CERTBOT_VALIDATION','fixture-acme-value')
    return module


def test_auth_waits_for_txt_without_overwriting_other_records(hook,monkeypatch):
    seen=[];answers=iter([[],[],['fixture-acme-value']])
    monkeypatch.setattr(hook,'txt_values',lambda _:next(answers));monkeypatch.setattr(hook,'update',lambda *args:seen.append(args))
    hook.run('auth',sleep=lambda _:None)
    assert len(seen)==1 and seen[0][2]=='fixture-acme-value'
    monkeypatch.setattr(hook,'txt_values',lambda _:['some-other-record'])
    with pytest.raises(RuntimeError,match='refusing to overwrite'):hook.run('auth',sleep=lambda _:None)
    assert len(seen)==1


def test_cleanup_never_deletes_somebody_elses_txt(hook,monkeypatch):
    seen=[];monkeypatch.setattr(hook,'update',lambda *args:seen.append(args))
    monkeypatch.setattr(hook,'txt_values',lambda _:['some-other-record']);hook.run('cleanup');assert not seen
    monkeypatch.setattr(hook,'txt_values',lambda _:['fixture-acme-value']);hook.run('cleanup');assert seen[0][2]==''


def test_hook_rejects_other_domain_and_hides_credential_urls(hook,monkeypatch):
    monkeypatch.setenv('CERTBOT_DOMAIN','other.duckdns.org')
    with pytest.raises(RuntimeError,match='Unexpected domain'):hook.run('auth')
    def fail(*args,**kwargs):raise OSError('URL containing a private token')
    monkeypatch.setattr(hook,'urlopen',fail)
    with pytest.raises(RuntimeError) as error:hook.update('vinhome-platform.duckdns.org','offline-fixture-token','value')
    assert 'offline-fixture-token' not in str(error.value) and 'containing a private token' not in str(error.value)


def test_duckdns_empty_txt_is_not_an_existing_ownership_record(hook,monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(hook.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(returncode=0,stdout='""\n'))
    assert hook.txt_values('vinhome-platform.duckdns.org')==[]
