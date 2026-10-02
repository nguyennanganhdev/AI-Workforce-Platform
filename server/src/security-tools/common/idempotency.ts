/**
 * Quyết định idempotency cho WRITE (spec v0.3 §5).
 *
 * MCP không lưu dedup production: bản ghi operation nằm ở Core, dùng chung mọi MCP instance, khóa
 * unique `(tenant_id, property_id, idempotency_key)`. File này chỉ là phần thuần "đọc bản ghi Core
 * trả về thì làm gì": provider thật dùng khi map phản hồi của Core, mock dùng cùng hàm để giữ
 * semantics giống nhau. Claim atomic nằm ở Core (hoặc ledger của mock), không ở đây.
 */
import type { WriteResult } from "../providers/provider";
import { type ToolError, toolError } from "./errors";
import type { WriteEvidence } from "./responses";

/** Trạng thái operation ở Core. UNKNOWN: outcome chưa rõ (timeout/mất kết nối), cần đối soát. */
export type OperationStatus =
  | "IN_PROGRESS"
  | "UNKNOWN"
  | "COMMITTED"
  | "REJECTED";

/** Thời gian giữ full result tối thiểu. Hết hạn thì còn tombstone key/hash/proposal, không còn result. */
export const RESULT_RETENTION_DAYS = 7;

export type OperationRecord<T = unknown> = {
  idempotency_key: string;
  /** Hash của ActionBinding đã ghi lúc claim. */
  payload_hash: string;
  proposal_id: string;
  status: OperationStatus;
  /** COMMITTED: kết quả của lần commit đầu. null khi đã archive nhưng tombstone còn. */
  result: { data: T; evidence: WriteEvidence } | null;
  /** REJECTED: failure terminal đã lưu của lần đầu. */
  rejection: ToolError | null;
};

/** Thứ cần so với bản ghi: lấy từ VerifiedWrite (claims đã verify, hash đã so với binding). */
export type OperationRequest = {
  idempotency_key: string;
  payload_hash: string;
  proposal_id: string;
};

export type ReplayResult<T> = Extract<WriteResult<T>, { ok: true }>;

export type IdempotencyDecision<T = unknown> =
  /** Chưa có operation nào cho key và proposal này: được claim và thực thi. */
  | { action: "EXECUTE" }
  /** Cùng key/hash đã commit: trả lại data/evidence của lần đầu với replayed=true. */
  | { action: "REPLAY"; result: ReplayResult<T> }
  /**
   * Không thực thi, không side effect mới. `replayed` = true khi `error` là failure terminal đã lưu
   * của lần đầu (operation REJECTED); false khi lỗi do chính lần gọi này (conflict, đang chạy...).
   */
  | { action: "REJECT"; error: ToolError; replayed: boolean };

/**
 * `byKey`: bản ghi cùng `(tenant, property, key)`. `byProposal`: bản ghi đang gắn proposal_id này,
 * có thể mang key khác (một proposal chỉ gắn một operation).
 *
 * | Trường hợp                                   | Kết quả                                              |
 * |----------------------------------------------|------------------------------------------------------|
 * | Cùng key, khác hash                          | IDEMPOTENCY_CONFLICT                                 |
 * | Cùng key/hash, COMMITTED                     | REPLAY (replayed=true, kể cả entity đã đổi)          |
 * | Cùng key/hash, COMMITTED nhưng đã archive    | IDEMPOTENCY_RESULT_EXPIRED (RECONCILE)               |
 * | Cùng key/hash, REJECTED                      | failure terminal đã lưu, replayed=true               |
 * | Cùng key/hash, IN_PROGRESS                   | IDEMPOTENCY_IN_PROGRESS (SAME_KEY, 1000ms)           |
 * | Cùng key/hash, UNKNOWN                       | PROVIDER_TIMEOUT (RECONCILE/UNKNOWN)                 |
 * | Key mới, proposal đã gắn key khác            | IDEMPOTENCY_CONFLICT                                 |
 */
export function decideIdempotency<T>(
  request: OperationRequest,
  byKey: OperationRecord<T> | null,
  byProposal: OperationRecord<T> | null = null,
): IdempotencyDecision<T> {
  if (byKey) {
    if (
      byKey.payload_hash !== request.payload_hash ||
      byKey.proposal_id !== request.proposal_id
    ) {
      return reject(
        "IDEMPOTENCY_CONFLICT",
        "Idempotency-Key đã gắn với payload khác.",
      );
    }
    switch (byKey.status) {
      case "COMMITTED":
        if (byKey.result === null) {
          return reject(
            "IDEMPOTENCY_RESULT_EXPIRED",
            "Kết quả đã archive; cần đối soát, không thực thi lại.",
          );
        }
        return {
          action: "REPLAY",
          result: {
            ok: true,
            data: byKey.result.data,
            evidence: byKey.result.evidence,
            replayed: true,
          },
        };
      case "REJECTED":
        if (byKey.rejection === null) {
          return reject(
            "IDEMPOTENCY_RESULT_EXPIRED",
            "Kết quả thất bại đã archive; cần đối soát, không thực thi lại.",
          );
        }
        return { action: "REJECT", error: byKey.rejection, replayed: true };
      case "IN_PROGRESS":
        return reject(
          "IDEMPOTENCY_IN_PROGRESS",
          "Operation đang chạy; thử lại cùng key.",
        );
      case "UNKNOWN":
        // Không takeover, không chạy lại: executor tra operation của Core để đối soát.
        return reject(
          "PROVIDER_TIMEOUT",
          "Chưa biết operation đã commit hay chưa; cần đối soát, không cấp key mới.",
        );
    }
  }
  if (byProposal && byProposal.idempotency_key !== request.idempotency_key) {
    return reject(
      "IDEMPOTENCY_CONFLICT",
      "Proposal đã gắn với một operation khác.",
    );
  }
  return { action: "EXECUTE" };
}

/** WriteResult sẵn có để trả cho wrapper, hoặc null khi cần thực thi. */
export function resultOf<T>(
  decision: IdempotencyDecision<T>,
): WriteResult<T> | null {
  switch (decision.action) {
    case "EXECUTE":
      return null;
    case "REPLAY":
      return decision.result;
    case "REJECT": {
      // `replayed` đi kèm failure để wrapper đặt meta.replayed; ProviderFailure khai báo cờ này là tùy chọn.
      const failure = {
        ok: false as const,
        error: decision.error,
        replayed: decision.replayed,
      };
      return failure;
    }
  }
}

function reject(
  code: Parameters<typeof toolError>[0],
  message: string,
): IdempotencyDecision<never> {
  return {
    action: "REJECT",
    error: toolError(code, message, { mode: "WRITE" }),
    replayed: false,
  };
}
