/**
 * Đọc body HTTP có giới hạn theo byte, dùng cho request vào MCP và response từ Core.
 *
 * Giới hạn tính trên byte đã nhận, không phải số ký tự sau khi decode: chuỗi nhiều byte UTF-8 không
 * lách được giới hạn. Content-Length khai vượt thì từ chối không đọc; stream vượt thì hủy ngay ở
 * chunk vượt, không đọc hết body vào bộ nhớ.
 */

export type BodyText =
  | { ok: true; text: string }
  | { ok: false; reason: "too_large" | "invalid_utf8" };

export async function readBodyText(
  message: Request | Response,
  maxBytes: number,
): Promise<BodyText> {
  const declared = Number(message.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > maxBytes) {
    await message.body?.cancel().catch(() => {});
    return { ok: false, reason: "too_large" };
  }
  if (message.body === null) return { ok: true, text: "" };

  const reader = message.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > maxBytes) {
      await reader.cancel().catch(() => {});
      return { ok: false, reason: "too_large" };
    }
    chunks.push(value);
  }

  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    // fatal: byte UTF-8 sai bị từ chối, không âm thầm thay bằng U+FFFD.
    return {
      ok: true,
      text: new TextDecoder("utf-8", { fatal: true }).decode(bytes),
    };
  } catch {
    return { ok: false, reason: "invalid_utf8" };
  }
}
