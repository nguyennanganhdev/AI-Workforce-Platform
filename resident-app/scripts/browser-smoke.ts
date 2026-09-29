// Run against an isolated Chrome debugging profile and the resident dev server:
// bun resident-app/scripts/browser-smoke.ts
// Chrome: --headless=new --remote-debugging-port=9333 --user-data-dir=<temporary profile>
const targets = (await fetch("http://127.0.0.1:9333/json/list").then((r) =>
  r.json(),
)) as { type: string; url: string; webSocketDebuggerUrl: string }[];
const target = targets.find(
  (t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:3011"),
);
if (!target)
  throw new Error(
    "Open the resident app on port 3011 in an isolated Chrome debugging session (9333).",
  );
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise<void>((resolve, reject) => {
  socket.onopen = () => resolve();
  socket.onerror = reject;
});
let sequence = 0;
const pending = new Map<
  number,
  { resolve: (value: any) => void; reject: (error: Error) => void }
>();
const errors: string[] = [];
socket.onmessage = (event) => {
  const data = JSON.parse(String(event.data));
  if (data.id) {
    const request = pending.get(data.id);
    pending.delete(data.id);
    if (data.error) request?.reject(new Error(JSON.stringify(data.error)));
    else request?.resolve(data.result);
  } else if (data.method === "Runtime.exceptionThrown")
    errors.push(JSON.stringify(data.params.exceptionDetails));
};
function command(
  method: string,
  params: Record<string, unknown> = {},
): Promise<any> {
  const id = ++sequence;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`Timeout: ${method}`));
    }, 15000);
    pending.set(id, {
      resolve: (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      reject: (error) => {
        clearTimeout(timer);
        reject(error);
      },
    });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression: string) {
  const result = await command("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails)
    throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
const settle = () => Bun.sleep(180);
async function screenshot(name: string) {
  await settle();
  const result = await command("Page.captureScreenshot", { format: "png" });
  await Bun.write(
    `.logs/resident-${name}.png`,
    Buffer.from(result.data, "base64"),
  );
}
async function clickText(text: string) {
  const found = await evaluate(
    `(() => { const el = [...document.querySelectorAll('button')].find(e => e.textContent.trim() === ${JSON.stringify(text)}); if(!el) return false; el.click(); return true; })()`,
  );
  if (!found) throw new Error(`Missing button: ${text}`);
  await settle();
}
async function send(text: string) {
  await evaluate(
    `(() => {const el = document.querySelector('.composer textarea'); Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(el,${JSON.stringify(text)}); el.dispatchEvent(new Event('input',{bubbles:true})); })()`,
  );
  await settle();
  await evaluate(`document.querySelector('.composer').requestSubmit()`);
  await settle();
}
async function assert(condition: string, message: string) {
  if (!(await evaluate(condition))) throw new Error(message);
}
try {
  await command("Runtime.enable");
  await command("Page.enable");
  // Only this app's demo key is removed, in the isolated testing profile.
  await evaluate(
    `localStorage.removeItem('nha.resident.demo.v1'); location.hash='/'; location.reload();`,
  );
  await Bun.sleep(700);
  for (const [width, height] of [
    [390, 844],
    [320, 640],
    [430, 932],
    [768, 1024],
    [1440, 1000],
  ]) {
    await command("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: width < 761,
    });
    await settle();
    await assert(
      "document.documentElement.scrollWidth <= innerWidth",
      `Horizontal overflow at ${width}`,
    );
    await assert(
      `document.querySelector('.composer').getBoundingClientRect().bottom <= innerHeight`,
      `Composer outside viewport at ${width}`,
    );
    await screenshot(`home-${width}`);
  }
  await command("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true,
  });
  await evaluate(`location.hash='/utilities'`);
  await settle();
  await screenshot("utilities-390");
  await evaluate(`location.hash='/'`);
  await settle();
  await clickText("Báo sự cốCó mình hỗ trợ");
  const document = await command("DOM.getDocument");
  const picker = await command("DOM.querySelector", {
    nodeId: document.root.nodeId,
    selector: ".composer input[type=file]",
  });
  await command("DOM.setFileInputFiles", {
    nodeId: picker.nodeId,
    files: [`${process.cwd()}/.logs/resident-home-390.png`],
  });
  await Bun.sleep(450);
  await assert(
    `!!document.querySelector('.attachment-strip img')`,
    "Photo attachment preview missing",
  );
  await send("Vòi nước dưới bồn rửa bị rò");
  await clickText("Căn hộ của tôi · 1208");
  await assert(
    `!!document.querySelector('.draft-card')`,
    "Draft review not shown",
  );
  await screenshot("draft-390");
  const savedConversation = await evaluate(
    `localStorage.getItem('nha.resident.demo.v1')`,
  );
  await evaluate(
    `document.querySelector('[aria-label="Thoát cuộc trò chuyện, về trang Trợ lý"]').click()`,
  );
  await settle();
  await assert(
    `location.hash === '#/' && !!document.querySelector('.greeting') && !document.querySelector('.draft-card')`,
    "Exit did not return home",
  );
  await assert(
    `localStorage.getItem('nha.resident.demo.v1') === ${JSON.stringify(savedConversation)}`,
    "Exit changed conversation or request data",
  );
  await evaluate(`document.querySelector('.resume-conversation').click()`);
  await settle();
  await assert(
    `location.hash === '#/chat' && !!document.querySelector('.draft-card')`,
    "Resume lost draft",
  );
  await evaluate(`history.back()`);
  await settle();
  await assert(
    `!!document.querySelector('.greeting')`,
    "Browser Back did not exit chat",
  );
  await evaluate(`history.forward()`);
  await settle();
  await assert(
    `!!document.querySelector('.draft-card')`,
    "Browser Forward did not restore chat",
  );
  await clickText("Gửi phản ánh");
  await assert(
    `JSON.parse(localStorage.getItem('nha.resident.demo.v1')).requests.length === 2`,
    "Request not persisted",
  );
  await assert(
    `JSON.parse(localStorage.getItem('nha.resident.demo.v1')).requests[0].photos.length === 1`,
    "Request lost photo attachment",
  );
  await evaluate(`location.hash='/requests'`);
  await settle();
  await assert(
    `document.querySelectorAll('.request-card').length === 2`,
    "Chat/list data mismatch",
  );
  await evaluate(`location.reload()`);
  await Bun.sleep(700);
  await assert(
    `document.querySelectorAll('.request-card').length === 2`,
    "Reload lost requests",
  );
  await evaluate(`location.hash='/requests/YC-2409-018'`);
  await settle();
  await screenshot("request-390");
  await clickText("Đã ổn, xác nhận hoàn tất");
  await assert(
    `document.querySelector('.detail-heading .status').textContent.includes('Hoàn tất')`,
    "Confirmation failed",
  );
  for (const page of [
    "utilities",
    "requests",
    "notifications",
    "profile",
    "building",
    "amenities",
  ]) {
    await evaluate(`location.hash='/${page}'`);
    await settle();
    await assert(
      "document.documentElement.scrollWidth <= innerWidth",
      `Overflow on ${page}`,
    );
    await assert(
      `!!document.querySelector('main').textContent.trim()`,
      `Empty ${page}`,
    );
  }
  await evaluate(`location.hash='/'`);
  await settle();
  // Reduced viewport emulates the available area above a software keyboard.
  await command("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 410,
    deviceScaleFactor: 1,
    mobile: true,
  });
  await settle();
  await assert(
    `document.querySelector('.composer').getBoundingClientRect().bottom <= innerHeight`,
    "Keyboard-sized viewport obscures composer",
  );
  await screenshot("keyboard-390");
  await assert(
    `(async () => {
    const {readPhotos} = await import('/src/services/resident-service.ts');
    const canvas = document.createElement('canvas'); canvas.width=2400; canvas.height=1800;
    const ctx=canvas.getContext('2d'); ctx.fillStyle='#45c5c5'; ctx.fillRect(0,0,2400,1800);
    const blob=await new Promise(resolve => canvas.toBlob(resolve,'image/png'));
    const photos=await readPhotos([new File([blob],'phone-photo.png',{type:'image/png'})]);
    const image=await createImageBitmap(await fetch(photos[0].url).then(r=>r.blob()));
    const valid=image.width===1280 && image.height===960 && photos[0].url.startsWith('data:image/jpeg;base64,'); image.close();
    let rejected=false; try {await readPhotos([new File(['bad'],'broken.png',{type:'image/png'})]);} catch {rejected=true;}
    return valid && rejected;
  })()`,
    "Phone photo resizing or invalid photo handling failed",
  );
  // Auth remains an isolated UI; unavailable BE must never look like a login success.
  const storedBeforeAuth = await evaluate(
    `JSON.stringify({local: {...localStorage}, session: {...sessionStorage}})`,
  );
  for (const [width, height] of [
    [320, 640],
    [390, 844],
    [430, 932],
    [768, 1024],
    [1440, 1000],
  ]) {
    await command("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: width < 761,
    });
    for (const mode of ["login", "register", "forgot-password"]) {
      await evaluate(`location.hash='/${mode}'`);
      await settle();
      await assert(
        `!!document.querySelector('.resident-auth') && !document.querySelector('.mobile-nav')`,
        "Auth layout leaked resident navigation",
      );
      await assert(
        "document.documentElement.scrollWidth <= innerWidth",
        `Auth overflow ${mode} ${width}`,
      );
      if (width === 390 || width === 1440)
        await screenshot(`auth-${mode}-${width}`);
    }
  }
  await command("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true,
  });
  const fillAuth = async (field: string, value: string) => {
    await evaluate(
      `(() => { const el=document.querySelector('[name="${field}"]'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,${JSON.stringify(value)}); el.dispatchEvent(new Event('input',{bubbles:true})); })()`,
    );
    await settle();
  };
  await evaluate(`location.hash='/login'`);
  await settle();
  await clickText("Đăng nhập");
  await assert(
    `document.querySelectorAll('.resident-auth-field-error').length===2 && document.activeElement.name==='phone'`,
    "Login validation/focus failed",
  );
  await fillAuth("phone", "0900000000");
  await fillAuth("password", "example-password");
  await evaluate(
    `document.querySelector('[aria-label="Hiện mật khẩu"]').click()`,
  );
  await settle();
  await assert(
    `document.querySelector('[name="password"]').type==='text'`,
    "Password visibility toggle failed",
  );
  await clickText("Đăng nhập");
  await assert(
    `location.hash==='#/login' && document.querySelector('[role="alert"]').textContent.includes('chưa được kết nối')`,
    "Unconfigured login reported success",
  );
  await evaluate(`document.querySelector('a[href="#/register"]').click()`);
  await settle();
  await fillAuth("fullName", "Cư dân thử nghiệm");
  await fillAuth("phone", "0900000000");
  await fillAuth("password", "example-password");
  await fillAuth("confirmPassword", "different-password");
  await clickText("Đăng ký");
  await assert(
    `document.querySelector('#resident-auth-confirmPassword-error').textContent.includes('chưa khớp')`,
    "Password mismatch not validated",
  );
  await fillAuth("confirmPassword", "example-password");
  await clickText("Đăng ký");
  await assert(
    `document.querySelector('[role="alert"]').textContent.includes('tài khoản chưa được tạo')`,
    "Registration pretended to create an account",
  );
  await evaluate(`document.querySelector('a[href="#/login"]').click()`);
  await settle();
  await assert(
    `document.querySelector('[name="password"]').value===''`,
    "Password survived auth route change",
  );
  await evaluate(
    `document.querySelector('a[href="#/forgot-password"]').click()`,
  );
  await settle();
  await fillAuth("phone", "0900000000");
  await clickText("Tiếp tục");
  await assert(
    `document.querySelector('[role="alert"]').textContent.includes('Chưa có mã xác minh')`,
    "Reset pretended to send a code",
  );
  await assert(
    `JSON.stringify({local: {...localStorage}, session: {...sessionStorage}}) === ${JSON.stringify(storedBeforeAuth)}`,
    "Auth persisted credentials or changed resident data",
  );
  await evaluate(`location.hash='/register'`);
  await settle();
  await evaluate(`location.reload()`);
  await Bun.sleep(700);
  await assert(
    `!!document.querySelector('.resident-auth--register')`,
    "Direct auth route/reload failed",
  );
  await command("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 410,
    deviceScaleFactor: 1,
    mobile: true,
  });
  await evaluate(
    `document.querySelector('.resident-auth-submit').scrollIntoView({block:'center'})`,
  );
  await settle();
  await assert(
    `document.querySelector('.resident-auth-submit').getBoundingClientRect().bottom <= innerHeight`,
    "Auth submit unreachable with keyboard-sized viewport",
  );
  await evaluate(`location.hash='/profile'`);
  await settle();
  await assert(
    `!!document.querySelector('a[href="#/login"]') && !!document.querySelector('a[href="#/register"]')`,
    "Profile is missing auth entry links",
  );
  if (errors.length) throw new Error(errors.join("\n"));
  console.log(
    "PASS: resident journey and auth at 5 viewport sizes; photo upload/resize; chat exit/resume; login/register/reset validation and route navigation; no credential persistence or fake auth success; keyboard-sized viewport; no runtime exceptions.",
  );
} finally {
  socket.close();
}
