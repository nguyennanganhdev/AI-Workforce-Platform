import { initialState } from "../mocks/seed";
import type {
  ChatMessage,
  Photo,
  ResidentRequest,
  ResidentState,
} from "./types";

export const STORAGE_KEY = "nha.resident.demo.v1";
export const MAX_PHOTOS = 3;
export const MAX_PHOTO_BYTES = 600 * 1024;
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const id = () => crypto.randomUUID();
const assistant = (text: string, requestId?: string): ChatMessage => ({
  id: id(),
  role: "assistant",
  text,
  requestId,
});
const normalized = (text: string) =>
  text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d");

// Local demo adapter. Replace this boundary with authenticated resident APIs;
// never use browser-supplied apartment/persona as server authorization.
export function loadState(storage: Pick<Storage, "getItem">): ResidentState {
  const raw = storage.getItem(STORAGE_KEY);
  if (!raw) return initialState();
  const value: unknown = JSON.parse(raw);
  if (!isState(value))
    throw new Error(
      "Dữ liệu trên thiết bị không hợp lệ. Vui lòng dùng nút đặt lại bản trải nghiệm.",
    );
  return value;
}

const record = (v: unknown): v is Record<string, unknown> =>
  !!v && typeof v === "object";
const dateValid = (v: unknown) =>
  typeof v === "string" && Number.isFinite(Date.parse(v));
const photosValid = (v: unknown): v is Photo[] =>
  Array.isArray(v) &&
  v.length <= MAX_PHOTOS &&
  v.every(
    (p) =>
      record(p) &&
      typeof p.id === "string" &&
      typeof p.name === "string" &&
      typeof p.url === "string" &&
      /^data:image\/(png|jpeg|webp);base64,/.test(p.url),
  );
function isState(v: unknown): v is ResidentState {
  if (
    !record(v) ||
    v.version !== 1 ||
    !Array.isArray(v.requests) ||
    !Array.isArray(v.messages)
  )
    return false;
  if (
    !v.requests.every(
      (r) =>
        record(r) &&
        ["id", "title", "description", "location", "createdAt"].every(
          (k) => typeof r[k] === "string",
        ) &&
        ["received", "processing", "confirmation", "completed"].includes(
          String(r.status),
        ) &&
        dateValid(r.createdAt) &&
        photosValid(r.photos) &&
        Array.isArray(r.events) &&
        r.events.length > 0 &&
        r.events.every(
          (e) =>
            record(e) &&
            typeof e.label === "string" &&
            dateValid(e.at) &&
            (e.note === undefined || typeof e.note === "string"),
        ),
    )
  )
    return false;
  if (
    !v.messages.every(
      (m) =>
        record(m) &&
        typeof m.id === "string" &&
        typeof m.text === "string" &&
        ["resident", "assistant"].includes(String(m.role)) &&
        (m.photos === undefined || photosValid(m.photos)) &&
        (m.requestId === undefined || typeof m.requestId === "string"),
    )
  )
    return false;
  const d = v.draft;
  return (
    d === null ||
    (record(d) &&
      ["description", "location", "review"].includes(String(d.step)) &&
      typeof d.description === "string" &&
      typeof d.location === "string" &&
      photosValid(d.photos))
  );
}

export function saveState(
  storage: Pick<Storage, "setItem">,
  state: ResidentState,
): void {
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    throw new Error(
      "Chưa lưu được trên thiết bị. Bộ nhớ có thể đã đầy hoặc bị chặn. Hãy giảm ảnh đính kèm và thử lại.",
    );
  }
}

