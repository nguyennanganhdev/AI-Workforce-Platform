"""Start a real Domain image CMD against an owned, disposable local PG fixture.

No application source mount, deployment env, model call or production DB.
Requires pgvector fixture named vin-n1-* with vin.fixture=vin-n1-* and user
vinfixture. Creates/drops only its UUID database and labelled API container.
"""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from vin_domain_rc_check import run


CLIENT = r'''
import base64,hashlib,json,re,time
from urllib.parse import parse_qs,urlsplit
import httpx
base='http://127.0.0.1:18121'
with httpx.Client(base_url=base,trust_env=False,timeout=5,follow_redirects=False,
    headers={'x-vinhomes-surface':'resident'}) as client:
    for attempt in range(80):
        try:
            if client.get('/ready').status_code==200: break
        except httpx.HTTPError: pass
        time.sleep(.25)
    else: raise AssertionError('Production CMD never became ready')
    verifier='offline-domain-candidate-verifier-material-2026-10-18'
    params={'client_id':'local-e2e','redirect_uri':'http://127.0.0.1:18104/connections/callback/vinhomes',
        'state':'s'*32,'code_challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),
        'platform_user_id':'domain-image-smoke-user'}
    page=client.get('/platform/link/authorize',params=params)
    assert page.status_code==200 and 'id="login"' in page.text
    login=client.post('/auth/login',headers={'x-vinhomes-surface':'resident'},
        json={'identifier':'resident@example.invalid','password':'Offline-e2e-password-2026!'})
    assert login.status_code==200, login.status_code
    page=client.get('/platform/link/authorize',params=params)
    assert page.status_code==200 and 'id="login"' not in page.text, 'Resident session did not reach consent'
    transaction=re.search(r'name="transaction" value="([^"]+)"',page.text)[1]
    csrf=re.search(r'name="csrf" value="([^"]+)"',page.text)[1]
    consent=client.post('/platform/link/authorize',data={'transaction':transaction,'csrf':csrf,'decision':'allow'})
    assert consent.status_code==303, consent.status_code
    code=parse_qs(urlsplit(consent.headers['location']).query)['code'][0]
    linked=client.post('/platform/link/token',json={**{key:params[key] for key in ('client_id','redirect_uri','platform_user_id')},
        'grant_type':'authorization_code','client_secret':'offline-e2e-domain-client-secret-only','code':code,'code_verifier':verifier})
    assert linked.status_code==200, linked.status_code
    grant=client.post('/platform/customer/grants',json={'client_id':'local-e2e',
        'client_secret':'offline-e2e-domain-client-secret-only','link_token':linked.json()['link_token']})
    assert grant.status_code==200
    profile=client.get('/platform/customer/me',headers={'Authorization':'Bearer '+grant.json()['access_token']})
    assert profile.status_code==200 and profile.json()['apartments']
    policy=client.get('/resident/intake-policy')
    assert policy.status_code==200 and policy.json()['legacy_new_intake'] is True, policy.status_code
print(json.dumps({'status':'PASS','production_cmd_ready':True,'password_consent_pkce_grant_profile':True,
    'legacy_intake_preserved':True,'paid_model_calls':0}))
'''


def smoke(image, pg, output):
    output.mkdir(parents=True, exist_ok=True)
    parent = json.loads(run("docker", "inspect", pg))[0]
    assert parent["Name"].startswith("/vin-n1-") and parent["Config"]["Labels"].get("vin.fixture", "").startswith("vin-n1-")
    namespace = "vin-n1-domain-rc-" + uuid4().hex[:8]
    name = "vin_domain_rc_" + uuid4().hex
    api = namespace + "-api"
    created, started = False, False
    report = {"status": "RUNNING", "image": image, "app_db_migrations": 0, "paid_model_calls": 0}
    try:
        run("docker", "exec", pg, "psql", "-U", "vinfixture", "-d", "vinfixture", "-c", "CREATE DATABASE " + name)
        created = True
        fixture = Path(__file__).with_name("vin_platform_local_fixture.py").resolve()
        run("docker", "run", "--rm", "--network", "container:" + pg,
            "--mount", "type=bind,source=" + str(fixture) + ",target=/fixture.py,readonly",
            "-e", "FIXTURE_DOMAIN_OWNER_URL=postgresql://vinfixture:offline-vin-fixture-only@127.0.0.1:5432/" + name,
            "--entrypoint", "python", image, "/fixture.py", "seed-domain")
        run("docker", "run", "-d", "--name", api, "--label", "vin.fixture=" + namespace,
            "--network", "container:" + pg,
            "-e", "VINHOMES_API_DATABASE_URL=postgresql+asyncpg://vin_runtime:offline-runtime-only@127.0.0.1:5432/" + name,
            "-e", "VINHOMES_API_TENANT_ID=11111111-1111-5111-a111-111111111111",
            "-e", "VINHOMES_API_PASSWORD_AUTH=1", "-e", "VINHOMES_API_HOST=127.0.0.1", "-e", "VINHOMES_API_PORT=18121",
            "-e", "VINHOMES_CUSTOMER_PLATFORM_ENABLED=true", "-e", "VINHOMES_API_LOCAL_FILE_STORAGE=1",
            "-e", "VINHOMES_CHATBOT_COHORT_CUTOVER_ENABLED=false", image)
        started = True
        container = json.loads(run("docker", "inspect", api))[0]
        assert not container["Mounts"] and container["Config"]["Cmd"] == ["python", "-m", "vinhomes_api"]
        checks = json.loads(run("docker", "run", "--rm", "--network", "container:" + pg, "--entrypoint", "python",
            "agentscope-op2-offline-qa:20261017", "-c", CLIENT))
        report.update(checks, application_source_mounts=0, production_cmd=container["Config"]["Cmd"])
    except BaseException as exc:
        report.update(status="FAIL", error=type(exc).__name__ + ": " + str(exc)[:1500])
        raise
    finally:
        if started:
            current = json.loads(run("docker", "inspect", api))[0]
            assert current["Config"]["Labels"]["vin.fixture"] == namespace
            (output / "domain-runtime.log").write_text(run("docker", "logs", api), encoding="utf-8")
            run("docker", "rm", "-f", "-v", api)
        if created:
            assert name.startswith("vin_domain_rc_") and len(name) == len("vin_domain_rc_") + 32
            run("docker", "exec", pg, "psql", "-U", "vinfixture", "-d", "vinfixture", "-c", 'DROP DATABASE "' + name + '" WITH (FORCE)')
        report["cleanup"] = "owned API and UUID DB removed; parent PG preserved"
        (output / "domain-runtime.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--database-container", required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    smoke(options.image, options.database_container, options.output.resolve())
