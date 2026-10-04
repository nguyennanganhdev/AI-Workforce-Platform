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
from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import text
from .v3_coordination import Scope, TENANT, team_authority
from .v3_room_agents import managed_room
from .v3_reports import _management_building
from . import v3_report_jobs as reports
from .v3_security import cameras, contacts
from ._vendor.reporting.tools.catalog import tool_descriptors
from ._vendor.reporting.tools.facade import ReportTools, ROUTES, ALIASES
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
    buildings = (await db.execute(text('''select distinct b.id from buildings b
        join management_coverage mc on mc.tenant_id=b.tenant_id and mc.management_unit_id=:management
          and mc.valid_from<=now() and (mc.valid_to is null or mc.valid_to>now())
        join access_scopes s on s.id=mc.scope_id and s.tenant_id=mc.tenant_id
          and (s.kind='tenant' or (s.kind='building' and s.building_id=b.id)
            or (s.kind='site' and s.site_id=b.site_id) or (s.kind='zone' and s.zone_id=b.zone_id))
        where b.status='active' '''), {'management': run['management_unit_id']})).scalars().all()
    run['buildings'] = tuple(str(b) for b in buildings)
    return run


class BuildingRead(BaseModel):
    model_config = ConfigDict(extra='forbid')
    building_id: UUID


SECURITY = {
    'security.camera.read': ('Tra cứu danh mục camera; không mở luồng hình ảnh hay điều khiển thiết bị.', cameras),
    'security.contact.read': ('Tra cứu đầu mối khẩn cấp trong tòa nhà được giao; không gửi cảnh báo.', contacts),
}


def catalogue():
    return ([{'server_id': 'reporting', 'name': 'reporting.' + t['name'], 'description': t['description'],
        'input_schema': t['inputSchema'], 'effect': t['effect']} for t in tool_descriptors() if t['effect'] == 'read'] +
        [{'server_id': 'security-tools', 'name': name, 'description': description,
          'input_schema': BuildingRead.model_json_schema(), 'effect': 'read'} for name, (description, _) in SECURITY.items()])


class ReportingBackend:
    """Run the existing business reads in this verified transaction, with no forged cookie."""
    def __init__(self, db, run):
        self.db, self.run = db, run

    async def request(self, method, path, context, *, params=None, body=None):
        if method != 'GET':
            raise ReportToolError('HUMAN_APPROVAL_REQUIRED')
        scope = (self.db, self.run['actor_user_id'] or '', not bool(self.run['actor_user_id']))
        if scope[1]:
            admin = (await self.db.execute(text('select 1 from platform_admins where user_id=:actor'), {'actor': scope[1]})).first() is not None
            scope = (self.db, scope[1], admin)
        if path == '/reports/filter-options':
            # Build options inside this workspace, including staff/category rows. Do not
            # call an admin-global filter API and prune a partially leaked response.
            from .v3_agent_results import agent_result
            buildings = (await self.db.execute(text('select id,name from buildings where id=any(:ids) order by name'), {'ids': [UUID(b) for b in self.run['buildings']]})).mappings().all()
            categories = (await self.db.execute(text('select id,name,code from service_categories where enabled order by name'))).mappings().all()
            employees = (await self.db.execute(text('select sp.id,u.name,sp.employee_code from staff_profiles sp join users u on u.id=sp.user_id where sp.management_unit_id=:management order by u.name'), {'management': self.run['management_unit_id']})).mappings().all()
            return jsonable_encoder(agent_result('get_report_filter_options', {'buildings': [dict(b) for b in buildings], 'categories': [dict(c) for c in categories], 'employees': [dict(e) for e in employees], 'exportFormats': ['docx']}, {}))
        funcs = {'/reports/employee-performance': reports.performance, '/reports/employee-feedback': reports.feedback,
            '/reports/repair-revenue': reports.repair_revenue, '/reports/incident-frequency-summary': reports.incident_summary,
            '/reports/supporting-records': reports.supporting}
        func = funcs.get(path)
        if not func:
            if path.startswith('/reports/exports/') and scope[1]:
                export_id = UUID(path.rsplit('/', 1)[-1])
                building = (await self.db.execute(text('select building_id from vh_report_exports where id=:id and created_by=:actor'),
                    {'id': export_id, 'actor': scope[1]})).scalar_one_or_none()
                if building is None or str(building) not in self.run['buildings']:
                    raise ReportToolError('REPORT_SCOPE_FORBIDDEN')
                return jsonable_encoder(await reports.export_status(export_id, scope))
            raise ReportToolError('REPORT_OPERATION_UNKNOWN')
        reverse = {v: k for k, v in ALIASES.items()}
        kwargs = {reverse.get(k, k): v for k, v in (params or {}).items()}
        for k in ('building_id', 'category_id', 'staff_id'):
            if kwargs.get(k): kwargs[k] = UUID(kwargs[k])
        for k in ('from_date', 'to_date'):
            if kwargs.get(k): kwargs[k] = date.fromisoformat(kwargs[k])
        for name, parameter in inspect.signature(func).parameters.items():
            if name not in kwargs and hasattr(parameter.default, 'default'):
                kwargs[name] = parameter.default.default
        # Pydantic defaults are present in the validated input, never FastAPI Query objects.
        return jsonable_encoder(await func(scope=scope, **kwargs))