export function reply(
  state: ResidentState,
  text: string,
  photos: Photo[] = [],
): ResidentState {
  const clean = text.trim();
  if (!clean && !photos.length) return state;
  if (clean.length > 2000) throw new Error("Tin nhắn tối đa 2.000 ký tự.");
  if (photos.length + (state.draft?.photos.length ?? 0) > MAX_PHOTOS)
    throw new Error("Mỗi phản ánh đính kèm tối đa 3 ảnh.");
  const next = structuredClone(state);
  next.messages.push({ id: id(), role: "resident", text: clean, photos });
  const key = normalized(clean);
  if (next.draft) {
    const draft = next.draft;
    draft.photos.push(...photos);
    if (draft.step === "description") {
      if (clean.length < 8) {
        next.messages.push(
          assistant(
            "Bạn mô tả thêm sự cố giúp mình nhé. Ví dụ: “Vòi nước dưới bồn rửa đang bị rò”.",
          ),
        );
      } else {
        draft.description = clean;
        draft.step = "location";
        next.messages.push(
          assistant(
            "Mình đã ghi nhận nội dung. Sự cố xảy ra ở đâu? Bạn có thể chọn căn hộ của mình hoặc nhập vị trí cụ thể.",
          ),
        );
      }
    } else if (draft.step === "location") {
      if (clean.length < 3)
        next.messages.push(
          assistant(
            "Bạn cho mình biết vị trí cụ thể nhé, ví dụ căn hộ, tầng hoặc khu vực chung.",
          ),
        );
      else {
        draft.location = clean;
        draft.step = "review";
        next.messages.push(
          assistant(
            "Bạn kiểm tra thông tin bên dưới nhé. Phản ánh chỉ được tạo khi bạn bấm “Gửi phản ánh”.",
          ),
        );
      }
    } else {
      if (clean) draft.description += `\nBổ sung: ${clean}`;
      next.messages.push(
        assistant(
          "Mình đã bổ sung thông tin. Bạn kiểm tra lại thẻ phản ánh trước khi gửi nhé.",
        ),
      );
    }
  } else if (
    /bao su co|bao phan anh|gui phan anh/.test(key) ||
    /ro nuoc|hong|hu hong|mat dien|nhap nhay|rac|tac nuoc|thang may bi|su co|vo ong|ngap|dieu hoa|tieng on/.test(
      key,
    ) ||
    photos.length
  ) {
    const generic =
      /^(bao su co|bao phan anh|gui phan anh)[.!]?$/.test(key) ||
      clean.length < 8;
    next.draft = {
      step: generic ? "description" : "location",
      description: generic ? "" : clean,
      location: "",
      photos: [...photos],
    };
    next.messages.push(
      assistant(
        generic
          ? "Mình sẵn sàng hỗ trợ. Bạn đang gặp sự cố gì? Hãy mô tả ngắn và gửi ảnh nếu có nhé."
          : "Mình sẽ giúp bạn lập phản ánh. Sự cố xảy ra ở đâu? Bạn có thể chọn căn hộ của mình hoặc nhập vị trí cụ thể.",
      ),
    );
  } else if (/yeu cau|tien do|phan anh/.test(key)) {
    const requests = next.requests.filter((r) => r.status !== "completed");
    next.messages.push(
      assistant(
        requests.length
          ? `Bạn có ${requests.length} yêu cầu chưa hoàn tất. Bạn có thể mở từng thẻ để xem tiến độ.`
          : "Bạn chưa có yêu cầu nào đang chờ xử lý. Khi cần hỗ trợ, hãy chọn “Báo sự cố” nhé.",
      ),
    );
    requests.forEach((r) => next.messages.push(assistant(r.title, r.id)));
  } else if (/tien ich|be boi|ho boi|gym|cong vien/.test(key)) {
    next.messages.push(
      assistant(
        "Bạn có thể xem bể bơi, phòng tập và không gian xanh trong tab Tiện ích. Lịch hoạt động và đặt chỗ chưa được kết nối trong bản trải nghiệm này.",
      ),
    );
  } else if (/ban quan ly|lien he|toa nha|noi quy/.test(key)) {
    next.messages.push(
      assistant(
        "Bạn mở Tiện ích → Thông tin tòa nhà để xem các đầu mục hướng dẫn. Thông tin liên hệ và nội quy chính thức sẽ được bổ sung khi kết nối Ban quản lý.",
      ),
    );
  } else {
    next.messages.push(
      assistant(
        "Mình đang hỗ trợ theo kịch bản trải nghiệm: báo sự cố, xem yêu cầu và tra cứu các mục tiện ích. Bạn có thể chọn gợi ý bên dưới hoặc mô tả sự cố để mình giúp lập phản ánh.",
      ),
    );
  }
  return next;
}

