/** Explicit timer also bounds collaborators that do not implement fetch cancellation. */
export function operationDeadline(milliseconds: number, parent?: AbortSignal) {
  const controller = new AbortController();
  const cancel = () => controller.abort(parent?.reason);
  if (parent?.aborted) cancel();
  else parent?.addEventListener("abort", cancel, { once: true });
  const timer = setTimeout(
    () => controller.abort(new DOMException("Factory deadline exceeded.", "TimeoutError")),
    milliseconds,
  );
  return {
    signal: controller.signal,
    dispose() {
      clearTimeout(timer);
      parent?.removeEventListener("abort", cancel);
    },
  };
}

/** Bound bytes before decoding, including bodies without Content-Length. */
export async function readBoundedText(
  message: Request | Response,
  maxBytes: number,
): Promise<string> {
  if (Number(message.headers.get("content-length")) > maxBytes) {
    await message.body?.cancel().catch(() => {});
    throw new RangeError("Body exceeds byte limit.");
  }
  if (!message.body) return "";
  const reader = message.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  const parts: string[] = [];
  let bytes = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > maxBytes) throw new RangeError("Body exceeds byte limit.");
      parts.push(decoder.decode(value, { stream: true }));
    }
    parts.push(decoder.decode());
    return parts.join("");
  } catch (error) {
    await reader.cancel().catch(() => {});
    throw error;
  } finally {
    reader.releaseLock();
  }
}
