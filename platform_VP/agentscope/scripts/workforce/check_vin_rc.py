"""Run owned Docker/Chromium acceptance on built Platform images, never production.

Auth/data/model/dispatcher and browser scenario use N1's synthetic fixture.
Both APIs use their production image CMD and installed source; web uses its
image bundle. No application source or deployment env file is mounted.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]
P = ROOT / 'platform_VP/agentscope'


def cleanup_fixture(fixture, output):
    """Retain the producer's ownership checks; omit already removed names."""
    path = output / 'state.json'
    state = json.loads(path.read_text(encoding='utf-8'))
    existing = set(fixture.docker('ps', '-a', '--format', '{{.Names}}').splitlines())
    state['containers'] = [name for name in state['containers'] if name in existing]
    path.write_text(json.dumps(state, indent=2), encoding='utf-8')
    fixture.down(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-image')
    parser.add_argument('--web-image')
    parser.add_argument('--domain-image')
    parser.add_argument('--staff-dist', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--keep-running', action='store_true', help='Keep a successful loopback-only staging fixture for review')
    parser.add_argument('--restore', action='store_true', help='Also rehearse the four-store backup/restore using this RC runtime')
    parser.add_argument('--cleanup-only', action='store_true', help='Remove only the owned fixture recorded in --output')
    options = parser.parse_args()
    output = options.output.resolve()
    tests = ROOT / 'vinhome_Recident/services/vinhomes-api/tests'
    sys.path.insert(0, str(tests))
    import run_vin_platform_docker_e2e as fixture
    if options.cleanup_only:
        cleanup_fixture(fixture, output)
        return
    if not all((options.app_image, options.web_image, options.domain_image, options.staff_dist)):
        parser.error('Pass all three RC images and the unchanged staff build')
    if (output / 'state.json').exists():
        parser.error('Use a fresh artifact directory; never overwrite a fixture state')
    if not (options.staff_dist / 'index.html').is_file():
        parser.error('Pass the existing Domain staff build')
    output.mkdir(parents=True, exist_ok=True)
    import vin_platform_browser_roundtrip as journey
    import vin_domain_rc_check as domain_check
    import httpx

    docker = fixture.docker
    image_ids = {kind: docker('image', 'inspect', '--format', '{{.Id}}', name)
        for kind, name in (('app', options.app_image), ('web', options.web_image), ('domain', options.domain_image))}
    domain_revision = docker('image', 'inspect', '--format', '{{index .Config.Labels "org.opencontainers.image.revision"}}', options.domain_image)
    domain_check.check(output / 'domain-package', options.domain_image, source_revision=domain_revision)
    revision = docker('image', 'inspect', '--format', '{{index .Config.Labels "org.opencontainers.image.revision"}}', options.app_image)
    assert len(revision) == 40 and revision == docker('image', 'inspect', '--format',
        '{{index .Config.Labels "org.opencontainers.image.revision"}}', options.web_image), 'Image revisions differ/missing'
    changed = subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-only', revision, '--',
        'platform_VP/agentscope/src', 'platform_VP/agentscope/examples/agent_service/main.py',
        'platform_VP/agentscope/examples/web_ui', 'platform_VP/agentscope/Dockerfile'], text=True).splitlines()
    assert not changed, 'Check out the image source revision before acceptance; application/build files differ'
    tracked = subprocess.check_output(['git', '-C', str(ROOT), 'ls-tree', '-r', '--name-only', revision,
        'platform_VP/agentscope/src', 'platform_VP/agentscope/examples/agent_service/main.py'], text=True).splitlines()
    expected = {name.removeprefix('platform_VP/agentscope/'): hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in tracked if name.endswith('.py')}
    hash_script = "import hashlib,json,pathlib;paths=[*pathlib.Path('/app/src').rglob('*.py'),pathlib.Path('/app/examples/agent_service/main.py')];print(json.dumps({str(p.relative_to('/app')):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}))"
    installed = json.loads(docker('run', '--rm', '--network', 'none', '--entrypoint', 'python', options.app_image, '-c', hash_script))
    assert expected and all(installed.get(name) == value for name, value in expected.items()), 'Image source differs from checked-out RC source'
    report = dict(status='RUNNING', source_revision=revision, images=image_ids, installed_python_files_verified=len(expected),
        paid_model_calls=0, production_cutover_verified=False, autonomous_staff_dispatch_verified=False,
        bootstrap='production image CMD; synthetic auth/data/model; test socket egress guard', scenarios={})
    def save():
        (output / 'rc-summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    save()
    try:
        fixture.up(ROOT, output)
        state = json.loads((output / 'state.json').read_text(encoding='utf-8'))
        prefix = state['prefix']
        assert prefix.startswith('vin-n1-r04-e2e-')
        def remember(name):
            state['containers'].append(name)
            (output / 'state.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
        original = prefix + '-platform'
        assert docker('inspect', '--format', '{{index .Config.Labels "vin.fixture"}}', original) == prefix
        docker('rm', '-f', original)
        state['containers'].remove(original)
        guard = output / 'guard'
        guard.mkdir()
        (guard / 'sitecustomize.py').write_text('''import socket,sys
connect,connect_ex,resolve,sendto=socket.socket.connect,socket.socket.connect_ex,socket.getaddrinfo,socket.socket.sendto
def check(host):
    if host not in ('localhost','127.0.0.1','::1',None):
        print('RC_OFFLINE_NETWORK_DENIED',file=sys.stderr,flush=True)
        raise RuntimeError('RC fixture permits loopback only')
def checked_connect(sock,address):
    if isinstance(address,tuple): check(address[0])
    return connect(sock,address)
def checked_connect_ex(sock,address):
    if isinstance(address,tuple): check(address[0])
    return connect_ex(sock,address)
def checked_resolve(host,*args,**kwargs):
    check(host)
    return resolve(host,*args,**kwargs)
def checked_sendto(sock,data,*args):
    if args and isinstance(args[-1],tuple): check(args[-1][0])
    return sendto(sock,data,*args)
socket.socket.connect=checked_connect
socket.socket.connect_ex=checked_connect_ex
socket.socket.sendto=checked_sendto
socket.getaddrinfo=checked_resolve
''', encoding='utf-8')
        original_domain = prefix + '-domain'
        assert docker('inspect', '--format', '{{index .Config.Labels "vin.fixture"}}', original_domain) == prefix
        docker('rm', '-f', original_domain)
        state['containers'].remove(original_domain)
        domain = prefix + '-domain-rc'
        remember(domain)
        domain_env = {'VINHOMES_API_DATABASE_URL': 'postgresql+asyncpg://vin_runtime:offline-runtime-only@127.0.0.1:5432/domain_e2e',
            'VINHOMES_API_TENANT_ID': '11111111-1111-5111-a111-111111111111', 'VINHOMES_API_PASSWORD_AUTH': '1',
            'VINHOMES_API_HOST': '0.0.0.0', 'VINHOMES_API_PORT': '18101', 'VINHOMES_CUSTOMER_PLATFORM_ENABLED': 'true',
            'VINHOMES_API_VOLUME_FILE_STORAGE': '1', 'VINHOMES_API_PLATFORM_MCP_TOKEN': 'offline-e2e-mcp-control-token-0123456789',
            'VINHOMES_API_RESIDENT_SIGNING_KEY': 'ab' * 32, 'VINHOMES_CHATBOT_COHORT_CUTOVER_ENABLED': 'false', 'PYTHONPATH': '/rc-guard'}
        domain_args = ['run', '-d', '--name', domain, '--label', 'vin.fixture=' + prefix, '--network', 'container:' + prefix + '-postgres',
            '--mount', 'type=bind,source=' + guard.as_posix() + ',target=/rc-guard,readonly']
        for key, value in domain_env.items():
            domain_args.extend(['-e', key + '=' + value])
        docker(*domain_args, options.domain_image)
        fixture.wait_ready('http://127.0.0.1:18101/ready')
        env = {'AGENTSCOPE_SQL_URL': 'postgresql+asyncpg://vinfixture:offline-vin-fixture-only@127.0.0.1:5432/platform_e2e',
            'AUTH_ENABLED': 'true', 'AUTH_JWT_SECRET': 'offline-e2e-jwt-material-' * 3,
            'AUTH_REFRESH_PEPPER': 'offline-e2e-refresh-material-' * 3, 'AUTH_COOKIE_SECURE': 'false',
            'AUTH_DEFAULT_TENANT_ID': 'default', 'PARTNER_API_KEY_PEPPER': 'offline-partner-pepper-only-' * 3,
            'PARTNER_API_PROVISIONING_SECRET': 'offline-provision-only-' * 3,
            'REDIS_HOST': '127.0.0.1', 'REDIS_PORT': '18106', 'S3_ENABLED': 'false',
            'CORS_ALLOWED_ORIGINS': 'http://127.0.0.1:18104', 'VIN_PLATFORM_ENABLED': 'true',
            'VIN_PLATFORM_ENCRYPTION_KEY': 'ZmFrZS1maXh0dXJlLWZlcm5ldC1rZXktMDAwMDAwMDA=',
            'WORKFORCE_PLATFORM_OPENAI_API_KEY': 'offline-scripted-model-no-real-key',
            'WORKFORCE_PLATFORM_OPENAI_BASE_URL': 'http://127.0.0.1:18103/v1', 'PYTHONPATH': '/rc-guard:/app/src'}
        app = prefix + '-platform-rc'
        remember(app)
        args = ['run', '-d', '--name', app, '--label', 'vin.fixture=' + prefix, '--network', 'container:' + prefix + '-postgres',
            '--mount', 'type=bind,source=' + guard.as_posix() + ',target=/rc-guard,readonly']
        for key, value in env.items():
            args.extend(['-e', key + '=' + value])
        docker(*args, options.app_image)
        # Extract public artifacts from the image, never from a host build tree.
        assets = prefix + '-assets'
        remember(assets)
        docker('create', '--name', assets, '--label', 'vin.fixture=' + prefix, options.web_image)
        docker('cp', assets + ':/usr/share/nginx/html', str(output / 'web-dist'))
        docker('cp', assets + ':/etc/nginx/conf.d/default.conf', str(output / 'image-nginx.conf'))
        bundled = (output / 'image-nginx.conf').read_text(encoding='utf-8')
        # Only address/port adaptation: retain production proxy, cookies, SSE,
        # asset cache and SPA rules; staff app/API remain Domain-owned.
        config = 'events {}\nhttp {\n include /etc/nginx/mime.types;\n' + bundled.replace('listen 80;', 'listen 18104;').replace('http://app:8000/', 'http://127.0.0.1:8000/') + '''
server { listen 18105; root /staff; index index.html; client_max_body_size 25m;
location /api/business/ { proxy_pass http://127.0.0.1:18101/; proxy_set_header Host $http_host; proxy_set_header X-Vinhomes-Surface ""; }
location / { try_files $uri /index.html; }
}\n}\n'''
        (output / 'nginx.conf').write_text(config, encoding='utf-8')
        web = prefix + '-web-rc'
        remember(web)
        docker('run', '-d', '--name', web, '--label', 'vin.fixture=' + prefix, '--network', 'container:' + prefix + '-postgres',
            '--mount', 'type=bind,source=' + (output / 'nginx.conf').as_posix() + ',target=/etc/nginx/nginx.conf,readonly',
            '--mount', 'type=bind,source=' + options.staff_dist.resolve().as_posix() + ',target=/staff,readonly', options.web_image)
        fixture.wait_ready('http://127.0.0.1:18104/api/health')
        probe = json.loads(docker('exec', app, 'python', '-c',
            "import json,agentscope;print(json.dumps({'module':agentscope.__file__}))"))
        assert probe['module'].startswith('/app/src/'), 'Application is not running image source'
        report['runtime_module'] = probe['module']
        report['domain_source_revision'] = domain_revision
        report['application_source_mounts'] = 0
        report['web_assets_sha256'] = {p.relative_to(output / 'web-dist').as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((output / 'web-dist').rglob('*')) if p.is_file()}
        journey.main(output)
        model = httpx.get('http://127.0.0.1:18103/evidence', trust_env=False).json()
        assert [item['operation'] for item in model['calls']] == ['context', 'create', None], 'Leader retried after a valid receipt'
        report['scenarios']['customer_staff_photo_consent'] = 'PASS'
        # Actual N2 admin UI -> production image API -> persisted policy revision.
        from playwright.sync_api import sync_playwright, expect
        admin = journey.login_platform('fixtureadmin')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                context.add_cookies([dict(name=c.name, value=c.value, domain='127.0.0.1', path=c.path, httpOnly=True, secure=False, sameSite='Lax') for c in admin.cookies.jar])
                page = context.new_page()
                external = []
                def route(request):
                    from urllib.parse import urlsplit
                    parsed = urlsplit(request.request.url)
                    if (parsed.scheme, parsed.netloc) != ('http', '127.0.0.1:18104'):
                        external.append(parsed.netloc)
                        request.abort()
                    else:
                        request.continue_()
                page.route('**/*', route)
                page.goto('http://127.0.0.1:18104/admin')
                page.get_by_role('button', name='Quota & thư viện Vin', exact=True).click()
                page.get_by_role('button', name='Đọc chính sách', exact=True).click()
                expect(page.get_by_label('Token mỗi ngày', exact=True)).to_have_value('200000')
                page.get_by_label('Token mỗi ngày', exact=True).fill('190000')
                page.get_by_role('button', name='Áp dụng chính sách thay thế', exact=True).click()
                expect(page.get_by_text('Đã lưu chính sách quota.', exact=True)).to_be_visible()
                # The browser rotated the copied refresh session. Verify with
                # a fresh login, not the HTTP client's now-revoked access JWT.
                admin.close()
                admin = journey.login_platform('fixtureadmin')
                policy = journey.call(admin, 'GET', '/admin/vin/quota-policies/role:VIN_USER')
                assert policy['policy']['daily_tokens'] == 190000 and policy['revision'] >= 2
                assert not external
                page.screenshot(path=str(output / 'rc-admin-policy.png'), full_page=True)
                report['scenarios']['admin_policy_ui_persistence'] = 'PASS'
            finally:
                browser.close()
                admin.close()
        logs = docker('logs', app) + docker('logs', domain)
        assert 'RC_OFFLINE_NETWORK_DENIED' not in logs, 'Production code attempted external IO'
        if options.restore:
            sys.path.insert(0, str(P / 'tests'))
            import vin_release_rehearsal
            vin_release_rehearsal.QA_IMAGE = options.app_image
            vin_release_rehearsal.rehearse(output / 'restore')
            restore = json.loads((output / 'restore/deep-restore.json').read_text(encoding='utf-8'))
            assert restore['status'] == 'PASS' and restore['restored_app_started'] is False
            report['four_store_restore'] = dict(passed=4, skipped=0, restored_app_started=False)
        report.update(status='PASS', passed=2, skipped=0, failed=0, errors=0, scripted_model_calls=len(model['calls']), external_network_attempts=0)
        report['staging_running'] = options.keep_running
        save()
        print(json.dumps({key: report[key] for key in ('status', 'passed', 'skipped', 'failed', 'errors', 'scripted_model_calls', 'paid_model_calls')}))
    except Exception as exc:
        report.update(status='FAIL', error_type=type(exc).__name__, error=str(exc)[:1500])
        save()
        raise
    finally:
        if (output / 'state.json').exists() and not (options.keep_running and report['status'] == 'PASS'):
            cleanup_fixture(fixture, output)


if __name__ == '__main__':
    main()
