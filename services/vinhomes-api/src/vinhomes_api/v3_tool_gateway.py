"""Read gateway shared by session specialists and BQL room conversations.

Grants, pinned releases, actor authority and building coverage come from PostgreSQL.
Writes are deliberately refused here; the existing human approval APIs own effects.
"""
import inspect
import json
import os
from datetime import date
from uuid import UUID, uuid4
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import text
from .v3_coordination import Scope, TENANT, team_authority
from .v3_room_agents import managed_room
from .v3_reports import _management_building
from . import v3_report_jobs as reports
from .v3_agent_results import AgentBusinessResponse, agent_result
from .v3_billing import invoice_detail
from .v3_operations import catalogs
from .v3_security import cameras, contacts
from .v3_connections import connection, host, prepare_external_call
from .v3_audit import audit
from . import v3_agent_knowledge as agent_knowledge
from ._vendor.reporting.application.client import exact_decimal, invalid_constant, json_safe_numbers, unique_object
from ._vendor.reporting.tools.catalog import tool_descriptors
from ._vendor.reporting.tools.facade import ReportTools
from ._vendor.reporting.tools.contracts import RuntimeContext, ReportToolError

router = APIRouter(prefix='/internal/coordination/v1/tools', tags=['Authorized agent read tools'])


async def run_authority(db, run_id: UUID):
    row = (await db.execute(text('''select r.*,v.config,a.workspace_id,w.management_unit_id,
        m.team_id from agent_runs r join agent_versions v on v.id=r.version_id and v.tenant_id=r.tenant_id
        join agents a on a.id=r.agent_id and a.tenant_id=r.tenant_id and a.status='active'
        join agent_releases rel on rel.version_id=v.id and rel.tenant_id=v.tenant_id and rel.status='published' and rel.revoked_at is null
        join execution_principals p on p.id=r.authority_principal_id and p.tenant_id=r.tenant_id
          and p.status='active' and p.authz_version=r.authority_version
        join runtime_session_bindings b on b.id=r.binding_id and b.tenant_id=r.tenant_id and b.status='active'
        join workspaces w on w.id=a.workspace_id and w.tenant_id=a.tenant_id and w.status='active'
        left join team_members m on m.id=r.team_member_id and m.tenant_id=r.tenant_id
        where r.id=:run and r.status='running'
          and (m.id is null or (m.status='active' and m.version_id=r.version_id))'''), {'run': run_id})).mappings().first()
    if not row:
        raise HTTPException(403, 'Active run with a published pinned release required')
    run = dict(row)
    if run['team_id']:
        team = await team_authority(db, run['team_id'])
        if team['status'] in ('completed', 'cancelled', 'failed'):
            raise HTTPException(409, 'Session has finished')
    elif run['actor_user_id']:
        await managed_room((db, run['actor_user_id']), run['channel_id'], lock=False)
        if not (await db.execute(text("select 1 from users u join tenant_memberships m on m.user_id=u.id and m.tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid where u.id=:actor and u.status='active' and m.status='active'"), {'actor': run['actor_user_id']})).first():
            raise HTTPException(403, 'Requesting user is inactive')
    else:
        raise HTTPException(403, 'Run has no authorized conversation or session')
    run['buildings'] = tuple(str(b['id']) for b in await covered_buildings(db, run['management_unit_id']))
    return run


async def covered_buildings(db, management_unit_id):
    """The active buildings a management unit covers today: the only buildings its agents' tools may read."""
    return (await db.execute(text('''select distinct b.id,b.code,b.name from buildings b
        join management_coverage mc on mc.tenant_id=b.tenant_id and mc.management_unit_id=:management
          and mc.valid_from<=now() and (mc.valid_to is null or mc.valid_to>now())
        join access_scopes s on s.id=mc.scope_id and s.tenant_id=mc.tenant_id
          and (s.kind='tenant' or (s.kind='building' and s.building_id=b.id)
            or (s.kind='site' and s.site_id=b.site_id) or (s.kind='zone' and s.zone_id=b.zone_id))
        where b.status='active' order by b.code'''), {'management': management_unit_id})).mappings().all()


async def agent_workspace(db, workspace_id):
    """What an agent of this unit needs to call its tools: the current time and the ids of the buildings it may read.
    Without them a tool that takes building_id or a time cannot be called, and the agent asks people for ids."""
    management = (await db.execute(text('select management_unit_id from workspaces where id=:id'), {'id': workspace_id})).scalar_one_or_none()
    now = (await db.execute(text('''select to_char(now() at time zone 'Asia/Ho_Chi_Minh','YYYY-MM-DD"T"HH24:MI:SS"+07:00"')'''))).scalar_one()
    buildings = await covered_buildings(db, management) if management else []
    return {'now': now, 'timezone': 'Asia/Ho_Chi_Minh',
            'buildings': [{'id': str(b['id']), 'code': b['code'], 'name': b['name']} for b in buildings],
            'note': 'id chỉ dùng để gọi công cụ; khi trả lời, gọi tòa nhà bằng mã hoặc tên, không hiển thị id.'}


