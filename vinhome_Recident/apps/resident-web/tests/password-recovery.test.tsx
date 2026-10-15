import {afterAll,afterEach,beforeAll,expect,test} from "vitest";
import {GlobalRegistrator} from "@happy-dom/global-registrator";

let render: typeof import("@testing-library/react")["render"];
let cleanup: typeof import("@testing-library/react")["cleanup"];
let fireEvent: typeof import("@testing-library/react")["fireEvent"];
const originalFetch=globalThis.fetch;
beforeAll(async () => {
  GlobalRegistrator.register({url:"http://localhost:3011/login"});
  ({render,cleanup,fireEvent}=await import("@testing-library/react/pure"));
});
afterEach(() => {cleanup();globalThis.fetch=originalFetch;});
afterAll(async () => {await new Promise(resolve=>setTimeout(resolve,50));GlobalRegistrator.unregister();});

test("recovery link stays out of history and submits only after matching passwords",async () => {
  const token="test-token-for-recovery-not-a-production-secret";
  history.replaceState(null,"",`/login#reset-password?token=${token}`);
  const {ResetPasswordPage}=await import("../src/features/auth/ResetPasswordPage");
  const calls: {path:string; body: unknown}[]=[];
  globalThis.fetch=(async (path,init) => {calls.push({path:String(path),body:JSON.parse(String(init?.body))});return Response.json({ok:true});}) as typeof fetch;
  const view=render(<ResetPasswordPage />);
  expect(location.href).not.toContain(token);
  fireEvent.change(view.getByLabelText("Mật khẩu mới"),{target:{value:"new-password-for-test"}});
  fireEvent.change(view.getByLabelText("Nhập lại mật khẩu"),{target:{value:"does-not-match"}});
  fireEvent.submit(view.getByRole("button",{name:"Lưu mật khẩu mới"}).closest("form")!);
  expect(calls).toEqual([]);
  expect(view.getByRole("alert").textContent).toContain("phải khớp");
  fireEvent.change(view.getByLabelText("Nhập lại mật khẩu"),{target:{value:"new-password-for-test"}});
  fireEvent.submit(view.getByRole("button",{name:"Lưu mật khẩu mới"}).closest("form")!);
  expect(await view.findByRole("status")).toBeTruthy();
  expect(calls).toEqual([{path:"/api/business/auth/password-reset/confirm",body:{token,new_password:"new-password-for-test"}}]);
  expect(view.queryByLabelText("Mật khẩu mới")).toBeNull();
});

test("an incomplete recovery link cannot submit a password",async () => {
  history.replaceState(null,"","/login#reset-password");
  const {ResetPasswordPage}=await import("../src/features/auth/ResetPasswordPage");
  const view=render(<ResetPasswordPage />);
  expect(view.getByRole("alert").textContent).toContain("Link chưa đầy đủ");
  expect(view.queryByRole("button")).toBeNull();
});
