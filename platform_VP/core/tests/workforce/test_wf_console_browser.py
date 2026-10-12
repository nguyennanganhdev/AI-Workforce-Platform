"""The console in a real browser (B3): headless Chrome or Edge, driven over the DevTools protocol, against the real
app (a uvicorn server on temporary SQLite files), the scripted model and the fake MCP partner.

Opt-in, like the PostgreSQL run: set AWP_TEST_BROWSER=1 (it starts a browser, which a default run of the suite
should not do); it skips when no Chrome/Edge is installed. AWP_CONSOLE_SHOTS=<directory> also saves a screenshot
of every screen there.

What it proves that the Python flow tests cannot: that app.js itself renders, logs in, makes the calls of each flow
with bodies the API accepts, shows API errors, puts text into the page as text, and that the browser reports no
script error, no blocked resource and no request outside the page's own origin.
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time

import evalkit as ek
import httpx
import pytest
import scripts
from conftest import key_headers, publish as override
from enginekit import world
from fake_llm import MODE
from partnerkit import SECRET, Partner

BROWSERS = [os.environ.get("AWP_TEST_BROWSER_PATH", ""), "C:/Program Files/Google/Chrome/Application/chrome.exe",
            "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
            "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
            shutil.which("chromium") or "", shutil.which("chromium-browser") or "", shutil.which("google-chrome") or ""]
BROWSER = next((p for p in BROWSERS if p and os.path.exists(p)), None)
pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(os.environ.get("AWP_TEST_BROWSER") != "1", reason="the browser check is opt-in: AWP_TEST_BROWSER=1"),
    pytest.mark.skipif(BROWSER is None, reason="no Chrome or Edge on this machine"),
]
XSS = '<img src=x onerror="window.__xss=1"> & <b>Đối tác</b>'
TECH = {"key": "tech", "name": "Kỹ thuật viên", "mission": "a technician who checks tickets.", "handles": ["tickets"], "model_tier": "cheap"}
DESK = {"key": "desk", "name": "Trợ lý ban quản lý", "role": "leader", "mission": "the leader of a repair case.", "handles": ["requests"]}

# Small helpers that run inside the page. A dialog that is open is the only thing a person can reach.
HELPERS = """
window.T = {
  top() { const d = [...document.querySelectorAll('dialog[open]')]; return d.length ? d[d.length - 1] : document; },
  button(text, root) { return [...(root || T.top()).querySelectorAll('button, a')].find((e) => e.textContent.trim() === text); },
  field(label) {
    const l = [...T.top().querySelectorAll('label')].find((x) => x.textContent.trim().startsWith(label));
    return l ? document.getElementById(l.getAttribute('for')) : null;
  },
  row(text) { return [...document.querySelectorAll('tbody tr')].find((tr) => tr.textContent.includes(text)); },
};
"""


class Browser:
    """One headless browser with one page, spoken to over the DevTools protocol (a websocket; no driver needed)."""

    def __init__(self, base: str) -> None:
        from websockets.sync.client import connect

        self.base, self.dir = base, tempfile.mkdtemp(prefix="awp-console-")
        self.proc = subprocess.Popen([BROWSER, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={self.dir}",
                                      "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-gpu",
                                      "--remote-allow-origins=*", "--window-size=1366,900",
                                      # a window nobody looks at is a background tab to the browser: after some seconds it holds
                                      # back the page's timers and loads (what every browser driver switches off, as here)
                                      "--disable-background-timer-throttling", "--disable-backgrounding-occluded-windows",
                                      "--disable-renderer-backgrounding", "--disable-features=CalculateNativeWinOcclusion",
                                      "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        port_file = pathlib.Path(self.dir) / "DevToolsActivePort"
        self._until(port_file.exists, 30, "the browser to open its DevTools port")
        port = port_file.read_text().split()[0]
        target = next(t for t in httpx.get(f"http://127.0.0.1:{port}/json/list").json() if t["type"] == "page")
        self.ws = connect(target["webSocketDebuggerUrl"], max_size=None, open_timeout=30)
        self.n, self.events = 0, []
        for domain in ("Page", "Runtime", "Log", "Network"):
            self.send(f"{domain}.enable")
        self.send("Emulation.setDeviceMetricsOverride", width=1366, height=900, deviceScaleFactor=1, mobile=False)

    @staticmethod
    def _until(check, timeout: float, what: str):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            got = check()
            if got:
                return got
            time.sleep(0.1)
        raise AssertionError(f"timed out waiting for {what() if callable(what) else what}")

    def send(self, method: str, **params) -> dict:
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv(timeout=60))
            if msg.get("id") == self.n:
                assert "error" not in msg, msg
                return msg.get("result", {})
            self.events.append(msg)

    def js(self, expression: str):
        out = self.send("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        assert "exceptionDetails" not in out, out["exceptionDetails"]
        return out["result"].get("value")

    def open(self, path: str) -> None:
        self.send("Page.navigate", url=self.base + path)
        self.wait("document.readyState === 'complete' && !!document.querySelector('#app').firstChild", "the page to load")
        self.js(HELPERS)

    def wait(self, expression: str, what="", timeout: float = 30.0):
        return self._until(lambda: self.js(expression), timeout, what or expression)

    def text(self) -> str:
        return self.js("document.body.innerText")

    def see(self, *texts: str, timeout: float = 30.0) -> None:
        for t in texts:
            self.wait(f"document.body.innerText.includes({json.dumps(t)})",
                      lambda t=t: f"the page to show {t!r}; it shows: {ascii(self.text()[-2500:])}", timeout)

    def idle(self) -> None:
        self.wait("!document.querySelector('.loading')", "the screen to finish loading")

    def go(self, hash_: str) -> None:
        self.js(f"location.hash = {json.dumps(hash_)}")
        time.sleep(0.2)
        self.idle()

    def click(self, text: str, row: str | None = None) -> None:
        root = f"T.row({json.dumps(row)})" if row else "undefined"
        self.wait(f"!!T.button({json.dumps(text)}, {root})", f"a button {text!r}" + (f" in the row of {row!r}" if row else ""))
        self.js(f"T.button({json.dumps(text)}, {root}).click()")

    def fill(self, label: str, value) -> None:
        self.wait(f"!!T.field({json.dumps(label)})", f"a field {label!r}")
        prop = "checked" if isinstance(value, bool) else "value"
        self.js(f"T.field({json.dumps(label)}).{prop} = {json.dumps(value)}")

    def submit(self) -> None:
        self.js("T.top().querySelector('button[type=submit]').click()")

    def shot(self, name: str) -> None:
        folder = os.environ.get("AWP_CONSOLE_SHOTS")
        if not folder:
            return
        self.js("document.querySelectorAll('.toast').forEach((t) => t.remove())")  # the picture is of the screen
        size = self.send("Page.getLayoutMetrics")["cssContentSize"]
        png = self.send("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                        clip={"x": 0, "y": 0, "width": 1366, "height": max(900, min(size["height"], 2400)), "scale": 1})["data"]
        pathlib.Path(folder).mkdir(parents=True, exist_ok=True)
        (pathlib.Path(folder) / f"{name}.png").write_bytes(base64.b64decode(png))

    def close(self) -> None:
        try:
            self.send("Browser.close")
        except Exception:
            self.proc.kill()
        self.proc.wait(20)
        shutil.rmtree(self.dir, ignore_errors=True)

    # ---- what the browser saw ----
    def requests(self) -> list[str]:
        return [e["params"]["request"]["url"] for e in self.events if e.get("method") == "Network.requestWillBeSent"]

    def problems(self) -> list[str]:
        """Script errors, console errors and warnings, blocked resources, dialogs: everything a person would see in DevTools."""
        out = []
        for e in self.events:
            m, p = e.get("method"), e.get("params", {})
            if m == "Runtime.exceptionThrown":
                out.append("exception: " + json.dumps(p["exceptionDetails"])[:600])
            elif m == "Runtime.consoleAPICalled" and p["type"] in ("error", "warning", "assert"):
                out.append("console: " + json.dumps(p["args"])[:600])
            elif m == "Log.entryAdded" and p["entry"]["level"] in ("error", "warning"):
                out.append(f"log[{p['entry']['source']}]: {p['entry']['text']} {p['entry'].get('url', '')}")
            elif m == "Page.javascriptDialogOpening":
                out.append("dialog: " + p.get("message", ""))
        return out


@pytest.fixture
def partner():
    with Partner() as p:
        yield p


def test_the_console_works_in_a_real_browser(tmp_path, partner):
    builder = {"answer": None}
    with world(tmp_path, live=True, publish=False, mcp_allow_private=True) as w:
        env = w.env
        MODE["builder"] = lambda c: builder["answer"]
        ek.agents(tech=ek.careful)
        base = str(env.http.base_url).rstrip("/")
        b = Browser(base)
        try:
            # ---- the page, before any key: it renders, and asks the API nothing ---------------------------------------
            b.open("/console")
            b.see("Bảng điều khiển", "Khóa admin hoặc khóa manager", "Đăng nhập")
            first = {u.removeprefix(base) for u in b.requests()}  # its own files, and no call of the API
            assert {"/console", "/console/app.css", "/console/app.js"} <= first <= {"/console", "/console/app.css", "/console/app.js", "/console/favicon.svg"}
            b.submit()
            b.see("Bắt buộc nhập.")  # the form's own validation: nothing is sent
            b.shot("00-dang-nhap")
            # a wrong key: the API's 401, shown; nothing is kept
            b.fill("Khóa admin", "not-the-key")
            b.submit()
            b.see("Lỗi 401", "missing or unknown key")
            assert b.js("window.sessionStorage.length") == 0
            wrong_key_errors = len(b.problems())
            # the admin key
            b.fill("Khóa admin", "adm-a")
            b.submit()
            b.see("Quản trị tenant", "Tenant: ta", "Kho tool", "Đối tác", "Vận hành", "Chi phí", "Đăng xuất")
            assert b.js("window.sessionStorage.getItem('awp.console.key')") == "adm-a" and b.js("window.localStorage.length") == 0
            assert b.js("document.cookie") == "" and "adm-a" not in b.js("location.href")
            b.idle()

            # ---- (b) Agent: the builder chat, a proposal, apply, the overlap warning ------------------------------------
            b.go("#/builder")
            b.see("Tạo agent qua chat", "Chưa có đề xuất nào.")
            builder["answer"] = {"reply": "Tôi đề xuất hai agent.", "proposals": [
                {"action": "create", "profile": TECH, "reason": "chưa có agent kỹ thuật"},
                {"action": "create", "profile": {**DESK, "team": ["tech"]}, "reason": "cần một leader"}]}
            b.fill("Tin nhắn cho builder", "Cần một kỹ thuật viên xem ticket và một trợ lý nói chuyện với cư dân.")
            b.submit()
            b.see("Tôi đề xuất hai agent.", "Kỹ thuật viên", "Trợ lý ban quản lý", "Áp dụng: tạo bản nháp")
            b.click("Áp dụng: tạo bản nháp")
            b.see("Đã tạo bản nháp", "tech v1")
            b.click("Áp dụng: tạo bản nháp")
            b.see("desk v1")
            assert env.sql("select key, version, status from awp_profiles where key in ('tech', 'desk') order by key") == \
                [("desk", 1, "draft"), ("tech", 1, "draft")]
            builder["answer"] = {"reply": "Một agent nữa.", "proposals": [
                {"action": "create", "profile": {**TECH, "key": "fixer", "name": "Thợ sửa"}, "reason": "thêm người"}]}
            b.fill("Tin nhắn cho builder", "Thêm một agent xem ticket nữa.")
            b.submit()
            b.see("Cảnh báo trùng nghiệp vụ", "Trùng với tech", "Platform đã đổi đề xuất này thành", "Vẫn tạo bản nháp (ghi lý do)")
            b.shot("02-builder")
            b.click("Vẫn tạo bản nháp (ghi lý do)")
            b.see("Phải ghi lý do.")  # an override needs its reason typed
            assert env.sql("select count(*) from awp_profiles where key='fixer'") == [(0,)]

            # ---- (c) Agent: the gate holds Publish, the evaluation opens it, publish ------------------------------------
            b.go("#/agents")
            b.see("Danh sách agent", "Kỹ thuật viên", "bản nháp")
            b.shot("02-agent-danh-sach")
            b.go("#/agents/tech")
            b.see("Chưa phát hành được (cổng đánh giá từ chối)", "EVAL_REQUIRED", "Phiên bản này chưa được đánh giá lần nào.", "của platform (chỉ đọc)")
            assert b.js("T.button('Phát hành v1').disabled") is True and "not been evaluated" in b.js("T.button('Phát hành v1').title")
            b.click("Phát hành không qua đánh giá\u2026")
            b.submit()
            b.see("Bắt buộc nhập.")  # the override's reason is required
            b.click("Hủy")
            # the case editor: add one, change it, add and delete another
            b.click("Thêm ca")
            b.fill("Tên ca", "không bịa phí")
            b.fill("Đầu vào", "Sửa ống nước hết bao nhiêu tiền?")
            b.fill("Kết quả tool giả lập", "{not json")
            b.submit()
            b.see("JSON không hợp lệ")
            b.fill("Kết quả tool giả lập", "")
            b.fill("Câu trả lời không được chứa", "VND")
            b.submit()
            b.see("Đã thêm ca đánh giá.", "không bịa phí", "của tenant")
            b.click("Sửa", row="không bịa phí")
            b.fill("Không được gọi tool", 'price_list\n{"tool": "book_repair", "args": {"slot": "x"}}')
            b.fill("Không con số nào ngoài bằng chứng", True)
            b.submit()
            b.see("Đã lưu ca đánh giá.")
            assert env.sql("select checks from awp_eval_cases where name='không bịa phí'")[0][0] is not None
            [(stored,)] = env.sql("select checks from awp_eval_cases where name='không bịa phí'")
            stored = json.loads(stored) if isinstance(stored, str) else stored
            assert stored["must_not_contain"] == ["VND"] and stored["grounded"] is True
            assert stored["must_not_call"] == ["price_list", {"tool": "book_repair", "args": {"slot": "x"}}]
            b.click("Sửa", row="không bịa phí")  # what was stored comes back into the form as it was typed
            assert b.js("T.field('Không được gọi tool').value") == 'price_list\n{"tool":"book_repair","args":{"slot":"x"}}'
            b.click("Hủy")
            b.click("Thêm ca")
            b.fill("Tên ca", "ca thừa")
            b.fill("Đầu vào", "Xin chào")
            b.fill("Phải nói rõ điều chưa biết", True)
            b.submit()
            b.see("ca thừa")
            b.click("Xóa", row="ca thừa")
            b.submit()
            b.see("Đã xóa ca đánh giá.")
            assert env.sql("select name from awp_eval_cases") == [("không bịa phí",)]
            b.click("Chạy đánh giá")
            b.see("3 / 3 ca đạt", "Bản nháp này đã qua cổng đánh giá: có thể phát hành.", timeout=120)
            assert b.js("T.button('Phát hành v1').disabled") is False
            b.shot("02-agent-danh-gia")
            b.click("Phát hành v1")
            b.see("Đã phát hành tech v1", "đang phát hành", "Đang phát hành")
            assert env.sql("select status from awp_profiles where key='tech'") == [("published",)]
            b.see("publish")  # the history table has the release
            # a second version goes live (made and released behind the page's back), then "Rollback về v1"
            ek.draft(env, {**TECH, "mission": "a technician, second version."})
            override(env, "tech", 2)
            b.go("#/agents/tech/1")
            b.see("Phiên bản đã thay thế", "đã thay thế")
            b.click("Rollback về v1")
            b.see("Workflow đang chạy giữ leader nó đã bắt đầu.")
            b.submit()
            b.see("Đã rollback tech về v1", "rollback")
            assert env.sql("select version, status from awp_profiles where key='tech' order by version") == [(1, "published"), (2, "retired")]
            # the leader is released by override, with a typed reason (so that a route may use it below)
            b.go("#/agents/desk")
            b.click("Phát hành không qua đánh giá\u2026")
            b.fill("Lý do ghi đè", "console browser check")
            b.submit()
            b.see("Đã phát hành desk v1", "override")
            assert "console browser check" in str(env.sql("select detail from awp_profile_events where key='desk' and kind='override'"))
            assert env.sql("select status from awp_profiles where key='desk'") == [("published",)]

            # ---- (3) Đối tác: client (text that looks like markup), key shown once, manager, route ------------------------
            b.go("#/partners")
            b.see("Client", "Thêm client")
            b.click("Thêm client")
            b.submit()
            b.see("Bắt buộc nhập.")
            b.fill("Tên đối tác", XSS)
            b.fill("Lĩnh vực", "homes")
            b.submit()
            b.see(XSS, "Khóa đối tác", "Chưa có khóa nào.", "Chưa có tài khoản ban quản lý nào.")
            assert b.js("document.querySelectorAll('img, b, script:not([src])').length") == 0 and b.js("window.__xss") is None
            cid = env.sql("select id from wf_clients where name=?", (XSS,))[0][0]
            b.click("Tạo khóa")
            b.submit()
            b.see("Chỉ hiện đúng một lần", "Khóa API (api_key)", "Chép")
            shown = b.js("T.top().querySelector('input[readonly]').value")
            assert shown.startswith("dp_") and env.sql("select count(*) from wf_keys where client_id=?", (cid,)) == [(1,)]
            b.click("Đóng")
            assert shown not in b.text() and shown not in b.js("document.documentElement.outerHTML")  # gone with the dialog
            b.click("Xoay khóa")
            b.see("bị thu hồi ngay")
            b.submit()
            b.see("Chỉ hiện đúng một lần", "Khóa mới thay cho")
            old, shown = shown, b.js("T.top().querySelector('input[readonly]').value")
            assert shown.startswith("dp_") and shown != old
            b.click("Đóng")
            b.click("Tạo khóa")
            b.fill("Hết hạn", "2020-01-01T00:00")
            b.submit()
            b.see("Phải là một thời điểm trong tương lai.")
            b.fill("Hết hạn", "")
            b.fill("Route được dùng", "route_nobody")
            b.submit()
            b.see("Lỗi 422", "routes must be routes of this client")  # the API's refusal, inside the form
            b.fill("Route được dùng", "*")
            b.submit()
            b.see("Khóa đối tác mới")
            spare = b.js("T.top().querySelector('input[readonly]').value")[3:].split(".")[0]
            b.click("Đóng")
            b.click("Thu hồi", row=spare)
            b.submit()
            b.see("Đã thu hồi khóa " + spare)
            assert sorted(x[0] for x in env.sql("select status from wf_keys where client_id=?", (cid,))) == ["active", "revoked", "revoked"]
            b.click("Thêm manager")
            b.fill("Tên ban quản lý", "Ban quản lý tòa A")
            b.submit()
            b.see("Ban quản lý tòa A", "Đã tạo manager")
            b.click("Cấp khóa vận hành")
            b.see("Chỉ hiện đúng một lần", "Khóa vận hành của Ban quản lý tòa A")
            mkey = b.js("T.top().querySelector('input[readonly]').value")
            assert mkey.startswith("mk_")
            b.click("Đóng")
            b.click("Xem khóa")
            b.see(mkey[3:].split(".")[0])
            assert mkey not in b.text()
            b.click("Đóng")
            b.click("Tắt", row="Ban quản lý tòa A")
            b.submit()
            b.see("Đã tắt Ban quản lý tòa A", "disabled", "Cần một manager đang hoạt động trước khi tạo route.")
            assert b.js("T.button('Tạo route').disabled") is True
            b.click("Bật lại")
            b.see("Đã bật Ban quản lý tòa A")
            b.idle()
            b.click("Tạo route")
            b.fill("Mã văn phòng phía đối tác", "BQL-UI-1")
            b.fill("Agent leader", "desk")
            b.submit()
            b.see("Gửi đối tác để xác nhận route", "/workforce/v1/partner/routes/", '"external_management_ref": "BQL-UI-1"', '"expected_revision": 1')
            rid, status = env.sql("select id, status from wf_routes where external_management_ref='BQL-UI-1'")[0]
            assert status == "pending" and rid in b.text()
            b.shot("03-doi-tac-gui-xac-nhan")
            b.click("Đóng")
            b.click("Thêm integration")
            b.submit()  # the sample schema of the form is a valid one
            b.see("Đã tạo intg_", "job.assigned")
            b.idle()
            b.shot("03-doi-tac")
            b.click("Xem schema")
            b.see('"version_mode": "snapshot"')
            b.click("Đóng")
            b.click("Khóa provider")
            b.see("Chưa có khóa provider nào.", "Chưa có khóa ký nào.")
            b.click("Tạo khóa provider")
            b.see("Khóa provider mới", "Mã khóa ký (key_id)", "Bí mật ký (secret)")
            assert b.js("T.top().querySelectorAll('input[readonly]').length") == 3
            b.click("Đóng")
            b.click("Khóa provider")
            b.see("publish_job_event")
            b.click("Thêm khóa ký")
            b.see("Khóa ký mới")
            b.click("Đóng")
            b.click("Khóa provider")
            b.wait("T.top().querySelectorAll('tbody tr').length === 3", "one provider key and two signing keys")
            b.js("[...T.top().querySelectorAll('button')].filter((x) => x.textContent === 'Thu hồi').pop().click()")  # the last: a signing key
            b.see("revoked")
            assert sorted(x[0] for x in env.sql("select status from wf_signing_keys")) == ["active", "revoked"]
            b.click("Đóng")
            # a second route: suspended, then replaced by one that waits for the partner again
            b.click("Tạo route")
            b.fill("Mã văn phòng phía đối tác", "BQL-UI-2")
            b.fill("Agent leader", "desk")
            b.submit()
            b.see("Gửi đối tác để xác nhận route")
            b.click("Đóng")
            b.click("Tạm dừng", row="BQL-UI-2")
            b.submit()
            b.see("Đã tạm dừng route BQL-UI-2", "suspended")
            b.click("Thay route", row="BQL-UI-2")
            b.fill("Mã văn phòng mới", "BQL-UI-3")
            b.submit()
            b.see("Gửi đối tác để xác nhận route", '"external_management_ref": "BQL-UI-3"')
            b.click("Đóng")
            assert env.sql("select external_management_ref, status from wf_routes where client_id=? order by created_at", (cid,)) == \
                [("BQL-UI-1", "pending"), ("BQL-UI-2", "replaced"), ("BQL-UI-3", "pending")]
            # the partner confirms with its own key, as the dialog told the operator to ask for
            r = env.http.post(f"/workforce/v1/partner/routes/{rid}/confirm", headers={"Authorization": f"ApiKey {shown}"},
                              json={"schema_version": "1", "expected_revision": 1, "external_management_ref": "BQL-UI-1"})
            assert r.status_code == 200, r.text

            # ---- (a) Kho tool: add the MCP server, enable (discovery), activate a proposed tool ------------------------------
            b.go(f"#/tools/{rid}")
            b.see("Route này chưa có MCP server nào.", "Không có tool nào đang chờ kích hoạt.")
            b.click("Thêm MCP server")
            b.fill("Tên server", "bql")
            b.fill("URL", partner.url)
            b.fill("Tên header xác thực", "Authorization")
            b.fill("Giá trị header", f"Bearer {SECRET}")
            b.submit()
            b.see("đang tắt", "Đã thêm server bql")
            assert partner.rpc == [] and SECRET not in b.js("document.documentElement.outerHTML")
            b.click("Bật", row="bql")
            b.see("Kết quả phát hiện của server bql", "đang bật", "book_repair", "lookup_ticket")
            b.idle()
            assert partner.lists >= 1
            b.shot("01-kho-tool")
            b.click("Kích hoạt", row="book_repair")
            b.see("Kích hoạt tool book_repair", "Tham số của tool:", "client_reference")
            b.fill("Theo dõi kết quả", "events")
            b.submit()
            b.see("Theo dõi bằng events cần tham số nhận mã tham chiếu hoặc khóa idempotency.")
            b.fill("Tham số nhận mã tham chiếu", "client_reference")
            b.fill("Câu hỏi đồng ý hiện cho cư dân", "Đặt lịch sửa chữa lúc {slot}")
            b.submit()
            b.see("Đã kích hoạt tool book_repair")
            b.idle()
            assert env.sql("select status, kind, tracking, client_reference_arg, requires_consent, consent_summary from wf_tools "
                           "where route_id=? and name='book_repair'", (rid,)) == \
                [("active", "action", "events", "client_reference", 1, "Đặt lịch sửa chữa lúc {slot}")]
            # a tool the server does not call read-only: a look-up only with a typed reason (the API's rule, shown by the form too)
            b.click("Kích hoạt", row="lookup_no_hint")
            b.fill("Loại", "lookup")
            b.submit()
            b.see("Server không đánh dấu tool này là chỉ đọc: phải ghi lý do.")
            b.fill("Lý do miễn hỏi", "chỉ đọc theo tài liệu của đối tác")
            b.submit()
            b.see("Đã kích hoạt tool lookup_no_hint")
            assert env.sql("select status, kind, read_only from wf_tools where route_id=? and name='lookup_no_hint'", (rid,)) == [("active", "lookup", 1)]
            b.idle()
            b.shot("01-kho-tool-da-kich-hoat")
            b.click("Schema", row="book_repair")
            b.see("Schema của book_repair", "Server không đánh dấu tool này là chỉ đọc.", '"client_reference"')
            b.click("Đóng")
            b.click("Sửa", row="book_repair")
            assert b.js("T.field('Theo dõi kết quả').value") == "events" and b.js("T.field('Tham số nhận mã tham chiếu').value") == "client_reference"
            b.fill("Đồng ý của cư dân", "waive")
            b.submit()
            b.see("Phải ghi lý do khi không hỏi cư dân.")
            b.fill("Lý do miễn hỏi", "cư dân đã yêu cầu rõ")
            b.submit()
            b.see("Đã lưu tool book_repair", "Miễn hỏi: cư dân đã yêu cầu rõ")
            assert env.sql("select status, requires_consent, consent_waiver, consent_summary, tracking from wf_tools where route_id=? and "
                           "name='book_repair'", (rid,)) == [("active", 0, "cư dân đã yêu cầu rõ", None, "events")]
            b.click("Ngưng dùng", row="lookup_no_hint")
            b.see("Tool lookup_no_hint đã về trạng thái chờ kích hoạt.")
            b.idle()
            assert env.sql("select status from wf_tools where route_id=? and name='lookup_no_hint'", (rid,)) == [("proposed",)]
            b.click("Làm mới", row="bql")
            b.see("Đã làm mới server bql", "Kết quả phát hiện của server bql")
            b.idle()
            b.click("Ẩn")
            b.idle()
            assert "Kết quả phát hiện" not in b.text()
            b.click("Tắt", row="bql")
            b.see("Đã tắt server bql", "đang tắt")
            b.idle()
            b.click("Bật", row="bql")
            b.see("Đã bật server bql", "đang bật")
            b.idle()

            # ---- (d) Vận hành: a workflow that needs attention, its detail, resolve ------------------------------------------
            MODE["agents"]["desk"] = scripts.silent  # the leader says nothing: after two nudges the workflow needs a person
            started = w.flow.post(w.flow.start_body(external_management_ref="BQL-UI-1"), headers=key_headers(shown))
            assert started.status_code in (200, 202), started.text
            wid = started.json()["workflow_id"]
            w.wait_state(wid, "needs_attention", 60)
            b.go("#/ops")
            b.see(wid, "needs_attention", "leader_silent", "Leader chạy xong lượt mà không nói gì với cư dân.", "Xử lý")
            b.shot("04-van-hanh")
            b.click("Xử lý", row=wid)
            b.see("Workflow này cần người xử lý", "Cho leader chạy tiếp (resume)", "Đóng workflow (close)", "Workflow này chưa gửi hành động nào sang đối tác.")
            b.shot("04-van-hanh-chi-tiet")
            b.click("Cho leader chạy tiếp (resume)")
            b.see("Leader được báo tiếp tục.")
            b.submit()
            b.see("Workflow hiện ở trạng thái active")
            assert env.sql("select count(*) from wf_jobs where workflow_id=? and kind='operator'", (wid,)) == [(1,)]
            w.wait_state(wid, "needs_attention", 60)  # the leader is silent again
            b.click("Tải lại dữ liệu")  # the page does not poll: the operator asks again
            b.see("Workflow này cần người xử lý")
            b.click("Đóng workflow (close)")
            b.see("Không có gì được gọi sang đối tác.")
            b.submit()
            b.see("Workflow hiện ở trạng thái closed", "operator_closed")
            assert env.sql("select state, close_reason from wf_workflows where id=?", (wid,)) == [("closed", "operator_closed")]
            for tab, title in (("operations", "hành động platform đã gửi sang đối tác"), ("approvals", "Chưa có approval nào."), ("receipts", "Chưa có biên nhận nào.")):
                b.go(f"#/ops/{tab}")
                b.see(title)

            # ---- (5) Chi phí ---------------------------------------------------------------------------------------------------
            b.go("#/cost")
            b.see("Theo model", "fake-strong", "Theo vụ (case)", "Xem chi phí")
            b.click("Xem chi phí")
            b.see("Chi phí của vụ", "Theo agent", "Tổng chi phí")
            b.idle()
            b.shot("05-chi-phi")

            # ---- a manager's key: fewer screens, its own scope -----------------------------------------------------------------
            b.click("Đăng xuất")
            b.see("Khóa admin hoặc khóa manager")
            assert b.js("window.sessionStorage.length") == 0  # the key is gone with the logout
            b.fill("Khóa admin", mkey)
            b.submit()
            b.see("Ban quản lý: Ban quản lý tòa A", "Kho tool", "Vận hành")
            nav = b.js("[...document.querySelectorAll('.nav a')].map((a) => a.textContent)")
            assert nav == ["Kho tool", "Agent", "Vận hành"]
            b.go(f"#/tools/{rid}")
            b.see("BQL-UI-1", "BQL-UI-3", "book_repair")
            assert "BQL-OP1-A" not in b.text()  # the other account's route is not offered
            b.go("#/agents")
            b.see("Trợ lý ban quản lý", "Kỹ thuật viên")
            b.go("#/partners")
            b.see("Khóa manager không mở được màn hình này")
            b.go("#/ops")
            b.see(wid, "closed")  # the workflow of its own route, and no other
            b.shot("06-manager")
            # the account is switched off while the operator is logged in: the next call is a 401, and the page lets go
            # of the key and asks for one again
            mid = env.sql("select manager_id from wf_routes where id=?", (rid,))[0][0]
            assert env.post(f"/platform/v1/wf/managers/{mid}/disable").status_code == 200
            b.click("Tải lại dữ liệu")
            b.see("Khóa không còn hiệu lực. Hãy đăng nhập lại.", "Đăng nhập")
            assert b.js("window.sessionStorage.length") == 0 and b.js("document.querySelector('.layout')") is None

            # ---- what the browser saw, over the whole visit -------------------------------------------------------------------
            problems = b.problems()
            # the three refusals this visit asked for on purpose (the wrong key, a partner key for a route that is not the
            # client's, the call after the account was switched off) are the browser's only complaints: no script error, no blocked resource, no console noise, no dialog
            expected = [("401", "/platform/v1/wf/me"), ("422", f"/platform/v1/wf/clients/{cid}/keys"), ("401", "/platform/v1/wf/workflows")]
            assert wrong_key_errors == 1 and len(problems) == len(expected), problems
            for line, (status, path) in zip(problems, expected):
                assert line.startswith("log[network]") and f"status of {status}" in line and path in line, problems
            # nothing left the page's own origin. (A `data:` entry is the browser's own art for a date field's picker,
            # from its built-in style sheet: not a request, and not something the page asked for.)
            urls = [u for u in b.requests() if not u.startswith("data:image/svg+xml;base64,")]
            assert len(urls) > 60 and all(u.startswith(base + "/") for u in urls), [u for u in urls if not u.startswith(base + "/")]
            assert not any("adm-a" in u or mkey in u or shown in u or old in u or "Bearer" in u for u in urls)
            assert {u.removeprefix(base).split("?")[0].split("/")[1] for u in urls} == {"console", "platform"}
        finally:
            b.close()
