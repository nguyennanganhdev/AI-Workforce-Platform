"""Provision reviewed local Platform resources through admin APIs, without LLMs."""
import argparse
import json
from pathlib import Path
import sys

import httpx

from configure_vin_owner import docker, inspect, environment


def provision(output, model):
    state = json.loads((output / 'state.json').read_text(encoding='utf-8'))
    prefix = state['prefix']
    assert prefix.startswith('vin-n1-r04-e2e-') and '.artifacts' in output.resolve().parts
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'vinhome_Recident/services/vinhomes-api/tests'))
    from vin_platform_local_fixture import PASSWORD
    with httpx.Client(base_url='http://127.0.0.1:18104/api', trust_env=False, timeout=40) as api:
        def call(method, path, **kwargs):
            response = api.request(method, path, **kwargs)
            if response.status_code >= 400:
                raise RuntimeError(method + ' ' + path + ' HTTP ' + str(response.status_code))
            return response.json() if response.content else None
        login = call('POST', '/auth/login', json={'tenant_id': 'default', 'identity': 'fixtureadmin', 'password': PASSWORD})
        api.headers['Authorization'] = 'Bearer ' + login['access_token']
        admin = state['platform_seed']['admin']
        roles = ('VIN_USER', 'PLATFORM_ADMIN', 'DOMAIN_ADMIN', 'AREA_MANAGER')
        for role in roles:
            subject = 'role:' + role
            current = call('GET', '/admin/vin/quota-policies', params={'subject': subject})['items']
            revision = current[0]['revision'] if current else 0
            call('PUT', '/admin/vin/quota-policies/' + subject, params={'expected_revision': revision}, json={
                'daily_tokens': 200000, 'monthly_tokens': 200000, 'max_output_tokens': 4096,
                'max_concurrency': 2, 'storage_bytes': 100000000, 'max_file_bytes': 10000000,
                'embedding_daily_tokens': 0, 'models': [model], 'enabled': True})

        def publish(kind, resource_id, name, description='', **fields):
            rows = call('GET', '/admin/vin/catalog', params={'kind': kind, 'resource_id': resource_id})['items']
            current = next((item for item in rows if item['resource_id'] == resource_id), None)
            result = call('POST', '/admin/vin/catalog', json=dict(kind=kind, resource_id=resource_id,
                owner_id=admin, version=current['version'] + 1 if current else 1, name=name,
                description=description, active=True, **fields))
            ident = result['id']
            grants = call('GET', '/admin/vin/grants', params={'catalog_id': ident, 'active': True})['items']
            for role in roles:
                if not any(g['subject_kind'] == 'role' and g['subject_id'] == role and set(g['permissions']) >= {'view', 'bind', 'execute'} for g in grants):
                    call('POST', '/admin/vin/grants', json={'catalog_id': ident, 'subject_kind': 'role',
                        'subject_id': role, 'permissions': ['view', 'bind', 'execute']})
            return ident

        publish('credential', 'vin-platform-openai', 'Model Platform · ' + model, model_names=[model])
        # Discovery is read-only. Its control token is stripped from the stored
        # customer record before any grant is published. Runtime gets per-ticket auth.
        mcps = call('GET', '/mcp')
        mcp = next((row for row in mcps if row['name'] == 'vinhomes-customer'), None)
        if mcp is None:
            token = environment(inspect(prefix + '-domain-rc'))['VINHOMES_API_PLATFORM_MCP_TOKEN']
            mcp = call('POST', '/mcp', json={'name': 'vinhomes-customer', 'display_name': 'Vinhomes · Dịch vụ của bạn',
                'url': 'http://127.0.0.1:18101/mcp', 'api_key': token,
                'description': 'Dịch vụ Vinhomes theo yêu cầu của chính bạn; quyền cấp riêng từng ticket. Không có quyền BQL hoặc ký quyết định thay cư dân.'})
        patch = '''import asyncio,os,json
from agentscope.app.storage import RedisStorage
from agentscope.app._service._customer_mcp import CUSTOMER_TOOLS
async def main():
 async with RedisStorage(host=os.environ['REDIS_HOST'],port=int(os.environ['REDIS_PORT']),password=os.environ.get('REDIS_PASSWORD') or None) as storage:
  record=await storage.get_mcp(OWNER,IDENT)
  record.tags=['domain','vin-customer-domain:vinhomes']
  record.discovered_tools=[t for t in record.discovered_tools if t['name'] in CUSTOMER_TOOLS]
  assert len(record.discovered_tools)==8
  record.client.enable_tools=[t['name'] for t in record.discovered_tools]
  record.client.mcp_config.headers=None
  record.client.confirm_tools=[t['name'] for t in record.discovered_tools if not t.get('read_only')]
  record.values={}
  await storage.upsert_mcp(OWNER,record)
  print(json.dumps({'tool_names':record.client.enable_tools,'bootstrap_credentials_stored':False}))
asyncio.run(main())'''.replace('OWNER', repr(admin)).replace('IDENT', repr(mcp['id']))
        tools = json.loads(docker('exec', '-i', prefix + '-platform-rc', 'python', '-', data=patch))
        publish('mcp', mcp['id'], 'Vinhomes · Dịch vụ của bạn', mcp['description'], tool_names=tools['tool_names'])
        skills = [
            ('vin-service-intake', 'Tiếp nhận yêu cầu Vinhomes', '# Tiếp nhận yêu cầu\nDùng CustomerService context trước. Hỏi rõ căn hộ, vị trí và nội dung còn thiếu; chỉ gửi create khi khách yêu cầu. Đọc đúng ID từ Domain. Không chuyển hội thoại sang BQL. Không tự ký xác nhận, báo giá hoặc nghiệm thu. Giao việc qua công cụ Domain đã được cấp, không hứa đã có nhân viên nếu chưa có receipt.'),
            ('vin-service-progress', 'Theo dõi tiến độ Vinhomes', '# Theo dõi tiến độ\nĐọc timeline canonical và as_of/sync_status trước khi trả lời. Tách đã tiếp nhận, đã phân công, đang làm, chờ xác nhận và hoàn tất. Chỉ nêu nhân viên, ảnh hoặc lịch đã có bằng chứng. Khi lỗi đồng bộ, nói rõ dữ liệu chưa cập nhật. Cư dân tự bấm thẻ quyết định trên Platform; chat không thay chữ ký.'),
            ('platform-source-citations', 'Trả lời có nguồn', '# Trả lời có nguồn\nChỉ dùng kho đã được cấp và tài liệu được duyệt. Trích tên nguồn, phiên bản và phạm vi áp dụng. Không suy nội quy hoặc phí Vin từ hướng dẫn sử dụng Platform. Nếu thiếu tài liệu nghiệp vụ, nói chưa có nguồn xác nhận. Không tiết lộ dữ liệu cư dân khác, thông tin cấu hình hay khóa dịch vụ.')]
        skill_ids = []
        for name, description, markdown in skills:
            existing = next((row for row in call('GET', '/skill') if row['name'] == name), None)
            row = existing or call('POST', '/skill', json={'name': name, 'description': description, 'markdown': markdown, 'tags': ['vin-platform', 'customer']})
            call('POST', '/skill/' + row['id'] + '/review', json={'status': 'approved'})
            publish('skill', row['id'], description)
            skill_ids.append(row['id'])
        bases = call('GET', '/knowledge_bases/')['knowledge_bases']
        kb = next((row for row in bases if row['name'] == 'Hướng dẫn sử dụng Platform'), None)
        kb_id = kb['id'] if kb else call('POST', '/knowledge_bases/lexical', json={
            'name': 'Hướng dẫn sử dụng Platform', 'description': 'Tài liệu sử dụng ứng dụng; không thay nội quy, biểu phí hoặc tài liệu nghiệp vụ Vin.'})['knowledge_base_id']
        docs = call('GET', '/knowledge_bases/' + kb_id + '/documents')['documents']
        if not any(row.get('filename') == 'huong-dan-platform.md' for row in docs):
            doc = call('POST', '/knowledge_bases/' + kb_id + '/references', json={'filename': 'huong-dan-platform.md',
                'source_ref': 'platform://user-guide/2026-10-18', 'text':
                '# Hướng dẫn Platform\nMỗi khách hàng có Leader, agent, hội thoại, kho riêng và lịch riêng. Liên kết Vinhomes ở trang Kết nối rồi gửi yêu cầu trong Leader. Theo dõi tiến độ và ảnh kết quả trong thẻ yêu cầu. Quyết định báo giá, phương án, nghiệm thu phải do bạn tự xem và bấm nút cuối; lời chat không thay xác nhận.\nMCP, provider và skill do quản trị cấp có thể xem, chọn và dùng nhưng không sửa. Builder cho phép soạn agent, review, chạy eval rồi phát hành. Lịch tự động chỉ chạy cho agent đã phát hành; lịch once chạy một lần. Kênh Discord cá nhân cần xác minh Discord ID của chủ và bot riêng.\nKho tri thức văn bản tìm theo từ khóa không cần embedding. Kho này chỉ hướng dẫn sử dụng ứng dụng, không chứa nội quy, biểu phí hoặc cam kết nghiệp vụ Vin. Quản trị cần bổ sung tài liệu nghiệp vụ đúng nguồn và đúng đối tượng trước khi dùng làm căn cứ trả lời.'})
            call('POST', f'/knowledge_bases/{kb_id}/references/{doc["document_id"]}/review', json={'status': 'approved'})
        publish('knowledge_base', kb_id, 'Hướng dẫn sử dụng Platform')
        report = dict(status='PROVISIONED', model=model, mcp_id=mcp['id'], domain_tools=tools['tool_names'],
            skill_ids=skill_ids, knowledge_base_id=kb_id, kb_mode='lexical', real_Vin_business_documents_loaded=False,
            embedding_enabled=False, real_provider_requests=0, paid_model_calls=0)
        (output / 'owner-resources.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--model', default='gpt-6-luna')
    args = parser.parse_args()
    provision(args.fixture.resolve(), args.model)
