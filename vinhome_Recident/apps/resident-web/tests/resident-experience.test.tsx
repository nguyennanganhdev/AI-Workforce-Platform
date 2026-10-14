import {afterAll,afterEach,beforeAll,expect,test,vi} from "vitest";
import {GlobalRegistrator} from "@happy-dom/global-registrator";
let render: typeof import("@testing-library/react")["render"];
let cleanup: typeof import("@testing-library/react")["cleanup"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
beforeAll(async () => {
  GlobalRegistrator.register({url:"http://localhost:3011/resident"});
  ({render,cleanup,fireEvent}=await import("@testing-library/react/pure"));
  HTMLDialogElement.prototype.showModal=function(){this.setAttribute("open","");};
  HTMLDialogElement.prototype.close=function(){this.removeAttribute("open");};
});
afterEach(() => cleanup());
afterAll(async () => {await new Promise(r => setTimeout(r,50));GlobalRegistrator.unregister();});

test("citations disclose reference text and true latency without duplicating the legacy footer",async () => {
  const {MessageDetails,answerText}=await import("../src/features/assistant/ChatExperience");
  const message={id:"reply",role:"assistant" as const,text:"Có tiện ích.\n(Nguồn tham khảo: Hướng dẫn; cần xác nhận.)",reception:{latencyMs:1500,citations:[{title:"Hướng dẫn",excerpt:"Đoạn tài liệu.",status:"reference" as const}],steps:[{stage:"searching" as const,at:new Date().toISOString()}]}};
  expect(answerText(message)).toBe("Có tiện ích.");
  expect(answerText({...message,reception:undefined})).toBe(message.text);
  const view=render(<MessageDetails message={message} />);
  expect(view.getByText("Tham khảo")).toBeTruthy();
  expect(view.getByText("Đoạn tài liệu.")).toBeTruthy();
  expect(view.getByText("1,5 giây")).toBeTruthy();
  expect(view.queryByText("Đã xác nhận")).toBeNull();
});

test("notifications filter unread and mark only the displayed owned IDs",async () => {
  const {NotificationCenter}=await import("../src/features/utilities/NotificationCenter");
  const read=vi.fn(),open=vi.fn();
  const props={items:[{id:"unread",created_at:new Date().toISOString(),read_at:null,payload:{title:"Mới"}},{id:"read",created_at:new Date().toISOString(),read_at:new Date().toISOString(),payload:{title:"Cũ"}}],unread:1,busy:false,more:false,onMore:vi.fn(),onRead:read,onOpen:open};
  const view=render(<NotificationCenter {...props} />);
  fireEvent.click(view.getByRole("button",{name:"Chưa đọc 1"}));
  expect(view.queryByText("Cũ")).toBeNull();
  fireEvent.click(view.getByRole("button",{name:"Đọc các mục hiển thị"}));
  expect(read).toHaveBeenCalledWith(["unread"]);
  fireEvent.click(view.getByRole("button",{name:/Mới/}));
  expect(open).toHaveBeenCalledWith(props.items[0]);
});

test("chat removal requires confirmation and keeps a failed removal reviewable",async () => {
  const {ConversationList}=await import("../src/features/assistant/ConversationList");
  const remove=vi.fn(async () => false);
  const view=render(<ConversationList state={{version:1,messages:[],draft:null,requests:[],activeConversationId:"chat",conversations:[{id:"chat",title:"Hỏi tiện ích",messages:[],draft:null,unread:0,updatedAt:new Date().toISOString()}]}} onSelect={vi.fn()} onNew={vi.fn()} onDelete={remove} />);
  fireEvent.click(view.getByRole("button",{name:"Hội thoại"}));
  fireEvent.click(view.getByRole("button",{name:"Xóa Hỏi tiện ích"}));
  expect(remove).not.toHaveBeenCalled();
  expect(view.getByRole("dialog").textContent).toContain("có thể khôi phục");
  fireEvent.click(view.getByRole("button",{name:"Xóa hội thoại"}));
  await vi.waitFor(() => expect(remove).toHaveBeenCalledWith("chat"));
  expect(view.getByRole("dialog").hasAttribute("open")).toBe(true);
});