class BuildingRead(BaseModel):
    model_config = ConfigDict(extra='forbid')
    building_id: UUID


SECURITY = {
    'security.camera.read': ('Tra cứu danh mục camera; không mở luồng hình ảnh hay điều khiển thiết bị.', cameras),
    'security.contact.read': ('Tra cứu đầu mối khẩn cấp trong tòa nhà được giao; không gửi cảnh báo.', contacts),
}
# Served by the Bun tool host: Team Quang's technical tools and Team Hoàng's cleaning counterparts of them.
TOOL_HOST_SERVERS = ('technical-tools', 'cleaning-tools')


def catalogue():
    return ([{'server_id': 'reporting', 'name': 'reporting.' + t['name'], 'description': t['description'],
        'input_schema': t['inputSchema'], 'effect': t['effect'], 'version': t['version']} for t in tool_descriptors() if t['effect'] == 'read'] +
        [{'server_id': 'security-tools', 'name': name, 'description': description, 'version': '1.0.1',
          'input_schema': BuildingRead.model_json_schema(), 'effect': 'read'} for name, (description, _) in SECURITY.items()] +
        [agent_knowledge.TOOL])


class ReportingBackend:
    """Team Hoàng's report tools read this API's own routes. Here the same route functions run in the
    verified transaction, with no forged cookie, and each answer takes the JSON form its route sends."""
    operation_timeout_seconds, max_pages, max_records = 60.0, 100, 10000
    READS = {'/reports/employee-feedback': reports.feedback, '/reports/incident-frequency-summary': reports.incident_summary,
        '/reports/supporting-records': reports.supporting}
    NAMES = {'buildingId': 'building_id', 'staffId': 'staff_id', 'fromDate': 'from_date', 'toDate': 'to_date'}

    def __init__(self, db, run):
        self.db, self.run = db, run

    async def request(self, path, context, *, params=None):
        scope = (self.db, self.run['actor_user_id'] or '', not bool(self.run['actor_user_id']))
        if scope[1]:
            admin = (await self.db.execute(text('select 1 from platform_admins where user_id=:actor'), {'actor': scope[1]})).first() is not None
            scope = (self.db, scope[1], admin)
        if path == '/catalogs':
            return wire(jsonable_encoder(await catalogs(scope)))
        if path == '/reports/filter-options':
            # Build options inside this workspace, including staff/category rows. Do not
            # call an admin-global filter API and prune a partially leaked response.
            buildings = (await self.db.execute(text('select id,name from buildings where id=any(:ids) order by name'), {'ids': [UUID(b) for b in self.run['buildings']]})).mappings().all()
            categories = (await self.db.execute(text('select id,name,code from service_categories where enabled order by name'))).mappings().all()
            employees = (await self.db.execute(text('select sp.id,u.name,sp.employee_code from staff_profiles sp join users u on u.id=sp.user_id where sp.management_unit_id=:management order by u.name'), {'management': self.run['management_unit_id']})).mappings().all()
            return typed(agent_result('get_report_filter_options', {'buildings': [dict(b) for b in buildings], 'categories': [dict(c) for c in categories], 'employees': [dict(e) for e in employees], 'exportFormats': ['docx']}, {}))
        if path.startswith('/invoices/'):
            invoice = UUID(path.rsplit('/', 1)[-1])
            building = (await self.db.execute(text('select t.building_id from invoices i join tickets t on t.id=i.ticket_id and t.tenant_id=i.tenant_id where i.id=:id'), {'id': invoice})).scalar_one_or_none()
            if str(building) not in self.run['buildings']:
                raise ReportToolError('REPORT_SCOPE_FORBIDDEN')
            return wire(jsonable_encoder(await invoice_detail(invoice, scope)))
        func = self.READS.get(path)
        if not func:
            raise ReportToolError('REPORT_OPERATION_UNKNOWN')
        kwargs = {self.NAMES.get(k, k): v for k, v in (params or {}).items()}
        for k in ('building_id', 'staff_id'):
            if kwargs.get(k): kwargs[k] = UUID(kwargs[k])
        for k in ('from_date', 'to_date'):
            if kwargs.get(k): kwargs[k] = date.fromisoformat(kwargs[k])
        if str(kwargs.get('building_id')) not in self.run['buildings']:
            raise ReportToolError('REPORT_SCOPE_FORBIDDEN')
        for name, parameter in inspect.signature(func).parameters.items():
            if name not in kwargs and hasattr(parameter.default, 'default'):
                kwargs[name] = parameter.default.default
        # Pydantic defaults are present in the validated input, never FastAPI Query objects.
        return typed(await func(scope=scope, **kwargs))


