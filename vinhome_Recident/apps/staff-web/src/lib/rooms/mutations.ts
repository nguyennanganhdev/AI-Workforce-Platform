import { mutationOptions, type QueryClient } from "@tanstack/react-query";
import { client } from "@/lib/client";
import { businessHeaders } from "@/lib/coordination/queries";
import { roomKeys } from "@/lib/rooms/queries";
import { ACCEPTED_IMAGE_MIME, ACCEPTED_TEXT_MIME, MAX_ATTACHMENTS_PER_MESSAGE, MAX_FILE_BYTES, MAX_IMAGE_BYTES,
  classifyAttachment, mediaTypeOf } from "../../../../../packages/shared/attachments";

const BY_EXTENSION: Record<string, string> = {png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", gif: "image/gif", webp: "image/webp",
  txt: "text/plain", md: "text/markdown", csv: "text/csv", json: "application/json"};
/** What the file dialog offers: the platform's accepted types, and their extensions for files a browser names no type for. */
export const ROOM_FILE_ACCEPT = [...ACCEPTED_IMAGE_MIME, ...ACCEPTED_TEXT_MIME, ...Object.keys(BY_EXTENSION).map((e) => `.${e}`)].join(",");
/** The type a picked file is uploaded as: the browser's claim when the platform accepts it, else what its name says. The API checks the bytes. */
export function roomFileType(file: {name: string; type: string}): string | null {
  const claimed = mediaTypeOf(file.type);
  if (["image", "text"].includes(classifyAttachment(claimed))) return claimed;
  return BY_EXTENSION[file.name.split(".").pop()?.toLowerCase() ?? ""] ?? null;
}
/** Why these files cannot go on one message, in the reader's words, or null when they can. The platform's limits (shared/attachments.ts). */
export function roomFilesRefusal(files: {name: string; type: string; size: number}[]): string | null {
  if (files.length > MAX_ATTACHMENTS_PER_MESSAGE) return `Mỗi tin nhắn tối đa ${MAX_ATTACHMENTS_PER_MESSAGE} tệp.`;
  for (const file of files) {
    const type = roomFileType(file);
    if (!type) return `${file.name}: chỉ đính kèm được ảnh (PNG, JPEG, GIF, WebP) hoặc tệp văn bản (.txt, .md, .csv, .json).`;
    if (file.size > (classifyAttachment(type) === "image" ? MAX_IMAGE_BYTES : MAX_FILE_BYTES)) return `${file.name}: ảnh tối đa 8 MB, tệp văn bản tối đa 1 MB.`;
  }
  return null;
}
// A send that failed after its files were stored sends again without storing them twice.
const uploaded = new WeakMap<File, Promise<string>>();
function uploadRoomFile(roomId: string, file: File): Promise<string> {
  const known = uploaded.get(file);
  if (known) return known;
  const sent = (async () => {
    const response = await fetch(`/api/business/rooms/${encodeURIComponent(roomId)}/files?filename=${encodeURIComponent(file.name)}&mimeType=${encodeURIComponent(roomFileType(file) ?? "")}`,
      {method: "POST", credentials: "include", headers: {...businessHeaders(), "content-type": "application/octet-stream"}, body: file});
    if (!response.ok) {
      const detail = (await response.json().catch(() => ({}))).detail;
      throw new Error(typeof detail === "string" && [413, 422].includes(response.status) ? `${file.name}: ${detail}` : `Không tải lên được ${file.name}.`);
    }
    return (await response.json()).fileId as string;
  })();
  uploaded.set(file, sent);
  sent.catch(() => uploaded.delete(file));
  return sent;
}
export function postRoomMessageMutationOptions(queryClient: QueryClient) {
  return mutationOptions({mutationFn: async ({roomId, text, agentId, requestId, files = []}: {roomId: string; text: string; agentId: string; requestId: string; files?: File[]}) => {
    const fileIds: string[] = [];
    for (const file of files) fileIds.push(await uploadRoomFile(roomId, file));
    await client(`/api/business/rooms/${encodeURIComponent(roomId)}/messages`, {method: "POST", headers: businessHeaders(),
      body: {text, mention_agent_id: agentId || null, client_message_id: requestId, file_ids: fileIds}, fallback: "Không gửi được tin nhắn nhóm."});
  }, onSuccess: (_, {roomId}) => queryClient.invalidateQueries({queryKey: roomKeys.detail(roomId)})});
}
/** Management's three decisions inside a session. Each one changes what the session waits for. */
function sessionAction<T>(queryClient: QueryClient, send: (input: T) => Promise<unknown>) {
  return mutationOptions({mutationFn: send, onSuccess: () => queryClient.invalidateQueries({queryKey: roomKeys.all})});
}
export function decidePlanMutationOptions(queryClient: QueryClient) {
  return sessionAction(queryClient, ({planId, decision, version, note}: {planId: string; decision: "approve" | "reject"; version: number; note: string}) =>
    client(`/api/business/plans/${encodeURIComponent(planId)}/management-decision`, {method: "POST", headers: businessHeaders(),
      body: {decision, version, note}, fallback: "Không ghi được quyết định."}));
}
export function askSessionAgentMutationOptions(queryClient: QueryClient) {
  // A session's messages live in its management room, so its files are uploaded there too.
  return sessionAction(queryClient, async ({ticketId, roomId, text, agentId, requestId, files = []}: {ticketId: string; roomId: string; text: string; agentId?: string; requestId: string; files?: File[]}) => {
    const fileIds: string[] = [];
    for (const file of files) fileIds.push(await uploadRoomFile(roomId, file));
    return client(`/api/business/tickets/${encodeURIComponent(ticketId)}/session/questions`, {method: "POST", headers: businessHeaders(),
      body: {text, client_message_id: requestId, file_ids: fileIds, ...(agentId ? {agent_id: agentId} : {})}, fallback: "Không gửi được câu hỏi cho agent."});
  });
}
export function closeSessionMutationOptions(queryClient: QueryClient) {
  return sessionAction(queryClient, ({ticketId, version}: {ticketId: string; version: number}) =>
    client(`/api/business/tickets/${encodeURIComponent(ticketId)}/session/close-approval`, {method: "POST", headers: businessHeaders(),
      body: {version}, fallback: "Không đóng được phiên."}));
}
