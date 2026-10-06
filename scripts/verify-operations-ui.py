"""Headless browser acceptance of the deployed Operations surface. No credentials in artifacts."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser()
parser.add_argument('--base',default='http://localhost:3022')
parser.add_argument('--output',default='.codex-artifacts/operations-ui-2026-10-06')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
output=root/args.output; output.mkdir(parents=True,exist_ok=True)
secret_dir=root/'services/vinhomes-api/.local-connected'
accounts={}
for line in (secret_dir/'accounts.txt').read_text(encoding='utf-8-sig').splitlines():
    role,_,record=line.partition(':')
    if ' / ' in record:
        accounts[role.strip()]=tuple(part.strip() for part in record.split(' / ',1))
admin={line.partition(':')[0].strip().lower():line.partition(':')[2].strip() for line in (secret_dir/'initial-admin.txt').read_text(encoding='utf-8-sig').splitlines() if ':' in line}
accounts['admin']=(admin['login'],admin['password'])
results=[]
def capture(page, errors, role, label, viewport):
    filename=f'{role}-{label}-{viewport}.png'
    page.screenshot(path=str(output/filename), full_page=True)
    results.append({'role':role, 'page':label, 'viewport':viewport,
                    'overflow':page.evaluate('document.documentElement.scrollWidth>innerWidth'),
                    'alerts':page.locator('[role=alert]').all_text_contents(), 'errors':errors[:], 'screenshot':filename})
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    for role,pages in [('management',['team','ask','agents','reports']),('admin',['','accounts','units','connections','models','audit','team','agents','reports'])]:
        context=browser.new_context(viewport={'width':1440,'height':900},locale='vi-VN',timezone_id='Asia/Ho_Chi_Minh',reduced_motion='reduce')
        identifier,password=accounts[role]
        signed=context.request.post(args.base+'/api/business/auth/login',data={'identifier':identifier,'password':password},headers={'Origin':args.base})
        if signed.status!=200:
            raise RuntimeError(f'Authentication for {role} returned HTTP {signed.status}')
        page=context.new_page()
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        for route in pages:
            errors.clear()
            page.goto(args.base+'/operations'+('/'+route if route else ''),wait_until='domcontentloaded')
            page.locator('.ops-topbar').wait_for(timeout=30000)
            page.wait_for_timeout(1200)
            title=page.locator('.ops-topbar > h1').inner_text()
            metrics=page.evaluate('''() => ({overflow:document.documentElement.scrollWidth>innerWidth,
              headings:[...document.querySelectorAll('h1')].filter(e=>e.getBoundingClientRect().height>0).map(e=>e.textContent),
              alerts:[...document.querySelectorAll('[role=alert]')].map(e=>e.textContent),
              nativeSelects:document.querySelectorAll('main select').length,
              font:getComputedStyle(document.querySelector('.ops-ui')).fontFamily})''')
            filename=f'{role}-{route or "overview"}-desktop.png'
            page.screenshot(path=str(output/filename),full_page=True)
            results.append({'role':role,'page':route or 'overview','viewport':'desktop','title':title,**metrics,'errors':errors[:],'screenshot':filename})
            if role=='management' and route=='team' and page.locator('.ops-request-row').count():
                page.locator('.ops-request-row').first.click()
                page.wait_for_timeout(1000)
                capture(page, errors, role, 'request-detail', 'desktop')
                page.set_viewport_size({'width':390,'height':844})
                capture(page, errors, role, 'request-detail', 'mobile')
                page.get_by_role('button',name='Chi tiết',exact=True).click()
                page.wait_for_timeout(300)
                capture(page, errors, role, 'request-detail-rail', 'mobile')
                page.set_viewport_size({'width':1440,'height':900})
            page.set_viewport_size({'width':390,'height':844})
            errors.clear()
            page.goto(args.base+'/operations'+('/'+route if route else ''),wait_until='domcontentloaded')
            page.wait_for_timeout(1200)
            filename=f'{role}-{route or "overview"}-mobile.png'
            page.screenshot(path=str(output/filename),full_page=True)
            results.append({'role':role,'page':route or 'overview','viewport':'mobile',
                'overflow':page.evaluate('document.documentElement.scrollWidth>innerWidth'),'errors':errors[:],'screenshot':filename})
            page.set_viewport_size({'width':1440,'height':900})
        # Inspect nested screens and drawers without deciding real user accounts or publishing agents.
        if role=='management':
            room=context.request.get(args.base+'/api/business/rooms').json()['items'][0]['id']
            agents=context.request.get(args.base+f'/api/business/rooms/{room}/agents').json()['items']
            draft=next((a for a in agents if not a.get('published') and a['status']=='draft'),agents[0])
            factory=output/'factory-acceptance.json'
            if factory.exists():
                accepted_agent=json.loads(factory.read_text(encoding='utf-8')).get('agent_id')
                draft=next((a for a in agents if a['id']==accepted_agent),draft)
            cases=[('agent-list',f'agents?view=list&room={room}'),('agent-library',f'agents?view=library&room={room}'),
                   ('agent-builder',f"agents?room={room}&builder={draft['id']}")]
            accepted=output/'runtime-acceptance.json'
            if accepted.exists():
                chat=next(answer['chat_id'] for answer in json.loads(accepted.read_text(encoding='utf-8'))['answers'] if answer['mode']=='automatic')
                cases.append(('ask-answer',f'ask?room={room}&chat={chat}'))
            for label,route in cases:
                for viewport,width,height in [('desktop',1440,900),('mobile',390,844)]:
                    errors.clear();page.set_viewport_size({'width':width,'height':height})
                    page.goto(args.base+'/operations/'+route,wait_until='domcontentloaded')
                    page.wait_for_timeout(1400)
                    capture(page,errors,role,label,viewport)
            for viewport,width,height in [('desktop',1440,900),('mobile',390,844)]:
                errors.clear();page.set_viewport_size({'width':width,'height':height})
                page.goto(args.base+'/operations/team',wait_until='domcontentloaded');page.wait_for_timeout(1000)
                page.get_by_role('button',name='Bảng',exact=True).click();page.wait_for_timeout(300)
                capture(page,errors,role,'request-board',viewport)
            session_evidence=output/'session-runtime-acceptance.json'
            if session_evidence.exists():
                accepted_session=json.loads(session_evidence.read_text(encoding='utf-8'))['session_id']
                for viewport,width,height in [('laptop',1366,768),('compact-mobile',390,800)]:
                    errors.clear();page.set_viewport_size({'width':width,'height':height})
                    page.goto(args.base+f'/operations/team?session={accepted_session}',wait_until='domcontentloaded')
                    page.wait_for_timeout(1400)
                    capture(page,errors,role,'session-answer',viewport)
                    primary=page.get_by_role('button',name='Gửi tin nhắn',exact=True)
                    bounds=primary.bounding_box()
                    results[-1]['primary_visible']=bool(bounds and bounds['y']>=0 and bounds['y']+bounds['height']<=height)
                    if width<768:
                        results[-1]['session_header_height']=round(page.locator('.ops-session-heading').bounding_box()['height'])
                    page.locator('.ops-session-source-picker').click();page.wait_for_timeout(300)
                    capture(page,errors,role,'session-sources',viewport)
        else:
            for route,label,selector in [
                ('accounts','account-detail','.ops-admin-row-title button'),
                ('units','unit-detail','.ops-admin-row-title button'),
                ('audit','audit-detail','tbody button'),
                ('models','model-add',None),('connections','connection-add',None)]:
                errors.clear();page.set_viewport_size({'width':1440,'height':900})
                page.goto(args.base+'/operations/'+route,wait_until='domcontentloaded');page.wait_for_timeout(1200)
                if selector:page.locator(selector).first.click()
                else:page.get_by_role('button',name='Thêm model' if route=='models' else 'Thêm kết nối',exact=True).click()
                page.wait_for_timeout(500)
                capture(page,errors,role,label,'desktop')
                page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(300)
                capture(page,errors,role,label,'mobile')
        context.close()
    browser.close()
(output/'verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'pages':len(results),'overflow':sum(r['overflow'] for r in results),'javascript_errors':sum(len(r['errors']) for r in results),'output':str(output)},ensure_ascii=False))
if any(row['overflow'] or row['errors'] or row.get('primary_visible') is False or row.get('session_header_height',0)>96 for row in results):
    raise SystemExit(1)
