"""Resolve manager identity from auth DB and obtain area-scoped read grants."""
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy import text

from ...mcp import MCPClient


async def manager_clients(storage, auth_service, user_id, agent, clients):
    selected = {}
    for tool in (agent.data.spec or {}).get('tools', []):
        if tool.get('tool_name', '').startswith('vh_management_'):
            selected.setdefault(tool['mcp_id'], []).append(tool['tool_name'])
    if not selected:
        return clients
    if auth_service is None:
        raise HTTPException(409, 'Management MCP requires authenticated BQL identity')
    # Refresh account status and area on every run. Neither model inputs nor
    # a copied AgentSpec are authority to pick a different manager or area.
    async with auth_service._require_engine().connect() as db:
        row = (await db.execute(text('select tenant_id,domain_id,area_id,role,status from auth_users where id=:id'),
                                {'id': UUID(user_id)})).mappings().first()
    if not row or row['role'] != 'AREA_MANAGER' or row['status'] != 'active':
        raise HTTPException(403, 'Active BQL account required')
    output = list(clients)
    for mcp_id, names in selected.items():
        record = await storage.get_mcp(user_id, mcp_id)
        if not record or not record.enabled or record.client.mcp_config.type != 'http_mcp':
            raise HTTPException(409, 'Management connector unavailable')
        config = record.client.mcp_config
        parsed = urlsplit(config.url)
        if parsed.scheme not in {'http', 'https'} or parsed.path.rstrip('/') != '/mcp':
            raise HTTPException(409, 'Management connector must use the Domain /mcp endpoint')
        descriptors = {t['name']: t for t in record.discovered_tools}
        if any(descriptors.get(name, {}).get('read_only') is not True for name in names):
            raise HTTPException(409, 'Management tool catalog is stale or not read-only')
        prefix = '' if parsed.port == 8000 else '/api/business'
        endpoint = urlunsplit((parsed.scheme, parsed.netloc, prefix + '/platform/management-grants', '', ''))
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as http:
            response = await http.post(endpoint, headers=config.headers, json={
                'platform_tenant': row['tenant_id'], 'platform_domain': row['domain_id'],
                'platform_area': row['area_id'], 'platform_user': user_id, 'tools': names})
        if response.status_code != 200:
            raise HTTPException(409, 'Chưa có quyền BQL theo khu cho connector này; cần cấu hình binding Domain.')
        client = MCPClient.model_validate(record.client.model_dump(mode='json'))
        client.enable_tools = names
        client.disable_tools = None
        client.confirm_tools = None
        # Dedicated clone never changes the ticket grant or shared live client.
        client.mcp_config.headers = {'Authorization': 'Bearer ' + response.json()['bearer_token']}
        output = [c for c in output if c.name != client.name]
        output.append(client)
    return output
