import type { ResidentState } from "../services/types";

export const resident = {
  name: "Minh An",
  apartment: "S2.02 · 1208",
  project: "Vinhomes Smart City",
};

export function initialState(): ResidentState {
  return {
    version: 1,
    messages: [],
    draft: null,
    requests: [
      {
        id: "YC-2409-018",
        title: "Đèn hành lang tầng 12",
        description: "Đèn hành lang gần thang máy tầng 12 nhấp nháy.",
        location: "S2.02 · Hành lang tầng 12",
        status: "confirmation",
        createdAt: "2026-09-28T08:30:00+07:00",
        photos: [],
        events: [
          { label: "Đã tiếp nhận phản ánh", at: "2026-09-28T08:30:00+07:00" },
          { label: "Đội kỹ thuật đang xử lý", at: "2026-09-28T10:00:00+07:00" },
          {
            label: "Chờ bạn xác nhận",
            at: "2026-09-28T15:00:00+07:00",
            note: "Kịch bản minh họa: đội kỹ thuật đã thay bóng đèn và kiểm tra hoạt động. Bạn vui lòng xác nhận kết quả.",
          },
        ],
      },
    ],
  };
}
