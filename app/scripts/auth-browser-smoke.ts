// Requires Chrome in an isolated debugging profile on 9333 and both FE servers.
// bun app/scripts/auth-browser-smoke.ts
const target = await (
  await fetch(
    "http://127.0.0.1:9333/json/new?http://127.0.0.1:3020/operations/login",
    { method: "PUT" },
  )
).json();
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise<void>((resolve, reject) => {
  socket.onopen = () => resolve();
  socket.onerror = reject;
});
let id = 0;
const pending = new Map<
  number,
  { resolve: (value: any) => void; reject: (error: Error) => void }
>();
const exceptions: string[] = [];
socket.onmessage = (event) => {
  const message = JSON.parse(String(event.data));
  if (message.id) {
    const request = pending.get(message.id);
    pending.delete(message.id);
    if (message.error)
      request?.reject(new Error(JSON.stringify(message.error)));
    else request?.resolve(message.result);
  } else if (message.method === "Runtime.exceptionThrown")
    exceptions.push(JSON.stringify(message.params.exceptionDetails));
};
function command(
  method: string,
  params: Record<string, unknown> = {},
): Promise<any> {
  return new Promise((resolve, reject) => {
    const current = ++id;
    const timer = setTimeout(() => {
      pending.delete(current);
      reject(new Error(`Timeout ${method}`));
    }, 20_000);
    pending.set(current, {
      resolve: (result) => {
        clearTimeout(timer);
        resolve(result);
      },
      reject: (error) => {
        clearTimeout(timer);
        reject(error);
      },
    });
    socket.send(JSON.stringify({ id: current, method, params }));
  });
}
async function evaluate(expression: string) {
  const result = await command("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (result.exceptionDetails)
    throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function until(expression: string) {
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      if (await evaluate(expression)) return;
    } catch {
      /* navigation creates a new context */
    }
    await Bun.sleep(200);
  }
  throw new Error(`Not reached: ${expression}`);
}
async function go(url: string, selector: string) {
  await command("Page.navigate", { url });
  await until(
    `location.href.startsWith(${JSON.stringify(url)}) && !!document.querySelector(${JSON.stringify(selector)})`,
  );
}
async function assert(expression: string, message: string) {
  if (!(await evaluate(expression))) throw new Error(message);
}
async function click(text: string) {
  await evaluate(
    `(() => { const el = [...document.querySelectorAll('button,a')].find(el => el.textContent.trim() === ${JSON.stringify(text)}); if (!el) throw new Error('Missing control'); el.click(); })()`,
  );
  await Bun.sleep(250);
}
async function fill(name: string, value: string) {
  await evaluate(
    `(() => { const el = document.querySelector('[name="${name}"]'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, ${JSON.stringify(value)}); el.dispatchEvent(new Event('input', { bubbles: true })); })()`,
  );
  await Bun.sleep(100);
}
try {
  await command("Runtime.enable");
  await command("Page.enable");
  await until(`!!document.querySelector('.staff-auth')`);
  for (const width of [320, 390, 768, 1440]) {
    await command("Emulation.setDeviceMetricsOverride", {
      width,
      height: 900,
      deviceScaleFactor: 1,
      mobile: width < 761,
    });
    await Bun.sleep(200);
    await assert(
      "document.documentElement.scrollWidth <= innerWidth",
      `Staff login overflows ${width}`,
    );
    if (width === 390 || width === 1440) {
      const shot = await command("Page.captureScreenshot", { format: "png" });
      await Bun.write(
        `.codex-artifacts/staff-login-${width}.png`,
        Buffer.from(shot.data, "base64"),
      );
    }
  }
  await assert(
    `!document.querySelector('.operations-app') && ![...document.querySelectorAll('a,button')].some(el=>el.textContent.trim()==='Đăng ký')`,
    "Staff login exposes registration or private layout",
  );
  await click("Đăng nhập");
  await assert(
    `document.querySelectorAll('.staff-auth-error').length === 2 && document.activeElement.name==='identifier'`,
    "Staff validation/focus failed",
  );
  await fill("identifier", "NV-TEST");
  await fill("password", "sample-password");
  await evaluate(
    `document.querySelector('[aria-label="Hiện mật khẩu"]').click()`,
  );
  await until(`document.querySelector('[name="password"]').type==='text'`);
  await click("Đăng nhập");
  await until(
    `document.querySelector('[role="alert"]')?.textContent.includes('Chưa kết nối')`,
  );
  await assert(
    `!sessionStorage.getItem('operations.ui-preview')`,
    "Submitting credentials opened preview",
  );
  await click("Quên mật khẩu?");
  await until(`!!document.querySelector('.staff-auth-help')`);
  await click("Quay lại đăng nhập");
  await until(`!!document.querySelector('[name="password"]')`);
  await assert(
    `document.querySelector('[name="password"]').value === ''`,
    "Password retained in help flow",
  );
  await click("Xem bản trải nghiệm");
  await until(`!!document.querySelector('.operations-app')`);
  await click("Thoát trải nghiệm");
  await until(
    `location.pathname==='/operations/login' && !!document.querySelector('.staff-auth')`,
  );
  await command("Page.navigate", {
    url: "http://127.0.0.1:3020/operations/my-tasks",
  });
  await until(
    `location.pathname==='/operations/login' && !!document.querySelector('.staff-auth')`,
  );
  await go("http://127.0.0.1:3011/login", ".resident-auth");
  await evaluate(`sessionStorage.removeItem('resident.ui-preview')`);
  await command("Page.navigate", { url: "http://127.0.0.1:3011/#/register" });
  await until(`location.pathname==='/register' && !!document.querySelector('.resident-auth--register')`);
  await command("Page.navigate", { url: "http://127.0.0.1:3011/" });
  await until(
    `location.pathname==='/login' && !!document.querySelector('.resident-auth')`,
  );
  await click("Khám phá bản trải nghiệm");
  await until(`!!document.querySelector('.app-shell')`);
  await go("http://127.0.0.1:3011/#/profile", ".profile-card");
  await click("Thoát trải nghiệm về đăng nhập");
  await until(
    `location.pathname==='/login' && !!document.querySelector('.resident-auth')`,
  );
  for (const status of ["verification-required", "membership-pending"]) {
    await go(
      `http://127.0.0.1:3011/account-status?preview=${status}`,
      ".resident-auth-status",
    );
    for (const width of [320, 390, 1440]) {
      await command("Emulation.setDeviceMetricsOverride", {
        width,
        height: 900,
        deviceScaleFactor: 1,
        mobile: width < 761,
      });
      await assert(
        "document.documentElement.scrollWidth <= innerWidth",
        `Resident status overflows ${width}`,
      );
    }
  }
  if (exceptions.length) throw new Error(exceptions.join("\n"));
  console.log(
    "PASS: separate login layouts, mobile/desktop overflow, staff validation, password visibility/help, no false auth, explicit demo entry/exit, protected demo navigation, resident status previews.",
  );
} finally {
  socket.close();
  await fetch(`http://127.0.0.1:9333/json/close/${target.id}`);
}
