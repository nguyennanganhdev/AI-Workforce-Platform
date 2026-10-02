/**
 * Môi trường mock có điều khiển cho test (spec v0.3 §9): provider reset được về fixture, đồng hồ
 * giả dùng chung cho provider và wrapper, fault/barrier của WRITE, và endpoint HTTP `POST /faults`
 * để test chạy ngoài process (E2E) điều khiển được server mock. Không bao giờ bật ở production.
 */
import { readBodyText } from "../common/body";
import { isId } from "../common/context";
import { parseStrictJson, StrictJsonError } from "../common/strict-json";
import { loadFixtureScope, MockSecurityProvider } from "./mock-provider";
import {
  createMockWrite,
  createWriteControl,
  type MockWriteFault,
  type WorkerCommands,
  type WorkerResult,
  type WriteControl,
} from "./mock-write";
import {
  isWriteTool,
  type SecurityProvider,
  type WriteToolName,
} from "./provider";

// ---------------------------------------------------------------------------------------------
// Đồng hồ giả
// ---------------------------------------------------------------------------------------------

export type MockClock = {
  now(): Date;
  /** Đóng băng đồng hồ tại mốc này. */
  set(at: Date): void;
  /** Tiến đồng hồ; đang chạy theo giờ thật thì đóng băng tại giờ thật + ms. */
  advance(ms: number): void;
  /** Về giờ thật. */
  reset(): void;
};

export function createMockClock(): MockClock {
  let fixed: number | null = null;
  return {
    now: () => new Date(fixed ?? Date.now()),
    set: (at) => {
      fixed = at.getTime();
    },
    advance: (ms) => {
      fixed = (fixed ?? Date.now()) + ms;
    },
    reset: () => {
      fixed = null;
    },
  };
}

// ---------------------------------------------------------------------------------------------
// Môi trường mock
// ---------------------------------------------------------------------------------------------

export type MockEnvironment = {
  /** Provider ổn định cho wrapper; bên trong được dựng lại khi reset. */
  provider: SecurityProvider;
  clock: MockClock;
  control: WriteControl;
  /**
   * Lệnh nội bộ Core mà worker platform gọi (callback dispatch, kết quả gửi tin, nhận ACK, quá hạn).
   * Dùng chung state và đồng hồ với provider; callback thành công làm cũ cursor đã phát.
   */
  worker: WorkerCommands;
  /** Giữ WRITE của tool ở IN_PROGRESS tới khi `release` (barrier cho request đồng thời). */
  hold(tool: WriteToolName): void;
  release(tool: WriteToolName): void;
  /** Dữ liệu về fixture, ledger trống, bỏ fault/barrier, đồng hồ về giờ thật. */
  reset(): void;
};

export function createMockEnvironment(
  options: { cursorSecret?: string } = {},
): MockEnvironment {
  const clock = createMockClock();
  const control = createWriteControl();
  const releases = new Map<WriteToolName, () => void>();
  const build = () => {
    // Handler WRITE và worker phải dùng chung một createMockWrite: chung reservation guard,
    // bộ đếm id và chống trùng event_id. Worker sửa dữ liệu sống của chính provider này.
    let provider: MockSecurityProvider | undefined;
    const mock = createMockWrite({
      control,
      now: clock.now,
      scopeOf: (tenant, property) => provider?.liveScope(tenant, property),
    });
    provider = new MockSecurityProvider({
      scopes: [loadFixtureScope()],
      now: clock.now,
      cursorSecret: options.cursorSecret,
      writeHandlers: mock.handlers,
    });
    return { provider, worker: invalidatingCursors(mock.worker, provider) };
  };
  let current = build();

  const release = (tool: WriteToolName) => {
    releases.get(tool)?.();
    releases.delete(tool);
  };
  return {
    provider: {
      name: "mock",
      read: (tool, input, context, call) =>
        current.provider.read(tool, input, context, call),
      write: (tool, input, invocation, call) =>
        current.provider.write(tool, input, invocation, call),
    },
    clock,
    control,
    worker: {
      recordDispatchStatus: (input) =>
        current.worker.recordDispatchStatus(input),
      recordNotificationResult: (input) =>
        current.worker.recordNotificationResult(input),
      expireEscalation: (input) => current.worker.expireEscalation(input),
      recordAckReceipt: (input) => current.worker.recordAckReceipt(input),
    },
    hold(tool) {
      release(tool);
      releases.set(tool, control.hold(tool));
    },
    release,
    reset() {
      for (const tool of [...releases.keys()]) release(tool);
      control.reset();
      clock.reset();
      current = build();
    },
  };
}