def wire(value):
    """Read a route's JSON the way the report client reads it: exact decimals, no repeated keys."""
    return json_safe_numbers(json.loads(json.dumps(value), object_pairs_hook=unique_object,
        parse_constant=invalid_constant, parse_float=exact_decimal))


def typed(value):
    """The routes that declare AgentBusinessResponse send money as exact text, not as a float."""
    return wire(AgentBusinessResponse.model_validate(value).model_dump(mode='json'))


async def repair_categories(db):
    """Which categories count as repair work is this deployment's decision; the catalogue does not say."""
    codes = [c.strip() for c in os.getenv('VINHOMES_API_REPAIR_CATEGORY_CODES', '').split(',') if c.strip()]
    found = (await db.execute(text('select id from service_categories where enabled and code=any(:codes)'), {'codes': codes})).scalars().all()
    return tuple(str(c) for c in found)


class Call(BaseModel):
    model_config = ConfigDict(extra='forbid')
    run_id: UUID
    tool: str = Field(min_length=1, max_length=160)
    arguments: dict = Field(default_factory=dict)


@router.post('/call')
async def call(body: Call, request: Request, db: Scope):
    status, result = 'FORBIDDEN', None
    run, withheld, grant, session_context = None, False, None, None
    try:
        run = await run_authority(db, body.run_id)
        grants = [g for g in run['config'].get('mcp_tools', []) if g.get('name') == body.tool]
        if len(grants) != 1:
            raise HTTPException(403, 'Tool not granted to this pinned version')
        grant = grants[0]
        registered = (await db.execute(text("select t.effect,t.destructive,s.provenance,s.status from mcp_tools t join mcp_servers s on s.id=t.server_id where t.server_id=:server and t.name=:name"), {'server': grant['server_id'], 'name': body.tool})).mappings().first()
        if not registered or registered['destructive'] or registered['status'] != 'active':
            raise HTTPException(403, 'Tool or connection is unavailable')
        custom = registered['provenance'] == 'custom'
        if custom and run['team_id'] and run['actor_user_id']:
            from .v3_session_sources import session_call_context, session_source_enabled
            session_context = await session_call_context(db, run['actor_user_id'], run['channel_id'], run['agent_id'], body.run_id)
            if not await session_source_enabled(db, run['actor_user_id'], session_context['team_id'], grant['server_id']):
                raise HTTPException(403, 'External source is disabled for this session question')
        if custom:
            personal = (await db.execute(text("select 1 from channels where id=:room and kind='personal'"), {'room': run['channel_id']})).first()
            if personal and (await db.execute(text('select enabled from vh_private_chat_sources where channel_id=:room and server_id=:server'), {'room': run['channel_id'], 'server': grant['server_id']})).scalar_one_or_none() is not True:
                raise HTTPException(403, 'External source is disabled in this conversation')
        if registered['effect'] != 'read':
            if not custom or not run['actor_user_id']:
                raise HTTPException(403, 'Actions require an authenticated management confirmation')
            prepared = await prepare_external_call(db, run['actor_user_id'], run['channel_id'], run['agent_id'], grant['server_id'], body.tool, body.arguments, **({'session_id': session_context['team_id'], 'request_message_id': session_context['message_id']} if session_context else {}))
            await audit(db, run['actor_user_id'], 'agent.tool_called', 'agent_run', str(body.run_id), {'tool':body.tool,'status':'AWAITING_CONFIRMATION','connectionId':grant['server_id'],'channelId':run['channel_id']})
            return {'status': 'AWAITING_CONFIRMATION', 'data': prepared, 'errors': []}
        # An external server's arguments are its own: a field it happens to call building_id is not ours to read.
        building = None if custom else body.arguments.get('building_id')
        if building is not None and str(UUID(building)) not in run['buildings']:
            raise HTTPException(403, 'Building outside workspace coverage')
        if run['actor_user_id'] and building:
            is_admin = (await db.execute(text('select 1 from platform_admins where user_id=:actor'), {'actor': run['actor_user_id']})).first() is not None
            await _management_building((db, run['actor_user_id'], is_admin), UUID(building))
        if grant['server_id'] == 'reporting' and body.tool.startswith('reporting.'):
            # The facade needs a nonempty transport credential when used over HTTP. This
            # in-process port carries no credential and never transmits this marker.
            context = RuntimeContext(str(run['authority_principal_id']), run['buildings'], 'verified-in-process', await repair_categories(db))
            result = await ReportTools(ReportingBackend(db, run), context).invoke(body.tool.removeprefix('reporting.'), body.arguments)
        elif grant['server_id'] == 'security-tools' and body.tool in SECURITY:
            args = BuildingRead.model_validate(body.arguments)
            payload = await SECURITY[body.tool][1]((db, run['actor_user_id'] or '', True), args.building_id)
            result = {'outcome': 'success', 'data': jsonable_encoder(payload), 'limitations': ['Camera catalogue only; live device feeds are not connected.']}
        elif grant['server_id'] == 'knowledge' and body.tool == agent_knowledge.NAME:
            result = await agent_knowledge.search(db, run, body.arguments, request.app.state.settings.coordination_service_token or '')
        elif grant['server_id'] in TOOL_HOST_SERVERS:
            url, token = os.getenv('VINHOMES_API_TECHNICAL_TOOLS_URL', '').rstrip('/'), os.getenv('VINHOMES_API_TECHNICAL_TOOLS_TOKEN', '')
            if not url or len(token) < 32:
                raise HTTPException(503, 'Technical tool host unavailable')
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                reply = await client.post(url + '/call', headers={'Authorization': 'Bearer ' + token}, json=body.model_dump(mode='json'))
                # The host answers every call it decided with its envelope and repeats the verdict in
                # the HTTP status (404 for "nothing in force"). Only a reply without one is an outage.
                result = reply.json() if reply.status_code < 500 else None
                if not isinstance(result, dict) or 'status' not in result:
                    raise HTTPException(503, 'Technical tool host unavailable')
        elif custom:
            server = await connection(db, grant['server_id'], lock=True)
            if server['status'] != 'active':
                raise HTTPException(403, 'Connection was suspended or is awaiting approval')
            if personal and (await db.execute(text('select enabled from vh_private_chat_sources where channel_id=:room and server_id=:server for share'), {'room': run['channel_id'], 'server': grant['server_id']})).scalar_one_or_none() is not True:
                raise HTTPException(403, 'External source is disabled in this conversation')
            if session_context and not await session_source_enabled(db, run['actor_user_id'], session_context['team_id'], grant['server_id']):
                raise HTTPException(403, 'External source is disabled for this session question')
            if server['workspace_id'] not in (None, run['workspace_id']):
                raise HTTPException(403, 'Connection belongs to another group')
            if server['credential_id'] and not server['sealed']:
                raise HTTPException(403, 'Connection credential was withdrawn')
            try:
                answer = await host('/call', {'url': server['url'], 'sealed': server['sealed'],
                    'tool': body.tool.removeprefix(grant['server_id'] + '.'), 'arguments': body.arguments})
            except HTTPException as refusal:
                # 400: the host kept arguments that carry a credential. The agent is told where, so it can ask again.
                if refusal.status_code != 400:
                    raise
                answer, withheld = {'isError': True, 'text': refusal.detail, 'truncated': False}, True
            # What the server said is data for the agent to read, never an instruction to this platform.
            result = {'outcome': 'failure' if answer['isError'] else 'success',
                      'data': {'text': answer['text'], 'truncated': answer['truncated']}}
            if answer['isError']:
                result['errors'] = [{'code': 'TOOL_ERROR', 'message': answer['text'][:2000], 'retryable': False}]
        else:
            raise HTTPException(403, 'Tool server not bound to this gateway')
        status = 'OK' if result.get('outcome') != 'failure' else 'TOOL_ERROR'
        if grant['server_id'] in TOOL_HOST_SERVERS:
            status = result.get('status', 'TOOL_ERROR')
        if withheld:
            status = 'ARGUMENTS_WITHHELD'
    except HTTPException as error:
        status = 'INTERNAL_ERROR' if error.status_code >= 500 else 'FORBIDDEN'
        result = None
    except httpx.HTTPError:
        status, result = 'INTERNAL_ERROR', None
    except (ValueError, ValidationError):
        status = 'INVALID_INPUT'
        result = None
    await db.execute(text(f'''insert into audit_events(tenant_id,initiator_kind,initiator_id,event_type,target_type,target_id,payload,correlation_id)
        values({TENANT},'agent',:agent,'agent.tool_called','agent_run',:run,cast(:payload as jsonb),:correlation)'''),
        {'agent': run['agent_id'] if run else 'refused-runtime-call', 'run': str(body.run_id),
         'payload': json.dumps({'tool': body.tool, 'status': status, 'connectionId': grant['server_id'] if grant else None, 'actorUserId': run['actor_user_id'] if run else None, 'channelId': run['channel_id'] if run else None}), 'correlation': uuid4()})
    from .v3_agent_eval_sandbox import record_tool_trace
    await record_tool_trace(db, run, body.run_id, grant['server_id'] if grant else None, body.tool, body.arguments, status, result)
    told = result.get('errors') if isinstance(result, dict) and status != 'OK' else None
    return {'status': status, 'data': result, 'errors': [] if status == 'OK' else told or [{'code': status, 'message': 'Tool is unavailable or outside this run permission.', 'retryable': status == 'INTERNAL_ERROR'}]}
