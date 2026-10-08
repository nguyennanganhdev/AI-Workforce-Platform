import { afterAll, afterEach, beforeAll, expect, test } from "vitest";
import { GlobalRegistrator } from '@happy-dom/global-registrator';
import { typeInto } from './type-into';

let render: typeof import('@testing-library/react')['render'];
let cleanup: typeof import('@testing-library/react')['cleanup'];
let waitFor: typeof import('@testing-library/react')['waitFor'];
const originalFetch = globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({url:'http://localhost:3022/operations/ask?chat=personal-acceptance'});
  ({render,cleanup,waitFor} = await import('@testing-library/react/pure'));
});
afterEach(() => {cleanup();globalThis.fetch=originalFetch;history.replaceState(null,'','/operations/ask?chat=personal-acceptance');});
afterAll(async () => {await new Promise(resolve=>setTimeout(resolve,50));GlobalRegistrator.unregister();});

test('a private answer retains its author and source after revocation; each external write identifies its action', async () => {
  const {QueryClient,QueryClientProvider} = await import('@tanstack/react-query');
  const {createRootRoute,createRouter,createMemoryHistory,RouterProvider} = await import('@tanstack/react-router');
  const {AskAgent} = await import('../src/features/vinhomes-operations/connected/AskAgent');
  const {default:userEvent} = await import('@testing-library/user-event');
  const user=userEvent.setup({document});
  const writes:{path:string;body:unknown}[]=[];
  let decision='pending';
  globalThis.fetch=(async (input:RequestInfo|URL,init?:RequestInit) => {
    const path=new URL(String(input),'http://localhost').pathname;
    if (init?.method==='POST') {
      writes.push({path,body:JSON.parse(String(init.body))});
      if (path.endsWith('/decision')) decision='succeeded';
      return Response.json({id:'posted',status:decision});
    }
    if (path.endsWith('/external-calls')) return Response.json({items:[{id:'write-one',connection_title:'Lịch Google',tool_name:'calendar.create_event',description:'Tạo lịch họp cư dân',arguments:{title:'Họp cư dân',starts_at:'2026-10-08T18:00:00+07:00'},status:decision}]});
    const agents=[{id:'retired',name:'Agent Kỹ thuật',purpose:'specialist',published:false,status:'revoked'},{id:'knowledge',name:'Agent Tri thức',purpose:'specialist',published:true,status:'active'}];
    if (path==='/api/business/rooms') return Response.json({items:[{id:'management',name:'BQL Sapphire'}]});
    if (path.endsWith('/agents')) return Response.json({items:agents});
    if (path.endsWith('/connections')) return Response.json({items:[{id:'calendar',title:'Lịch Google',status:'pending',tools:[]}]});
    if (path==='/api/business/personal-chats') return Response.json({items:[]});
    return Response.json({id:'personal-acceptance',room_id:'management',name:'Câu hỏi riêng',agents,sources:[],messages:[{id:'answer',sender_agent_id:'retired',created_at:'2026-10-06T08:00:00Z',body:{text:'Thiết bị còn bảo hành.'},route:{automatic:false},used_sources:[{tool:'knowledge.search',name:'knowledge',external:false,effect:'read'}]}]});
  }) as typeof fetch;
  const cache=new QueryClient({defaultOptions:{queries:{retry:false}}});
  const rootRoute=createRootRoute({component:()=> <AskAgent userId="manager" />});
  const router=createRouter({routeTree:rootRoute,history:createMemoryHistory({initialEntries:['/']})});
  const view=render(<QueryClientProvider client={cache}><RouterProvider router={router} /></QueryClientProvider>);
  expect(await view.findByText('Tạo lịch họp cư dân')).toBeTruthy();
  expect(view.getByText('Tìm kiếm tri thức')).toBeTruthy();
  expect(view.getAllByText('Agent Kỹ thuật').length).toBeGreaterThan(0);
  expect(view.getByRole('switch',{name:'Dùng Lịch Google cho hội thoại này'}).getAttribute('aria-disabled')).toBe('true');
  await user.click(view.getByRole('button',{name:'Cho phép'}));
  await view.findByText('Đã thực hiện');
  expect(writes[0]).toEqual({path:'/api/business/rooms/personal-acceptance/external-calls/write-one/decision',body:{decision:'approve'}});
  const question=view.getByRole('textbox',{name:'Câu hỏi cho agent'}) as HTMLTextAreaElement;
  await typeInto(question,'Tra cứu phí gửi xe tại S1.01.');
  await user.click(view.getByRole('button',{name:'Gửi câu hỏi'}));
  await waitFor(()=>expect(question.value).toBe(''));
  expect(writes.at(-1)?.path).toBe('/api/business/personal-chats/personal-acceptance/messages');
  expect(writes.at(-1)?.body).toMatchObject({text:'Tra cứu phí gửi xe tại S1.01.',mention_agent_id:null});
});

test('switching units clears the old private chat and creates the next chat in the selected unit', async () => {
  const {QueryClient,QueryClientProvider} = await import('@tanstack/react-query');
  const {createRootRoute,createRouter,createMemoryHistory,RouterProvider} = await import('@tanstack/react-router');
  const {AskAgent} = await import('../src/features/vinhomes-operations/connected/AskAgent');
  const {default:userEvent} = await import('@testing-library/user-event');
  const user=userEvent.setup({document});
  history.replaceState(null,'','/operations/ask?room=management&chat=personal-acceptance');
  const posted:{path:string;body:unknown}[]=[];
  globalThis.fetch=(async (input:RequestInfo|URL,init?:RequestInit) => {
    const url=new URL(String(input),'http://localhost');
    const path=url.pathname;
    if (init?.method==='POST') {
      posted.push({path,body:JSON.parse(String(init.body))});
      return Response.json({id:'personal-ruby'});
    }
    if (path==='/api/business/rooms') return Response.json({items:[{id:'management',name:'BQL Sapphire'},{id:'ruby',name:'BQL Ruby'}]});
    if (path.endsWith('/agents') || path.endsWith('/connections') || path.endsWith('/external-calls') || path==='/api/business/personal-chats') return Response.json({items:[]});
    return Response.json({id:'personal-acceptance',room_id:'management',name:'Câu hỏi riêng',agents:[],sources:[],messages:[]});
  }) as typeof fetch;
  const cache=new QueryClient({defaultOptions:{queries:{retry:false}}});
  const rootRoute=createRootRoute({component:()=> <AskAgent userId="manager" />});
  const router=createRouter({routeTree:rootRoute,history:createMemoryHistory({initialEntries:['/']})});
  const view=render(<QueryClientProvider client={cache}><RouterProvider router={router} /></QueryClientProvider>);
  await user.click(await view.findByRole('combobox',{name:'Đơn vị'}));
  await user.click(await view.findByRole('option',{name:'BQL Ruby'}));
  expect(new URLSearchParams(location.search).get('room')).toBe('ruby');
  expect(new URLSearchParams(location.search).has('chat')).toBe(false);
  await typeInto(view.getByRole('textbox',{name:'Câu hỏi cho agent'}) as HTMLTextAreaElement,'Cho tôi biết các yêu cầu đang mở.');
  await user.click(view.getByRole('button',{name:'Gửi câu hỏi'}));
  await waitFor(()=>expect(posted.length).toBe(2));
  expect(posted[0]).toMatchObject({path:'/api/business/personal-chats',body:{room_id:'ruby'}});
  expect(posted[1]?.path).toBe('/api/business/personal-chats/personal-ruby/messages');
});