/**
 * Worker sửa dữ liệu ngoài `write()` nên provider không tự biết snapshot đã đổi. Callback thành công
 * (không phải replay theo event_id) làm cũ cursor đã phát, để mọi trang của một cursor cùng snapshot.
 */
function invalidatingCursors(
  worker: WorkerCommands,
  provider: MockSecurityProvider,
): WorkerCommands {
  const after = <T>(result: WorkerResult<T>): WorkerResult<T> => {
    if (result.ok && !result.replayed) provider.invalidateCursors();
    return result;
  };
  return {
    recordDispatchStatus: (input) => after(worker.recordDispatchStatus(input)),
    recordNotificationResult: (input) =>
      after(worker.recordNotificationResult(input)),
    expireEscalation: (input) => after(worker.expireEscalation(input)),
    recordAckReceipt: (input) => after(worker.recordAckReceipt(input)),
  };
}

// ---------------------------------------------------------------------------------------------
// POST /faults
// ---------------------------------------------------------------------------------------------

/** Đủ 7 fault của §9; Record bắt buộc liệt kê hết, thiếu/thừa là lỗi biên dịch. */
const WRITE_FAULTS: Record<MockWriteFault, true> = {
  guard_unavailable: true,
  contact_unavailable: true,
  provider_error_before_commit: true,
  timeout_before_commit: true,
  timeout_after_commit: true,
  invalid_response: true,
  delivery_failed: true,
};

const MAX_CONTROL_BODY_BYTES = 4096;

/**
 * Handler `POST /faults`. Body là một lệnh:
 *
 *   { "action": "set_fault", "tool": "dispatch_guard", "fault": "timeout_after_commit", "times"?: 1 }
 *   { "action": "hold", "tool": "dispatch_guard" }      // barrier: WRITE kế tiếp chờ ở IN_PROGRESS
 *   { "action": "release", "tool": "dispatch_guard" }
 *   { "action": "set_clock", "at": "2026-10-01T03:00:00.000Z" }
 *   { "action": "advance_clock", "ms": 60000 }
 *   { "action": "reset" }
 *   { "action": "worker", "command": "<lệnh worker>", "input": { … } }   // xem workerCall
 *
 * Trả `{ "ok": true, "now": <giờ của đồng hồ mock> }`, lệnh worker có thêm `result`; lệnh sai → 400.
 */
export function createFaultsHandler(
  env: MockEnvironment,
): (request: Request) => Promise<Response> {
  const bad = (message: string) =>
    Response.json({ ok: false, error: message }, { status: 400 });
  return async (request) => {
    if (request.method !== "POST")
      return Response.json(
        { ok: false, error: "Method not allowed" },
        { status: 405, headers: { allow: "POST" } },
      );
    const body = await readBodyText(request, MAX_CONTROL_BODY_BYTES);
    if (!body.ok) return bad("Body không hợp lệ");
    let command: Record<string, unknown>;
    try {
      const parsed = parseStrictJson(body.text);
      if (
        parsed === null ||
        typeof parsed !== "object" ||
        Array.isArray(parsed)
      )
        return bad("Body phải là object");
      command = parsed as Record<string, unknown>;
    } catch (error) {
      if (error instanceof StrictJsonError)
        return bad("Body không phải JSON hợp lệ");
      throw error;
    }

    const tool = command.tool;
    const needTool = (): WriteToolName | null =>
      typeof tool === "string" && isWriteTool(tool) ? tool : null;
    switch (command.action) {
      case "set_fault": {
        const target = needTool();
        const fault = command.fault;
        const times = command.times ?? 1;
        if (!target) return bad("tool phải là một WRITE tool");
        if (typeof fault !== "string" || !Object.hasOwn(WRITE_FAULTS, fault))
          return bad(
            `fault phải là một trong: ${Object.keys(WRITE_FAULTS).join(", ")}`,
          );
        if (!Number.isSafeInteger(times) || (times as number) < 1)
          return bad("times phải là số nguyên ≥ 1");
        env.control.setFault(target, fault as MockWriteFault, times as number);
        break;
      }
      case "hold":
      case "release": {
        const target = needTool();
        if (!target) return bad("tool phải là một WRITE tool");
        if (command.action === "hold") env.hold(target);
        else env.release(target);
        break;
      }
      case "set_clock": {
        const at = typeof command.at === "string" ? new Date(command.at) : null;
        if (!at || Number.isNaN(at.getTime()))
          return bad("at phải là timestamp ISO 8601");
        env.clock.set(at);
        break;
      }
      case "advance_clock": {
        if (!Number.isSafeInteger(command.ms))
          return bad("ms phải là số nguyên");
        env.clock.advance(command.ms as number);
        break;
      }
      case "reset":
        env.reset();
        break;
      case "worker": {
        const call = workerCall(env.worker, command.command, command.input);
        if (typeof call === "string") return bad(call);
        // Lệnh hợp lệ thì luôn 200; kết quả nghiệp vụ (kể cả bị từ chối) nằm trong `result`.
        return Response.json({
          ok: true,
          now: env.clock.now().toISOString(),
          result: call(),
        });
      }
      default:
        return bad(
          "action phải là set_fault | hold | release | set_clock | advance_clock | reset | worker",
        );
    }
    return Response.json({ ok: true, now: env.clock.now().toISOString() });
  };
}