export function submitDraft(state: ResidentState): ResidentState {
  const d = state.draft;
  if (
    !d ||
    d.step !== "review" ||
    d.description.trim().length < 8 ||
    !d.location.trim()
  )
    throw new Error("Vui lòng bổ sung mô tả và vị trí trước khi gửi.");
  const now = new Date().toISOString();
  const request: ResidentRequest = {
    id: `YC-${id().slice(0, 8).toUpperCase()}`,
    title: d.description.split("\n")[0].slice(0, 90),
    description: d.description,
    location: d.location,
    photos: structuredClone(d.photos),
    status: "received",
    createdAt: now,
    events: [{ label: "Đã tiếp nhận trong bản trải nghiệm", at: now }],
  };
  return {
    ...state,
    draft: null,
    requests: [request, ...state.requests],
    messages: [
      ...state.messages,
      assistant(
        "Phản ánh đã được lưu trong bản trải nghiệm. Bạn có thể theo dõi ở thẻ bên dưới hoặc mục “Yêu cầu của tôi”. Chưa có thông tin nào được gửi đến Ban quản lý.",
        request.id,
      ),
    ],
  };
}

export function resolveRequest(
  state: ResidentState,
  requestId: string,
  accepted: boolean,
  reason = "",
): ResidentState {
  const request = state.requests.find((r) => r.id === requestId);
  if (!request || request.status !== "confirmation")
    throw new Error("Yêu cầu này hiện không ở bước chờ xác nhận.");
  if (!accepted && reason.trim().length < 8)
    throw new Error(
      "Bạn mô tả điều chưa được xử lý (ít nhất 8 ký tự) để đội kỹ thuật kiểm tra lại nhé.",
    );
  const label = accepted
    ? "Cư dân xác nhận hoàn tất"
    : "Cư dân yêu cầu kiểm tra lại";
  return {
    ...state,
    requests: state.requests.map((r) =>
      r.id === requestId
        ? {
            ...r,
            status: accepted ? "completed" : "processing",
            events: [
              ...r.events,
              {
                label,
                at: new Date().toISOString(),
                note: accepted ? undefined : reason.trim(),
              },
            ],
          }
        : r,
    ),
    messages: [
      ...state.messages,
      assistant(
        accepted
          ? "Cảm ơn bạn đã xác nhận. Yêu cầu đã hoàn tất trong bản trải nghiệm."
          : "Mình đã ghi nhận yêu cầu xử lý lại trong bản trải nghiệm.",
        requestId,
      ),
    ],
  };
}

export async function readPhotos(files: File[]): Promise<Photo[]> {
  if (files.length > MAX_PHOTOS)
    throw new Error("Bạn chọn tối đa 3 ảnh mỗi lần nhé.");
  for (const file of files) {
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type))
      throw new Error("Vui lòng dùng ảnh JPG, PNG hoặc WebP.");
    if (file.size > MAX_UPLOAD_BYTES)
      throw new Error(
        `Ảnh “${file.name}” vượt 10 MB. Hãy chọn ảnh nhỏ hơn nhé.`,
      );
  }
  const result: Photo[] = [];
  // Process sequentially to avoid decoding several large phone photos at once.
  for (const file of files) {
    let bitmap: ImageBitmap;
    try {
      bitmap = await createImageBitmap(file);
    } catch {
      throw new Error(
        `Không đọc được ảnh “${file.name}”. Hãy chọn lại ảnh JPG, PNG hoặc WebP hợp lệ.`,
      );
    }
    try {
      const scale = Math.min(1, 1280 / Math.max(bitmap.width, bitmap.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(bitmap.width * scale));
      canvas.height = Math.max(1, Math.round(bitmap.height * scale));
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Trình duyệt chưa hỗ trợ xử lý ảnh.");
      context.fillStyle = "#fff";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      let url = canvas.toDataURL("image/jpeg", 0.78);
      if (url.length > (MAX_PHOTO_BYTES * 4) / 3)
        url = canvas.toDataURL("image/jpeg", 0.5);
      if (
        !url.startsWith("data:image/jpeg;base64,") ||
        url.length > (MAX_PHOTO_BYTES * 4) / 3
      )
        throw new Error(
          "Ảnh vẫn quá lớn sau khi thu nhỏ. Hãy chọn ảnh khác nhé.",
        );
      result.push({ id: id(), name: file.name, url });
    } finally {
      bitmap.close();
    }
  }
  return result;
}
