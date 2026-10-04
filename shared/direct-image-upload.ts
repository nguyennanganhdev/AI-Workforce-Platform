type BusinessApi = <T>(path: string, init?: RequestInit) => Promise<T>;
type Upload = { storage: "s3" | "api"; status?: string; uploadId?: string; fileId?: string;
  uploadUrl?: string; fields?: Record<string, string> };

/** Metadata and verification go to the business API; the browser sends image bytes to S3. */
export async function uploadImage(api: BusinessApi, path: string, fallback: string, image: Blob,
  filename: string, idempotencyKey: string, purpose = "issue"): Promise<{ fileId: string }> {
  const bytes = await image.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const sha256 = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  const upload = await api<Upload>(path, { method: "POST", body: JSON.stringify({ filename,
    mime_type: image.type, size_bytes: image.size, sha256, idempotency_key: idempotencyKey, purpose }) });
  if (upload.storage === "api") {
    const result = await api<{ fileId?: string; id?: string }>(fallback, { method: "POST",
      headers: { "Content-Type": "application/octet-stream", "Idempotency-Key": idempotencyKey }, body: image });
    const fileId = result.fileId ?? result.id;
    if (!fileId) throw new Error("Không nhận được mã ảnh đã lưu.");
    return { fileId };
  }
  if (upload.status === "ready" && upload.fileId) return { fileId: upload.fileId };
  if (!upload.uploadUrl || !upload.fields || !upload.uploadId) throw new Error("Không nhận được quyền tải ảnh.");
  const form = new FormData();
  for (const [name, value] of Object.entries(upload.fields)) form.append(name, value);
  form.append("file", image, filename);
  const response = await fetch(upload.uploadUrl, { method: "POST", body: form, credentials: "omit" });
  if (!response.ok) throw new Error("Kho ảnh chưa nhận được tệp. Vui lòng thử lại.");
  return api<{ fileId: string }>(`/direct-uploads/${encodeURIComponent(upload.uploadId)}/complete`, { method: "POST" });
}
