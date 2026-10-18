"""Configure the owned local staging for manual owner use; never call a model.

Secrets move from the explicitly selected source container into an ignored env
file and Docker environment. They are never printed or stored in user records.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time

import httpx


def docker(*args, data=None):
    result = subprocess.run(['docker', *args], input=data, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Docker operation failed: ' + ' '.join(args[:3]))
    return result.stdout.strip()


def inspect(name):
    return json.loads(docker('inspect', name))[0]


def environment(container):
    return dict(item.split('=', 1) for item in container['Config']['Env'] if '=' in item)


def configure(options):
    output = options.fixture.resolve()
    state = json.loads((output / 'state.json').read_text(encoding='utf-8'))
    prefix = state['prefix']
    assert prefix.startswith('vin-n1-r04-e2e-') and '.artifacts' in output.parts
    name = prefix + '-platform-rc'
    previous = inspect(name)
    assert previous['Config']['Labels'].get('vin.fixture') == prefix
    source = environment(inspect(options.source_container))
    key = source.get('WORKFORCE_PLATFORM_OPENAI_API_KEY', '').strip()
    if not key or key.startswith(('offline-', 'server-managed')):
        raise RuntimeError('Selected provider has no configured server key')
    queued = docker('exec', prefix + '-postgres', 'psql', '-U', 'vinfixture', '-d', 'platform_e2e', '-Atc',
        "SELECT count(*) FROM wf_durable_jobs WHERE status NOT IN ('succeeded','failed','cancelled','dead_letter')")
    assert queued == '0', 'Resolve existing queued jobs before enabling owner provider'
    target_image = inspect(options.image)
    assert target_image['Config']['Labels'].get('org.opencontainers.image.revision'), 'Pinned image required'
    destination = output / 'owner-use'
    destination.mkdir(exist_ok=True)
    env = environment(previous)
    env.update(WORKFORCE_PLATFORM_OPENAI_API_KEY=key, WORKFORCE_MODEL_NAME=options.model,
        WORKFORCE_LEADER_MODEL_NAME=options.model, WORKFORCE_MAX_OUTPUT_TOKENS='4096',
        OPENAI_CHAT_API=source.get('OPENAI_CHAT_API') or 'responses', PYTHONPATH='/app/src')
    base = source.get('WORKFORCE_PLATFORM_OPENAI_BASE_URL', '').strip()
    if base:
        env['WORKFORCE_PLATFORM_OPENAI_BASE_URL'] = base
    else:
        env.pop('WORKFORCE_PLATFORM_OPENAI_BASE_URL', None)
    for field in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'):
        env.pop(field, None)
    env_file = destination / 'runtime.env'
    assert all('\n' not in value and '\r' not in value for value in env.values())
    env_file.write_text('\n'.join(k + '=' + v for k, v in env.items()) + '\n', encoding='utf-8')
    workspaces = destination / 'workspaces'
    if not workspaces.exists():
        docker('cp', name + ':/app/examples/agent_service/workspaces', str(workspaces))
    saved = name + '-before-owner'
    assert not subprocess.run(['docker', 'inspect', saved], capture_output=True).returncode == 0, 'Owner configuration already applied'
    docker('stop', name)
    docker('rename', name, saved)
    state['containers'].append(saved)
    state['owner_use'] = True
    (output / 'state.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
    try:
        docker('run', '-d', '--name', name, '--label', 'vin.fixture=' + prefix,
            '--network', 'container:' + prefix + '-postgres', '--env-file', str(env_file),
            '--mount', 'type=bind,source=' + workspaces.as_posix() + ',target=/app/examples/agent_service/workspaces', options.image)
        for _ in range(60):
            try:
                if httpx.get('http://127.0.0.1:18104/api/health', trust_env=False, timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Owner Platform did not become ready')
    except Exception:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
        docker('rename', saved, name)
        docker('start', name)
        raise
    report = dict(status='CONFIGURED_NOT_MODEL_TESTED', model=options.model, source_container=options.source_container,
        image=options.image, image_id=inspect(name)['Image'], endpoint=base or 'https://api.openai.com/v1',
        paid_calls_by_agent=0, real_provider_requests_by_agent=0, workspace_preserved=True,
        previous_container_retained=saved, background_jobs_before_change=0,
        discord_oauth_configured=all(source.get(k) for k in ('DISCORD_OAUTH_CLIENT_ID', 'DISCORD_OAUTH_CLIENT_SECRET', 'DISCORD_OAUTH_REDIRECT_URI')))
    (destination / 'configuration.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--source-container', required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--model', default='gpt-6-luna')
    configure(parser.parse_args())
