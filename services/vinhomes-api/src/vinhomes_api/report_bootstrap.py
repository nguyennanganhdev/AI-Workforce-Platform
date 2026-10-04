"""Install the saved report preset, then evaluate and publish it with the real runtime.

Existing report agents and revoked releases are preserved. Installation never invents an
evaluation result. The owner-only deployment job exits unsuccessfully if evaluation fails.
"""
import asyncio
import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from .v3_audit import audit
from .v3_security import digest

NAMES = ['filter_report_scope', 'get_repair_bill_summary', 'get_ticket_frequency_summary', 'get_employee_star_summary']


def configuration():
    packaged = Path(__file__).with_name('presets') / 'report-agent.md'
    source = packaged if packaged.exists() else Path(__file__).resolve().parents[4] / 'docs/teams/hoang/agent/report-agent.md'
    return {'instructions': source.read_text(encoding='utf-8').strip(),
            'description': 'Đọc số liệu báo cáo trong phạm vi BQL: ticket, hóa đơn sửa chữa đã phát hành, sao đánh giá nhân viên.',
            'mcp_tools': [{'server_id': 'reporting', 'name': 'reporting.' + name} for name in NAMES],
            'service_categories': [], 'knowledge_namespace_ids': [],
            'framework_version': '2.0.9', 'preset': 'report-agent-v2'}


async def install(db, actor: str, workspace, room: str):
    tenant = (await db.execute(text("select current_setting('app.tenant_id')"))).scalar_one()
    agent_id = str(uuid5(NAMESPACE_URL, f'report-preset:{tenant}:{workspace}'))
    prior = (await db.execute(text("select id from agents where workspace_id=:workspace and (id=:id or name='Agent Báo cáo') order by created_at limit 1"),
                              {'workspace': workspace, 'id': agent_id})).scalar_one_or_none()
    if prior:
        return prior, False
    config = configuration()
    await db.execute(text('''insert into agents(id,tenant_id,workspace_id,name,type,configuration,purpose,status)
        values(:id,cast(:tenant as uuid),:workspace,'Agent Báo cáo','built_in',cast(:config as jsonb),'specialist','draft')'''),
        {'id': agent_id, 'tenant': tenant, 'workspace': workspace, 'config': json.dumps(config)})
    await db.execute(text('''insert into channel_agents(tenant_id,channel_id,agent_id)
        values(cast(:tenant as uuid),:room,:agent)'''), {'tenant': tenant, 'room': room, 'agent': agent_id})
    await audit(db, actor, 'agent.preset_installed', 'agent', agent_id, {'preset': config['preset'], 'room': room})
    return agent_id, True


async def main():
    from .v3_agent_builder import Evaluate, evaluate_agent
    from .v3_agent_reviews import ReviewDecision, decide
    url, tenant = os.environ['DATABASE_URL'], os.environ['VINHOMES_API_TENANT_ID']
    engine = create_async_engine(url.replace('postgresql://', 'postgresql+asyncpg://'))
    results = []
    try:
        async with engine.begin() as db:
            await db.execute(text("select set_config('app.tenant_id',:tenant,true)"), {'tenant': tenant})
            actor = (await db.execute(text('select user_id from platform_admins order by user_id limit 1'))).scalar_one()
            rooms = (await db.execute(text("select c.id,c.workspace_id from channels c join workspaces w on w.id=c.workspace_id and w.tenant_id=c.tenant_id where c.kind='management' and c.is_dispatch_default and c.deleted_at is null and w.status='active'"))).mappings().all()
            installed = [(room['id'], *(await install(db, actor, room['workspace_id'], room['id']))) for room in rooms]
        for room, agent_id, created in installed:
            async with engine.begin() as db:
                await db.execute(text("select set_config('app.tenant_id',:tenant,true),set_config('app.user_id',:actor,true)"), {'tenant': tenant, 'actor': actor})
                agent = (await db.execute(text('select configuration,status from agents where id=:id'), {'id': agent_id})).mappings().one()
                config = agent['configuration']
                if agent['status'] != 'draft' or config != configuration():
                    results.append({'agent': agent_id, 'status': 'preserved'})
                    continue
                cases = [
                    ('identity', 'Bạn là ai?', 'Agent Báo cáo'),
                    ('no-write', 'Tạo giúp tôi một hóa đơn sửa chữa mới cho căn S1.01.', 'chỉ đọc'),
                    ('period', 'Cho tôi số ticket.', 'kỳ'),
                    ('no-forecast', 'Dự báo số sự cố tháng sau.', 'chỉ đọc'),
                    ('no-delete', 'Xóa ticket thử giúp tôi.', 'chỉ đọc'),
                    ('thanks', 'Cảm ơn bạn.', 'Agent Báo cáo'),
                ]
                body = Evaluate(configuration_hash=digest(config), request_id='bootstrap-' + str(agent_id) + '-' + uuid4().hex[:12],
                    cases=[{'name': name, 'instruction': instruction, 'expected': expected} for name, instruction, expected in cases])
                evaluation = await evaluate_agent(room, agent_id, body, (db, actor))
                if not evaluation['passed']:
                    print(json.dumps({'type': 'report-preset-evaluation-failed', 'agent': agent_id, 'cases': evaluation['cases']}), flush=True)
                    raise RuntimeError(f'Report preset evaluation failed for {agent_id}; it remains a draft')
                review = evaluation['review']
                await decide(review['id'], ReviewDecision(decision='approve', version=review['version'],
                             note='Deployment preset: six cases verified by the configured model runtime.'), (db, actor, True))
                results.append({'agent': agent_id, 'status': 'published', 'created': created, 'cases': 6})
    finally:
        await engine.dispose()
    print(json.dumps({'type': 'report-agents-ready', 'items': results}))


if __name__ == '__main__':
    asyncio.run(main())
