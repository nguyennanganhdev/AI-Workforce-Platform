"""Create one unpublished acceptance draft, construct with Factory, verify persistence and trial.

Uses local account files. Does not publish, revoke, approve accounts or change role defaults.
"""
import json
import uuid
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[1]
accounts={}
for line in (root/'services/vinhomes-api/.local-connected/accounts.txt').read_text(encoding='utf-8-sig').splitlines():
    role,_,record=line.partition(':')
    if ' / ' in record:accounts[role.strip()]=tuple(part.strip() for part in record.split(' / ',1))
base='http://localhost:3022'
out=root/'.codex-artifacts/operations-ui-2026-10-06/factory-acceptance.json'
def call(client,method,path,body=None):
    response=client.request(method,base+'/api/business'+path,json=body)
    if response.status_code>=400:
        try: detail=response.json().get('detail','Request failed')
        except ValueError: detail='Non-JSON error response'
        failure={'status':'refused' if response.status_code==422 else 'failed','http_status':response.status_code,'method':method,'operation':path,'reason':detail}
        if path.endswith('/construct'): failure['published']=False
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(failure,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(failure,ensure_ascii=True))
        raise RuntimeError(f'{method} {path}: HTTP {response.status_code}')
    return response.json()
result={}
with httpx.Client(timeout=150,headers={'Origin':base}) as client:
    call(client,'POST','/auth/login',{'identifier':accounts['management'][0],'password':accounts['management'][1]})
    room=call(client,'GET','/rooms')['items'][0]['id']
    model=next(m for m in call(client,'GET','/models/allowed')['items'] if m['name']=='gpt-6-luna')
    created=call(client,'POST',f'/rooms/{room}/agents',{'name':'Nghiệm thu Factory UI: tòa hoặc phân khu','purpose':'specialist',
                  'instructions':'Chưa cấu hình. Agent này chưa được phép chạy.','idempotency_key':'ops-ui-factory-acceptance-scopes-20261006'})
    agents=call(client,'GET',f'/rooms/{room}/agent-management')
    agent=next(a for a in agents['items'] if a['id']==created['id'])
    if agent.get('published') or agent['status']!='draft':raise RuntimeError('Acceptance agent must remain an unpublished draft.')
    skill=next((s for s in agents.get('skills',[]) if s['name']=='Nghiệm thu: phạm vi tòa hoặc phân khu'),None)
    if not skill:skill=call(client,'POST',f'/rooms/{room}/agent-skills',{'name':'Nghiệm thu: phạm vi tòa hoặc phân khu',
            'description':'Hỏi lại khi thiếu phạm vi tòa nhà/phân khu hoặc khoảng thời gian báo cáo.',
            'instructions':'Khi thiếu phạm vi tòa nhà/phân khu hoặc khoảng thời gian, hỏi lại trước khi tra cứu. Không tự đoán phạm vi hoặc số liệu.'})
    if not agent['configuration'].get('factory'):
        built=call(client,'POST',f"/rooms/{room}/agents/{agent['id']}/construct",{
            'role':'Trợ lý báo cáo tần suất yêu cầu cho Ban quản lý',
            'description':'Đọc báo cáo tần suất yêu cầu trong một tòa nhà HOẶC toàn phân khu và khoảng thời gian do BQL chỉ định. '
                          'Hỏi rõ loại phạm vi (tòa nhà hoặc phân khu), tên hoặc ID của phạm vi và thời gian nếu còn thiếu. '
                          'Chỉ dùng công cụ chọn phạm vi báo cáo và báo cáo tần suất yêu cầu. '
                          'Tóm tắt số liệu trả về, nêu giới hạn khi không có dữ liệu. Không sửa dữ liệu, không lập phương án, không gửi thông báo.',
            'service_categories':[], 'configuration_hash':agent['configurationHash'], 'revision_of':None,
            'model_id':model['id'],'skill_ids':[str(skill['id'])],'request_id':str(uuid.uuid4())})
        if built.get('needsInput'):
            result={'agent_id':agent['id'],'status':'clarification','questions':built['questions']}
            out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            raise RuntimeError('Acceptance description requires clarification; no draft was published.')
    saved=next(a for a in call(client,'GET',f'/rooms/{room}/agent-management')['items'] if a['id']==agent['id'])
    config=saved['configuration']
    assert config['model_id']==model['id'] and str(skill['id']) in config['skill_ids']
    assert config['instructions'] and config['mcp_tools'] and config['skill_snapshots']
    trial=call(client,'POST',f"/rooms/{room}/agents/{agent['id']}/try",{'configuration_hash':saved['configurationHash'],
            'question':'Hãy báo cáo tần suất yêu cầu. Tôi chưa chỉ định phạm vi tòa nhà/phân khu hoặc khoảng thời gian.'})
    assert trial.get('answer') and trial.get('called') == [], 'Agent must ask for missing scope before calling tools.'
    after_trial=next(a for a in call(client,'GET',f'/rooms/{room}/agent-management')['items'] if a['id']==agent['id'])
    assert after_trial['status'] == 'draft' and not after_trial['published']
    assert after_trial['configurationHash'] == saved['configurationHash'], 'Trial must not mutate the verified draft.'
    result={'agent_id':saved['id'],'room_id':room,'status':saved['status'],'published':saved['published'],
            'acceptance_scope':'building_or_zone',
            'selected_model':model['name'],'configuration_hash':saved['configurationHash'],'instructions_length':len(config['instructions']),
            'tools':config['mcp_tools'],'skill_snapshots':config['skill_snapshots'],
            'factory_spec_hash':config['factory']['artifact']['specHash'],'trial':trial,
            'post_trial_configuration_hash':after_trial['configurationHash']}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
