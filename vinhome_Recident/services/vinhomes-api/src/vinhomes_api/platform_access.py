"""Ticket-scoped MCP Bearers. The control-plane token discovers tools and issues workflow grants.

Issue/revoke with the database owner's DATABASE_URL, never the API runtime role.
Tokens are written only to --output and only hashes are stored in PostgreSQL.
"""
import argparse
import asyncio
import hashlib
import os
import secrets
import hmac
import json
from contextvars import ContextVar
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from fastapi import APIRouter,Request,Response,HTTPException
from pydantic import BaseModel,Field

from .platform import TENANT

TOOLS=('vh_ticket_get','vh_knowledge_search','vh_staff_available','vh_work_order_dispatch',
       'vh_work_order_reschedule','vh_ticket_cancel','vh_ticket_add_note')
ACCESS: ContextVar[dict | None] = ContextVar('vinhomes_mcp_access',default=None)
router=APIRouter(tags=['Platform control-plane'])


async def find_grant(db, token: str) -> dict | None:
    row=(await db.execute(text(f"""select g.id,g.ticket_id,g.management_ref,g.tools from platform_mcp_grants g
        join platform_links l on l.ticket_id=g.ticket_id and l.tenant_id=g.tenant_id
        join tickets t on t.id=g.ticket_id and t.tenant_id=g.tenant_id
        join management_units m on m.id=t.management_unit_id and m.tenant_id=t.tenant_id
        where g.tenant_id={TENANT} and g.token_hash=:hash and g.revoked_at is null and g.expires_at>now()
          and g.management_ref=l.management_ref and g.management_ref=m.code and m.status='active'
          and (g.workflow_id is null or l.workflow_id is null or g.workflow_id=l.workflow_id)"""),
        {'hash':hashlib.sha256(token.encode()).hexdigest()})).mappings().first()
    return dict(row) if row else None


async def authorize(db, tool: str, ticket_id) -> None:
    from .platform_work import Refused
    access=ACCESS.get()
    if access is None:
        raise Refused('Cần Bearer grant được cấp riêng cho ticket. Token khởi tạo chỉ dùng khám phá MCP.','TICKET_GRANT_REQUIRED')
    current=await find_grant(db,access['token'])
    if current is None or str(current['ticket_id'])!=str(ticket_id).strip().lower() or tool not in current['tools']:
        raise Refused('Không có quyền dùng công cụ này cho ticket được yêu cầu.','TICKET_SCOPE_FORBIDDEN')


class GrantRequest(BaseModel):
    ticket_id: UUID
    external_request_id: UUID
    workflow_id: str=Field(min_length=1,max_length=200)
    grant_request_id: UUID
    tools: list[str]=Field(min_length=1,max_length=7)
    ttl_seconds: int=Field(default=3600,ge=60,le=86400)