class Call(BaseModel):
    model_config = ConfigDict(extra='forbid')
    run_id: UUID
    tool: str = Field(min_length=1, max_length=160)
    arguments: dict = Field(default_factory=dict)


@router.post('/call')
async def call(body: Call, db: Scope):
    status, result = 'FORBIDDEN', None
    run = None
    try:
        run = await run_authority(db, body.run_id)
        grants = [g for g in run['config'].get('mcp_tools', []) if g.get('name') == body.tool]
        if len(grants) != 1:
            raise HTTPException(403, 'Tool not granted to this pinned version')
        grant = grants[0]
        if not (await db.execute(text("select 1 from mcp_tools where server_id=:server and name=:name and effect='read' and not destructive"), {'server': grant['server_id'], 'name': body.tool})).first():
            raise HTTPException(403, 'Actions require separate human approval')
        building = body.arguments.get('building_id')
        if building is not None and str(UUID(building)) not in run['buildings']:
            raise HTTPException(403, 'Building outside workspace coverage')
        if run['actor_user_id'] and building:
            is_admin = (await db.execute(text('select 1 from platform_admins where user_id=:actor'), {'actor': run['actor_user_id']})).first() is not None
            await _management_building((db, run['actor_user_id'], is_admin), UUID(building))
        if grant['server_id'] == 'reporting' and body.tool.startswith('reporting.'):
            # The facade needs a nonempty transport credential when used over HTTP. This
            # in-process port carries no credential and never transmits this marker.
            context = RuntimeContext(str(run['authority_principal_id']), run['buildings'], 'verified-in-process')
            result = await ReportTools(ReportingBackend(db, run), context).invoke(body.tool.removeprefix('reporting.'), body.arguments)
        elif grant['server_id'] == 'security-tools' and body.tool in SECURITY:
            args = BuildingRead.model_validate(body.arguments)
            payload = await SECURITY[body.tool][1]((db, run['actor_user_id'] or '', True), args.building_id)
            result = {'outcome': 'success', 'data': jsonable_encoder(payload), 'limitations': ['Camera catalogue only; live device feeds are not connected.']}
        elif grant['server_id'] == 'technical-tools':
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
        else:
            raise HTTPException(403, 'Tool server not bound to this gateway')
        status = 'OK' if result.get('outcome') != 'failure' else 'TOOL_ERROR'
        if grant['server_id'] == 'technical-tools':
            status = result.get('status', 'TOOL_ERROR')
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
         'payload': json.dumps({'tool': body.tool, 'status': status}), 'correlation': uuid4()})
    told = result.get('errors') if isinstance(result, dict) and status != 'OK' else None
    return {'status': status, 'data': result, 'errors': [] if status == 'OK' else told or [{'code': status, 'message': 'Tool is unavailable or outside this run permission.', 'retryable': status == 'INTERNAL_ERROR'}]}
