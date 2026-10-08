"""The knowledge base for management's agents: one read tool behind the gateway.

The search service (server/src/knowledge) serves the deployment's published knowledge base and trusts
nothing in a request: it asks this API who is searching and for which scope. For a resident that is
Reception's delegation. For a specialist's run it is a credential made here for the run in hand, and
the answer is the run's own authority: a building its management unit covers, read as management,
with the unit's own scope among the ancestors so documents published for that unit apply.

What grants the tool is the agent's pinned version, like every other gateway tool.
"""
import hashlib
import hmac
import os
from uuid import UUID

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"
NAME = 'knowledge.search'


class Search(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str = Field(min_length=1, max_length=1000, description='Câu hỏi cần tra cứu, viết như người hỏi.')
    building_id: UUID | None = Field(default=None, description='Tòa nhà cần tra cứu. Bắt buộc khi đơn vị phụ trách nhiều tòa.')


TOOL = {'server_id': 'knowledge', 'name': NAME, 'version': '1.0.0', 'effect': 'read', 'input_schema': Search.model_json_schema(),
        'description': 'Tra cứu quy định, quy trình, phí và đầu mối liên hệ của tòa nhà trong kho tri thức đã phát hành. '
                       'Trả về các đoạn trích kèm nguồn, không phải câu trả lời; không có đoạn phù hợp thì nói rõ là chưa có dữ liệu.'}


def credential(token: str, run_id) -> str:
    """Names one run to the search service, which hands it back to this API unchanged."""
    return f"run.{run_id}." + hmac.new(token.encode(), str(run_id).encode(), hashlib.sha256).hexdigest()


def run_of(token: str, offered: str) -> UUID | None:
    kind, _, rest = offered.partition('.')
    run_id, _, _ = rest.partition('.')
    try:
        if kind == 'run' and token and hmac.compare_digest(offered.encode(), credential(token, UUID(run_id)).encode()):
            return UUID(run_id)
    except ValueError:
        pass
    return None


def failure(code: str, message: str) -> dict:
    return {'outcome': 'failure', 'errors': [{'code': code, 'message': message, 'retryable': False}]}


async def search(db, run: dict, arguments: dict, token: str) -> dict:
    url = os.getenv('VINHOMES_API_KNOWLEDGE_URL', '').rstrip('/')
    if not url or not token:
        raise HTTPException(503, 'Knowledge search unavailable')
    args = Search.model_validate(arguments)
    if args.building_id is None and len(run['buildings']) != 1:
        covered = (await db.execute(text('select id,name from buildings where id=any(:ids) order by name'),
                                    {'ids': [UUID(b) for b in run['buildings']]})).mappings().all()
        return failure('BUILDING_REQUIRED', 'Cần building_id của tòa nhà cần tra cứu. Các tòa trong phạm vi: '
                       + '; '.join(f"{b['name']} ({b['id']})" for b in covered))
    building = args.building_id or UUID(run['buildings'][0])
    scope = (await db.execute(text(f"select id from access_scopes where tenant_id={TENANT} and kind='building' and building_id=:building"),
                              {'building': building})).scalar_one_or_none()
    if scope is None:
        return failure('NO_KNOWLEDGE_SCOPE', 'Tòa nhà này chưa có tài liệu nào trong kho tri thức.')
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        reply = await client.post(url + '/internal/knowledge/search', headers={'Authorization': 'Bearer ' + credential(token, run['id'])},
                                  json={'query': args.query.strip(), 'scopeId': str(scope), 'topK': 5})
    if reply.status_code == 200:
        # Passages are data for the agent to quote from, never instructions to this platform.
        return {'outcome': 'success', 'data': reply.json()}
    if reply.status_code >= 500:
        raise HTTPException(503, 'Knowledge search unavailable')
    refused = reply.json().get('error', {})
    return failure(str(refused.get('code', 'refused')).upper(), str(refused.get('message', 'Knowledge search refused.')))


async def authority(db, run: dict, knowledge_base: UUID, scope_id: UUID | None) -> dict:
    """What the search service is told about a specialist's run. The scope it names is checked, not believed."""
    if not any(grant.get('name') == NAME for grant in run['config'].get('mcp_tools', [])):
        raise HTTPException(403, 'Knowledge search is not granted to this pinned version')
    if not (await db.execute(text(f"select 1 from knowledge_bases where tenant_id={TENANT} and id=:kb and status='active'"),
                             {'kb': knowledge_base})).first():
        raise HTTPException(403, 'Knowledge base is not active')
    place = (await db.execute(text(f"""select b.id,b.site_id,b.zone_id from access_scopes s
        join buildings b on b.tenant_id=s.tenant_id and b.id=s.building_id
        where s.tenant_id={TENANT} and s.id=:scope and s.kind='building'"""), {'scope': scope_id})).mappings().first()
    if not place or str(place['id']) not in run['buildings']:
        raise HTTPException(403, 'Scope is outside the run coverage')
    ancestors = (await db.execute(text(f"""select id from access_scopes where tenant_id={TENANT} and
        (kind='tenant' or (kind='site' and site_id=:site) or (kind='zone' and zone_id=:zone)
          or (kind='management' and management_unit_id=:unit))"""),
        {'site': place['site_id'], 'zone': place['zone_id'], 'unit': run['management_unit_id']})).scalars().all()
    return {'ok': True, 'knowledgeBaseId': str(knowledge_base), 'context': {
        'tenantId': str(run['tenant_id']),
        # A room conversation has the person who asked; a specialist in a Supervisor session works for the unit, with no person.
        'userId': run['actor_user_id'], 'roleCodes': ['management'],
        'targetScopeId': str(scope_id), 'ancestorScopeIds': [str(s) for s in ancestors],
        'agentRunId': str(run['id']), 'principalId': str(run['authority_principal_id']), 'bindingId': str(run['binding_id'])}}