@router.post('/platform/mcp-grants')
async def issue_for_workflow(body: GrantRequest,request: Request,response: Response):
    """Trusted platform backend only, never a model tool or a BQL approval step.

    The caller already holds the start command's external_request_id. A pending link can be bound before the
    start response reaches the domain; later calls check the workflow_id the domain actually received.
    """
    secret=os.getenv('VINHOMES_API_PLATFORM_MCP_TOKEN','').strip()
    if not secret or not hmac.compare_digest(request.headers.get('authorization','').encode(),('Bearer '+secret).encode()):
        raise HTTPException(401,'Control-plane credential required',headers={'WWW-Authenticate':'Bearer'})
    if getattr(request.app.state,'engine',None) is None:
        raise HTTPException(503,'Grant database unavailable')
    response.headers['Cache-Control']='no-store'
    if any(tool not in TOOLS for tool in body.tools) or len(set(body.tools))!=len(body.tools):
        raise HTTPException(422,'Unknown or duplicate tool grant')
    if any(ord(c)<32 for c in body.workflow_id):
        raise HTTPException(422,'Invalid workflow reference')
    payload=body.model_dump(mode='json',exclude={'grant_request_id'})
    canonical=json.dumps(payload,sort_keys=True,separators=(',',':'))
    fingerprint=hashlib.sha256(canonical.encode()).hexdigest()
    tenant=str(request.app.state.settings.tenant_id)
    token='vhm_'+hmac.new(secret.encode(),('vinhomes-mcp-v2:'+tenant+':'+str(body.grant_request_id)+':'+fingerprint).encode(),hashlib.sha256).hexdigest()
    token_hash=hashlib.sha256(token.encode()).hexdigest()
    async with request.app.state.engine.begin() as db:
        await db.execute(text("select set_config('app.tenant_id',:tenant,true)"),{'tenant':tenant})
        link=(await db.execute(text(f"""select l.management_ref,l.workflow_id,l.status from platform_links l
            join platform_commands c on c.ticket_id=l.ticket_id and c.tenant_id=l.tenant_id
            join tickets t on t.id=l.ticket_id and t.tenant_id=l.tenant_id
            where l.ticket_id=:ticket and l.tenant_id={TENANT} and c.id=:command and c.kind='start_workflow'
              and t.status not in ('closed','cancelled') for update of l"""),
            {'ticket':body.ticket_id,'command':body.external_request_id})).mappings().first()
        if not link or link['status'] not in ('pending','open') or (link['workflow_id'] and link['workflow_id']!=body.workflow_id):
            raise HTTPException(409,'No active handover bound to these references')
        await db.execute(text(f"""insert into platform_mcp_grants(id,tenant_id,ticket_id,management_ref,workflow_id,request_hash,token_hash,tools,expires_at)
            values (:id,{TENANT},:ticket,:management,:workflow,:hash,:token,:tools,now()+make_interval(secs=>:ttl))
            on conflict(id) do nothing"""),{'id':body.grant_request_id,'ticket':body.ticket_id,'management':link['management_ref'],
                'workflow':body.workflow_id,'hash':fingerprint,'token':token_hash,'tools':body.tools,'ttl':float(body.ttl_seconds)})
        grant=(await db.execute(text(f'select *,expires_at>now() as valid from platform_mcp_grants where id=:id and tenant_id={TENANT}'),{'id':body.grant_request_id})).mappings().first()
        if not grant or grant['request_hash']!=fingerprint or grant['token_hash']!=token_hash or grant['revoked_at'] or not grant['valid']:
            raise HTTPException(409,'Grant reference changed, expired or revoked; use a new grant_request_id when renewing')
        # A deterministic token supports lost-response retry without storing its plaintext.
        return {'grant_id':str(grant['id']),'ticket_id':str(grant['ticket_id']),'workflow_id':grant['workflow_id'],
                'bearer_token':token,'expires_at':grant['expires_at'].isoformat(),'tools':grant['tools']}


async def operator(args):
    import asyncpg
    from .database import _url
    db=await asyncpg.connect(_url(os.environ['DATABASE_URL']))
    try:
        async with db.transaction():
            await db.execute("select set_config('app.tenant_id',$1,true)",str(args.tenant))
            if args.command=='revoke':
                result=await db.execute('update platform_mcp_grants set revoked_at=now() where id=$1 and tenant_id=$2 and revoked_at is null',args.grant_id,args.tenant)
                print(result)
                return
            if not 1<=args.hours<=720:
                raise SystemExit('Grant lifetime must be 1–720 hours')
            tools=args.tools.split(',') if args.tools else list(TOOLS)
            if not tools or any(t not in TOOLS for t in tools):
                raise SystemExit('Unknown MCP tool')
            linked=await db.fetchrow('select management_ref from platform_links where ticket_id=$1 and tenant_id=$2 and status in (\'pending\',\'open\')',args.ticket,args.tenant)
            if linked is None:
                raise SystemExit('Ticket is not handed over and active')
            token='vhm_'+secrets.token_urlsafe(32)
            row=await db.fetchrow("""insert into platform_mcp_grants(tenant_id,ticket_id,management_ref,token_hash,tools,expires_at)
                values($1,$2,$3,$4,$5,now()+make_interval(hours=>$6)) returning id,expires_at""",
                args.tenant,args.ticket,linked['management_ref'],hashlib.sha256(token.encode()).hexdigest(),tools,args.hours)
            # O_EXCL prevents silently overwriting a credential. A failure rolls the grant back.
            fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w',encoding='utf-8') as file:
                file.write('VINHOMES_MCP_BEARER='+token+'\nGRANT_ID='+str(row['id'])+'\nEXPIRES_AT='+row['expires_at'].isoformat()+'\n')
            print('Grant issued; credential saved to private output file. grant_id='+str(row['id']))
    finally:
        await db.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    issue=sub.add_parser('issue'); issue.add_argument('--ticket',type=UUID,required=True)
    issue.add_argument('--tenant',type=UUID,required=True); issue.add_argument('--hours',type=int,default=24)
    issue.add_argument('--tools'); issue.add_argument('--output',type=Path,required=True)
    revoke=sub.add_parser('revoke'); revoke.add_argument('--grant-id',type=UUID,required=True); revoke.add_argument('--tenant',type=UUID,required=True)
    asyncio.run(operator(parser.parse_args()))


if __name__=='__main__':
    main()
