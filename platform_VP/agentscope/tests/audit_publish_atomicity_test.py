"""Offline fault injection against the committed Studio publication route."""
from fastapi import HTTPException
from tests.workforce.console.test_agent_studio_api import BASE, env, studio


def test_failed_binding_does_not_publish_an_agent(env, monkeypatch):
    client, storage, _, _ = env
    created = client.post(f'{BASE}/agents', json={'template_id': 'resident_technical'})
    assert created.status_code == 201
    agent_id = created.json()['agent_id']
    # This fixture replaces both working model and judge with in-process fakes.
    report = client.post(f'{BASE}/agents/{agent_id}/tests/run')
    assert report.status_code == 200 and report.json()['publishable']

    async def unavailable_binding(*args, **kwargs):
        raise HTTPException(409, 'offline fixture: skill hub unavailable')

    monkeypatch.setattr(studio, 'apply_bindings', unavailable_binding)
    response = client.post(f'{BASE}/agents/{agent_id}/publish', json={'note': 'offline audit'})
    assert response.status_code == 409
    actual = storage.agents[agent_id].data
    assert (actual.lifecycle_state, actual.published_version, actual.invite_config.invitable) == ('draft', 0, False)


def test_failed_update_keeps_active_version_and_workspace(env, monkeypatch):
    client, storage, model, manager = env
    agent_id = client.post(f'{BASE}/agents', json={'template_id':'resident_technical'}).json()['agent_id']
    client.post(f'{BASE}/agents/{agent_id}/tests/run')
    assert client.post(f'{BASE}/agents/{agent_id}/publish', json={}).status_code == 200
    before = storage.agents[agent_id].model_copy(deep=True)
    old_workspace = manager.workspace
    model.copilot_operations = [{'op':'add','field':'rules','value':{'text':'Confirm evidence before dispatch'}}]
    client.post(f'{BASE}/agents/{agent_id}/copilot', json={'message':'add rule'})
    client.post(f'{BASE}/agents/{agent_id}/tests/run')
    async def unavailable(*args, **kwargs):
        raise HTTPException(409, 'fixture failed staging')
    monkeypatch.setattr(studio,'apply_bindings',unavailable)
    assert client.post(f'{BASE}/agents/{agent_id}/publish',json={}).status_code == 409
    actual = storage.agents[agent_id]
    assert actual.data.published_version == before.data.published_version == 1
    assert actual.data.resource_workspace_id == before.data.resource_workspace_id
    assert actual.data.spec == before.data.spec and actual.data.draft_spec is not None


def test_prepared_workspace_is_private_and_default_bindings_survive_reload(tmp_path):
    import asyncio
    from agentscope.app.workspace_manager import LocalWorkspaceManager
    from agentscope.mcp import MCPClient, HttpMCPConfig
    async def exercise():
        manager = LocalWorkspaceManager(str(tmp_path))
        legacy = await manager.get_workspace('owner','agent','s0','legacy')
        first = await manager.get_workspace('owner','agent','s1','published-first')
        second = await manager.get_workspace('owner','agent','s2','published-second')
        assert len({legacy.workdir,first.workdir,second.workdir}) == 3
        connector = MCPClient(name='domain',is_stateful=False,mcp_config=HttpMCPConfig(url='http://unreachable.invalid/mcp'),enable_tools=['read'])
        await first.set_mcp_declarations([connector],agent_id='agent')
        assert first._declared_specs('agent','new-personal')[0].enable_tools == ['read']
        assert second.declared_mcps(agent_id='agent') == []
        await manager.close('published-first')
        restored = await manager.get_workspace('owner','agent','s3','published-first')
        assert restored._declared_specs('agent','new-team')[0].enable_tools == ['read']
        await manager.close_all()
    asyncio.run(exercise())