const WORKER_COMMANDS = [
  "recordDispatchStatus",
  "recordNotificationResult",
  "expireEscalation",
  "recordAckReceipt",
] as const;

/**
 * Kiểm `input` của một lệnh worker rồi trả hàm gọi nó, hoặc chuỗi lỗi. Chỉ kiểm kiểu và field bắt
 * buộc; luật nghiệp vụ (transition, version, deadline) do chính lệnh worker quyết.
 *
 *   { "action": "worker", "command": "recordNotificationResult", "input": { "tenant_id", "property_id",
 *     "event_id", "escalation_id", "expected_version", "result": "NOTIFIED", "provider_reference_id" } }
 */
function workerCall(
  worker: WorkerCommands,
  command: unknown,
  input: unknown,
): (() => WorkerResult<unknown>) | string {
  if (
    typeof command !== "string" ||
    !(WORKER_COMMANDS as readonly string[]).includes(command)
  ) {
    return `command phải là một trong: ${WORKER_COMMANDS.join(", ")}`;
  }
  if (input === null || typeof input !== "object" || Array.isArray(input)) {
    return "input phải là object";
  }
  const i = input as Record<string, unknown>;
  const missing = (fields: Record<string, (value: unknown) => boolean>) =>
    Object.entries(fields).find(([name, ok]) => !ok(i[name]))?.[0];
  const version = (v: unknown) => Number.isSafeInteger(v) && (v as number) >= 1;
  const optionalId = (v: unknown) => v === undefined || isId(v);
  const actor = (v: unknown) => {
    const a = v as { actor_id?: unknown; actor_type?: unknown } | null;
    return (
      a !== null &&
      typeof a === "object" &&
      isId(a.actor_id) &&
      (a.actor_type === "HUMAN" || a.actor_type === "SERVICE")
    );
  };
  const common = { tenant_id: isId, property_id: isId, event_id: isId };

  const fields: Record<
    (typeof WORKER_COMMANDS)[number],
    Record<string, (value: unknown) => boolean>
  > = {
    recordDispatchStatus: {
      ...common,
      dispatch_id: isId,
      expected_version: version,
      to: (v) => typeof v === "string",
      failure_code: optionalId,
    },
    recordNotificationResult: {
      ...common,
      escalation_id: isId,
      expected_version: version,
      result: (v) => v === "NOTIFIED" || v === "FAILED",
      provider_reference_id: isId,
      failure_code: optionalId,
    },
    expireEscalation: {
      ...common,
      escalation_id: isId,
      expected_version: version,
    },
    recordAckReceipt: {
      ...common,
      escalation_id: isId,
      contact_id: isId,
      actor,
    },
  };
  const name = command as (typeof WORKER_COMMANDS)[number];
  const bad = missing(fields[name]);
  if (bad !== undefined) return `input.${bad} thiếu hoặc sai kiểu`;
  // Đã kiểm field bắt buộc; kiểu chính xác của từng lệnh do WorkerCommands định nghĩa.
  return () => (worker[name] as (x: unknown) => WorkerResult<unknown>)(i);
}
