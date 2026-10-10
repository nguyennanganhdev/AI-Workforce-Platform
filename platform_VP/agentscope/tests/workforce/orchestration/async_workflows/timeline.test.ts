import { describe, expect, test } from "bun:test";

import {
  createTimelineApi,
  followTimeline,
} from "../../../../examples/web_ui/frontend/src/features/workforce/chat/ticket_timeline/api";
import {
  applyEvent,
  applyReceipt,
  applySnapshot,
  createTimeline,
  timelineKey,
} from "../../../../examples/web_ui/frontend/src/features/workforce/chat/ticket_timeline/state";
import type {
  TimelineBinding,
  TimelineSnapshot,
} from "../../../../examples/web_ui/frontend/src/features/workforce/chat/ticket_timeline/state";
import type {
  ConversationEvent,
  InboundReceipt,
} from "../../../../examples/web_ui/frontend/src/features/workforce/shared/contracts/workforce-v1";
import { MemoryEventCursorStore } from "../../../../examples/web_ui/frontend/src/features/workforce/shared/event_transport";

// Shared browser transport uses window timers; no DOM or production service fake.
Object.assign(globalThis, { window: { setTimeout, clearTimeout } });
const binding: TimelineBinding = {
  identityKey: "verified-owner-1",
  workflowId: "workflow-A",
  conversationId: "conversation-A",
  externalUserId: "user-1",
  externalConversationId: "chat-A",
  externalTicketId: "ticket-A",
};
const now = "2026-10-10T09:00:00Z";
const event = (update: Partial<ConversationEvent> = {}): ConversationEvent => ({
  schema_version: "1",
  event_id: "event-A",
  sequence: 1,
  event_type: "assistant.message",
  occurred_at: now,
  recorded_at: now,
  conversation_id: binding.conversationId,
  workflow_id: binding.workflowId,
  external_ticket_id: binding.externalTicketId,
  external_user_id: binding.externalUserId,
  external_conversation_id: binding.externalConversationId,
  payload: { message_id: "message-A", text: "Đã tiếp nhận A" },
  ...update,
});
const receipt = (): InboundReceipt => ({
  request_id: "request-A",
  request_status: "completed",
  conversation_id: binding.conversationId,
  workflow_id: binding.workflowId,
  external_ticket_id: binding.externalTicketId,
  workflow_state: "awaiting_user",
  workflow_revision: 2,
  next_action: "submit_reply",
  accepted_at: now,
  status_url: "/requests/request-A",
  conversation_url: "/conversations/conversation-A",
  event_stream_url: "/events",
  result: {
    messages: [
      {
        message_id: "message-A",
        workflow_id: binding.workflowId,
        sender: "assistant",
        text: "Đã tiếp nhận A",
        created_at: now,
      },
    ],
    data: {},
  },
});
const snapshot = (): TimelineSnapshot => ({
  conversation_id: binding.conversationId,
  external_user_id: binding.externalUserId,
  external_conversation_id: binding.externalConversationId,
  workflows: [
    {
      workflow_id: binding.workflowId,
      external_ticket_id: binding.externalTicketId,
      state: "awaiting_user",
      next_action: "submit_reply",
      revision: 2,
    },
  ],
  messages: [...receipt().result!.messages],
  pending_approvals: [],
  snapshot_cursor: "snapshot-A",
});
const sse = (item: ConversationEvent) =>
  new Response(
    `id: ${item.event_id}\nevent: ${item.event_type}\ndata: ${JSON.stringify(item)}\n\n`,
    { headers: { "Content-Type": "text/event-stream" } },
  );

// An in-flight snapshot returns after a newer POST updates the host state.
async function snapshotRace(
  options: {
    staleReads?: number;
    cached?: boolean;
    abortAfterStale?: boolean;
    abortOnRetry?: boolean;
    failFresh?: number;
    invalidStale?: boolean;
    conflictFresh?: boolean;
  } = {},
) {
  const stop = new AbortController();
  const store = new MemoryEventCursorStore();
  const cacheKey = `${timelineKey(binding)}:workforce:conversation:${binding.conversationId}`;
  if (options.cached) store.set(cacheKey, "cached-A");
  let current = applyReceipt(createTimeline(binding), receipt());
  let snapshots = 0;
  let streams = 0;
  let observedCursor: string | null = null;
  const connections: string[] = [];
  const staleReads = options.staleReads ?? 1;
  const api = createTimelineApi({
    baseUrl: "/workforce/v1/partner",
    getAccessToken: () => null,
    fetchImpl: async (input, init) => {
      if (String(input).includes("/events?")) {
        streams++;
        if (!options.cached && streams === 1)
          return new Response("", { status: 410 });
        observedCursor = new Headers(init?.headers).get("Last-Event-ID");
        return sse(
          event({
            event_id: "event-fresh",
            sequence: 9,
            event_type: "operation.status_changed",
            payload: {
              operation_type: "repair",
              status_schema: "v1",
              status: "arrived",
            },
          }),
        );
      }
      snapshots++;
      if (snapshots <= staleReads) {
        const old = snapshot();
        old.workflows[0] = { ...old.workflows[0], revision: current.revision };
        current = applyReceipt(current, {
          ...receipt(),
          workflow_revision: current.revision + 1,
          result: {
            messages: [
              ...receipt().result!.messages,
              {
                ...receipt().result!.messages[0],
                message_id: "message-post",
                text: "New POST",
              },
            ],
            data: {},
          },
        });
        if (options.invalidStale) old.external_user_id = "other-user";
        if (options.abortAfterStale) stop.abort();
        return Response.json(old);
      }
      if (options.failFresh)
        return new Response("", { status: options.failFresh });
      return Response.json({
        ...snapshot(),
        messages: [...current.messages],
        workflows: [
          {
            ...snapshot().workflows[0],
            revision: current.revision,
            ...(options.conflictFresh
              ? { state: "awaiting_confirmation", next_action: "confirm_close" }
              : {}),
          },
        ],
        snapshot_cursor: "snapshot-fresh",
      });
    },
  });
  let error: unknown = null;
  try {
    await followTimeline(
      api,
      current,
      (next) => {
        current = next;
        connections.push(next.connection);
        if (next.cursor === "event-fresh") stop.abort();
        if (
          options.abortOnRetry &&
          snapshots > 0 &&
          next.connection === "reconnecting"
        )
          stop.abort();
      },
      stop.signal,
      store,
      () => current,
    );
  } catch (caught) {
    error = caught;
  } finally {
    stop.abort();
  }
  return {
    current,
    snapshots,
    streams,
    observedCursor,
    connections,
    error,
    cachedCursor: store.get(cacheKey),
  };
}

describe("PHH Phase B snapshot concurrency regressions", () => {
  test("UI064 410 recovery refetches stale snapshot after concurrent POST", async () => {
    const result = await snapshotRace();
    expect(result.error).toBeNull();
    expect(result.snapshots).toBe(2);
    expect(result.streams).toBe(2);
    expect(result.current.revision).toBe(3);
    expect(result.current.messages.map((m) => m.message_id)).toEqual([
      "message-A",
      "message-post",
    ]);
    expect(result.observedCursor).toBe("snapshot-fresh");
    expect(result.connections).not.toContain("blocked");
  });
  test("UI065 cached cursor recovery tolerates the same POST race", async () => {
    const result = await snapshotRace({ cached: true });
    expect(result.error).toBeNull();
    expect(result.snapshots).toBe(2);
    expect(result.streams).toBe(1);
    expect(result.observedCursor).toBe("snapshot-fresh");
    expect(result.current.messages).toHaveLength(2);
  });
  test("UI066 several in-flight POST revisions recover without rollback", async () => {
    const result = await snapshotRace({ staleReads: 3 });
    expect(result.error).toBeNull();
    expect(result.snapshots).toBe(4);
    expect(result.current.revision).toBe(5);
    expect(result.current.messages).toHaveLength(2);
    expect(result.connections).not.toContain("blocked");
  });
  test("UI067 cancellation during stale recovery preserves the newer POST", async () => {
    const result = await snapshotRace({ abortAfterStale: true });
    expect(result.error).toBeNull();
    expect(result.snapshots).toBe(1);
    expect(result.streams).toBe(1);
    expect(result.current.revision).toBe(3);
    expect(result.current.messages).toHaveLength(2);
    expect(result.connections).not.toContain("blocked");
  });
  test("UI068 recovery permission denial still blocks after a stale response", async () => {
    const result = await snapshotRace({ failFresh: 403 });
    expect(result.error).toBeInstanceOf(Error);
    expect(result.snapshots).toBe(2);
    expect(result.current.connection).toBe("blocked");
    expect(result.current.revision).toBe(3);
    expect(result.cachedCursor).toBeNull();
  });
  test("UI069 foreign snapshot is rejected even when its revision is stale", async () => {
    const result = await snapshotRace({ invalidStale: true });
    expect(result.error).toBeInstanceOf(Error);
    expect(result.snapshots).toBe(1);
    expect(result.current.connection).toBe("blocked");
    expect(result.current.messages).toHaveLength(2);
  });
  test("UI070 abort during stale snapshot backoff stops further requests", async () => {
    const result = await snapshotRace({ abortOnRetry: true });
    expect(result.error).toBeNull();
    expect(result.snapshots).toBe(1);
    expect(result.streams).toBe(1);
    expect(result.current.revision).toBe(3);
    expect(result.connections).not.toContain("blocked");
  });
  test("UI071 same revision state conflict is not retried as stale", async () => {
    const result = await snapshotRace({ conflictFresh: true });
    expect(result.error).toBeInstanceOf(Error);
    expect(result.snapshots).toBe(2);
    expect(result.current.connection).toBe("blocked");
    expect(result.current.state).toBe("awaiting_user");
    expect(result.cachedCursor).toBeNull();
  });
});

describe("PHH Phase B timeline state", () => {
  test("UI001 POST then SSE produces one bubble", () => {
    const state = applyEvent(
      applyReceipt(createTimeline(binding), receipt()),
      event(),
    );
    expect(state.messages).toHaveLength(1);
  });
  test("UI002 SSE then POST produces one bubble", () => {
    expect(
      applyReceipt(applyEvent(createTimeline(binding), event()), receipt())
        .messages,
    ).toHaveLength(1);
  });
  test("UI003 repeated event is deduped", () => {
    const state = applyEvent(createTimeline(binding), event());
    expect(applyEvent(state, event())).toBe(state);
  });
  test("UI004 identity participates in cache key", () => {
    expect(timelineKey(binding)).not.toBe(
      timelineKey({ ...binding, identityKey: "verified-owner-2" }),
    );
  });
  test("UI005 ticket participates in cache key", () => {
    expect(timelineKey(binding)).not.toBe(
      timelineKey({ ...binding, externalTicketId: "ticket-B" }),
    );
  });
  test("UI006 message conflict fails without mutation", () => {
    const state = applyEvent(createTimeline(binding), event());
    expect(() =>
      applyEvent(
        state,
        event({
          event_id: "event-2",
          sequence: 2,
          payload: { message_id: "message-A", text: "Khác" },
        }),
      ),
    ).toThrow();
    expect(state.messages[0].text).toBe("Đã tiếp nhận A");
  });
  test("UI007 status is a card, never an assistant bubble", () => {
    const state = applyEvent(
      createTimeline(binding),
      event({
        event_type: "operation.status_changed",
        payload: {
          operation_type: "repair",
          status_schema: "v1",
          status: "assigned",
        },
      }),
    );
    expect(state.messages).toHaveLength(0);
    expect(state.cards).toHaveLength(1);
  });
  test("UI008 workflow closed cannot reopen", () => {
    const closed = applyEvent(
      createTimeline(binding),
      event({
        event_type: "workflow.closed",
        payload: {
          state: "closed",
          revision: 3,
          reason: "Done",
          closed_at: now,
        },
      }),
    );
    const next = applyEvent(
      closed,
      event({
        event_id: "event-2",
        sequence: 2,
        event_type: "workflow.status_changed",
        payload: { state: "active", revision: 4 },
      }),
    );
    expect(next.state).toBe("closed");
    expect(next.nextAction).toBe("none");
  });
  test("UI009 older receipt cannot regress status", () => {
    const current = applyReceipt(createTimeline(binding), {
      ...receipt(),
      workflow_revision: 3,
      workflow_state: "awaiting_confirmation",
      next_action: "confirm_close",
    });
    expect(applyReceipt(current, receipt()).state).toBe(
      "awaiting_confirmation",
    );
  });
  test("UI010 snapshot catch-up dedupes next POST", () => {
    const state = applySnapshot(createTimeline(binding), snapshot());
    expect(applyReceipt(state, receipt()).messages).toHaveLength(1);
    expect(state.cursor).toBe("snapshot-A");
  });
  test("UI011 sequence reversal fails", () => {
    const state = applyEvent(createTimeline(binding), event({ sequence: 3 }));
    expect(() =>
      applyEvent(state, event({ event_id: "other", sequence: 2 })),
    ).toThrow();
  });
  test("UI012 approvals have independent ids", () => {
    const state = applyEvent(
      createTimeline(binding),
      event({
        event_type: "approval.required",
        payload: {
          approval_id: "approval-A",
          summary: "Xác nhận A",
          expires_at: now,
        },
      }),
    );
    const next = applyEvent(
      state,
      event({
        event_id: "resolve-A",
        sequence: 2,
        event_type: "approval.resolved",
        payload: { approval_id: "approval-A", status: "approved" },
      }),
    );
    expect(state.approvalIds).toEqual(["approval-A"]);
    expect(next.approvalIds).toEqual([]);
  });
  test("UI013 closed stream cannot introduce new assistant message", () => {
    const state = applyEvent(
      createTimeline(binding),
      event({
        event_type: "workflow.closed",
        payload: {
          state: "closed",
          revision: 2,
          reason: "Done",
          closed_at: now,
        },
      }),
    );
    expect(() =>
      applyEvent(state, event({ event_id: "late-message", sequence: 2 })),
    ).toThrow();
  });
  test("UI014 snapshot foreign message fails", () => {
    const data = snapshot();
    data.messages[0] = { ...data.messages[0], workflow_id: "workflow-B" };
    expect(() => applySnapshot(createTimeline(binding), data)).toThrow();
  });
  test("UI015 snapshot older revision fails", () => {
    const state = {
      ...createTimeline(binding),
      state: "awaiting_confirmation" as const,
      revision: 3,
    };
    expect(() => applySnapshot(state, snapshot())).toThrow();
  });
  test("UI016 invalid timestamp fails", () => {
    expect(() =>
      applyEvent(
        createTimeline(binding),
        event({ occurred_at: "2026-10-10T09:00:00" }),
      ),
    ).toThrow();
  });
  test("UI017 unknown event fails without cursor advancement", () => {
    const state = createTimeline(binding);
    expect(() =>
      applyEvent(state, event({ event_type: "private.checkpoint" })),
    ).toThrow();
    expect(state.cursor).toBeNull();
  });
  test("UI018 failed receipt for other ticket cannot update state", () => {
    expect(() =>
      applyReceipt(createTimeline(binding), {
        ...receipt(),
        external_ticket_id: "ticket-B",
      }),
    ).toThrow();
  });
  test("UI019 invalid closed event fails", () => {
    expect(() =>
      applyEvent(
        createTimeline(binding),
        event({
          event_type: "workflow.closed",
          payload: { state: "active", revision: 2 },
        }),
      ),
    ).toThrow();
  });
  test("UI020 status revision conflict fails", () => {
    const current = applyReceipt(createTimeline(binding), receipt());
    expect(() =>
      applyEvent(
        current,
        event({
          event_type: "workflow.status_changed",
          payload: { state: "active", revision: 2 },
        }),
      ),
    ).toThrow();
  });
  for (const [offset, [field, value]] of Object.entries({
    conversation_id: "conversation-B",
    workflow_id: "workflow-B",
    external_user_id: "user-B",
    external_conversation_id: "chat-B",
    external_ticket_id: "ticket-B",
  }).entries()) {
    test(`UI${String(21 + offset).padStart(3, "0")}: ${field} cross-chat event rejected`, () => {
      const state = createTimeline(binding);
      expect(applyEvent(state, event()).messages).toHaveLength(1);
      expect(() => applyEvent(state, event({ [field]: value }))).toThrow();
    });
  }
});

describe("PHH Phase B precision regressions", () => {
  test("UI037 pending receipt preserves watch_request while workflow is waiting", () => {
    const result = {
      ...receipt(),
      request_status: "accepted" as const,
      workflow_state: "waiting_external_event" as const,
      next_action: "watch_request" as const,
      result: null,
    };
    const state = applyReceipt(createTimeline(binding), result);
    expect(state.nextAction).toBe("watch_request");
  });
  test("UI038 failed receipt uses resolve_attention rather than watch_request", () => {
    const state = applyReceipt(createTimeline(binding), {
      ...receipt(),
      request_status: "failed",
      workflow_state: "active",
      next_action: "resolve_attention",
      result: null,
    });
    expect(state.nextAction).toBe("resolve_attention");
  });
  test("UI039 snapshot rejects inconsistent next_action", () => {
    const invalid = snapshot();
    invalid.workflows[0].next_action = "none";
    expect(() => applySnapshot(createTimeline(binding), invalid)).toThrow();
  });
  test("UI040 unknown public payload fields fail before cursor advancement", () => {
    expect(() =>
      applyEvent(
        createTimeline(binding),
        event({
          payload: {
            message_id: "message-A",
            text: "Allowed",
            credential_ref: "private-test-reference",
          },
        }),
      ),
    ).toThrow();
  });
  test("UI041 duplicate event id with changed payload is a conflict", () => {
    const state = applyEvent(createTimeline(binding), event());
    expect(() =>
      applyEvent(
        state,
        event({ payload: { message_id: "message-A", text: "Different" } }),
      ),
    ).toThrow();
    expect(state.cursor).toBe("event-A");
    expect(state.messages[0].text).toBe("Đã tiếp nhận A");
  });
  test("UI042 identical duplicate ignores object key ordering", () => {
    const state = applyEvent(createTimeline(binding), event());
    expect(
      applyEvent(
        state,
        event({ payload: { text: "Đã tiếp nhận A", message_id: "message-A" } }),
      ),
    ).toBe(state);
  });
  test("UI043 array payload cannot masquerade as a public object", () => {
    expect(() =>
      applyEvent(
        createTimeline(binding),
        event({
          event_type: "workflow.needs_attention",
          payload: [] as unknown as ConversationEvent["payload"],
        }),
      ),
    ).toThrow();
  });
  test("UI044 event id must be a string", () => {
    expect(() =>
      applyEvent(
        createTimeline(binding),
        event({ event_id: 5 as unknown as string }),
      ),
    ).toThrow();
  });
  test("UI045 closed POST still permits historical messages replayed before close", () => {
    const state = applyReceipt(createTimeline(binding), {
      ...receipt(),
      workflow_state: "closed",
      workflow_revision: 3,
      next_action: "none",
      result: { messages: [], data: {} },
    });
    const replayed = applyEvent(state, event());
    expect(replayed.state).toBe("closed");
    expect(replayed.messages).toHaveLength(1);
  });
  test("UI046 non existent calendar timestamp is rejected", () => {
    expect(() =>
      applyEvent(
        createTimeline(binding),
        event({ occurred_at: "2026-02-30T09:00:00Z" }),
      ),
    ).toThrow();
  });
  test("UI047 snapshot cursor must be null or a nonempty string", () => {
    expect(() =>
      applySnapshot(createTimeline(binding), {
        ...snapshot(),
        snapshot_cursor: "",
      }),
    ).toThrow();
  });
  test("UI048 snapshot approval cannot reference another workflow", () => {
    const invalid = {
      ...snapshot(),
      pending_approvals: [
        { approval_id: "approval-A", workflow_id: "workflow-B" },
      ],
    };
    expect(() => applySnapshot(createTimeline(binding), invalid)).toThrow();
  });
  test("UI049 REST refresh retries the identical command exactly once", async () => {
    let calls = 0;
    let refreshes = 0;
    const bodies: unknown[] = [];
    const api = createTimelineApi({
      baseUrl: "/workforce/v1/partner",
      getAccessToken: () => "token",
      refreshAccessToken: async () => {
        refreshes++;
      },
      fetchImpl: async (_, init) => {
        bodies.push(init?.body);
        return calls++ === 0
          ? new Response("", { status: 401 })
          : Response.json(receipt());
      },
    });
    await api.post({
      schema_version: "1",
      command_type: "start_workflow",
      external_request_id: "post-A",
      external_management_ref: "management-1",
      external_user_id: "user-1",
      external_conversation_id: "chat-A",
      external_ticket_id: "ticket-A",
      message: { type: "text", text: "Request" },
    });
    expect(calls).toBe(2);
    expect(refreshes).toBe(1);
    expect(bodies[0]).toBe(bodies[1]);
  });
  test("UI050 follower preserves a concurrent POST through the current-state provider", async () => {
    const stop = new AbortController();
    let current = createTimeline(binding);
    const api = createTimelineApi({
      baseUrl: "/workforce/v1/partner",
      getAccessToken: () => null,
      fetchImpl: async () => {
        current = applyReceipt(current, receipt());
        return sse(
          event({
            event_id: "event-B",
            payload: { message_id: "message-B", text: "Second" },
          }),
        );
      },
    });
    await followTimeline(
      api,
      current,
      (next) => {
        current = next;
        if (next.cursor === "event-B") stop.abort();
      },
      stop.signal,
      new MemoryEventCursorStore(),
      () => current,
    );
    expect(current.messages.map((m) => m.message_id)).toEqual([
      "message-A",
      "message-B",
    ]);
    expect(current.state).toBe("awaiting_user");
  });
  test("UI051 cached cursor recovery denial publishes blocked state", async () => {
    const store = new MemoryEventCursorStore();
    store.set(
      `${timelineKey(binding)}:workforce:conversation:${binding.conversationId}`,
      "cached-A",
    );
    let current = createTimeline(binding);
    const api = createTimelineApi({
      baseUrl: "/workforce/v1/partner",
      getAccessToken: () => null,
      fetchImpl: async () => new Response("", { status: 403 }),
    });
    await expect(
      followTimeline(
        api,
        current,
        (next) => {
          current = next;
        },
        new AbortController().signal,
        store,
      ),
    ).rejects.toThrow();
    expect(current.connection).toBe("blocked");
  });
  test("UI052 abort during token loading prevents a detached REST request", async () => {
    const stop = new AbortController();
    let calls = 0;
    const api = createTimelineApi({
      baseUrl: "/workforce/v1/partner",
      getAccessToken: async () => {
        stop.abort();
        return "token";
      },
      fetchImpl: async () => {
        calls++;
        return Response.json(receipt());
      },
    });
    await expect(
      api.readResult("request-A", "user-1", stop.signal),
    ).rejects.toThrow();
    expect(calls).toBe(0);
  });
});

describe("PHH Phase B shared transport integration", () => {
  test("UI026 follower applies event and stops on abort", async () => {
    const stop = new AbortController();
    let final = createTimeline(binding);
    const api = createTimelineApi({
      baseUrl: "/workforce/v1/partner",
      getAccessToken: () => "trusted-token",
      fetchImpl: async () => sse(event()),
    });
    await followTimeline(
      api,
      final,
      (state) => {
        final = state;
        if (state.messages.length) stop.abort();
      },
      stop.signal,
    );
    expect(final.messages).toHaveLength(1);
  });
  test("UI027 wrong binding stops before cursor is saved", async () => {
    const store = new MemoryEventCursorStore();
    const stop = new AbortController();
    const api = createTimelineApi({
      baseUrl: "/workforce/v1/partner",
      getAccessToken: () => null,
      fetchImpl: async () => sse(event({ external_ticket_id: "ticket-B" })),
    });
    await expect(
      followTimeline(
        api,
        createTimeline(binding),
        () => {},
        stop.signal,
        store,
      ),
    ).rejects.toThrow();
    expect(
      store.get(
        `${timelineKey(binding)}:workforce:conversation:${binding.conversationId}`,
      ),
    ).toBeNull();
  });
  test("UI028 410 recovers snapshot and uses fresh cursor", async () => {
    const stop = new AbortController();
    let calls = 0;
    let observedCursor: string | null = null;
    let final = createTimeline(binding);
    const api = createTimelineApi({
      baseUrl: "/workforce/v1/partner",
      getAccessToken: () => null,
      fetchImpl: async (input, init) => {
        if (!String(input).includes("/events?"))
          return Response.json(snapshot());
        if (calls++ === 0) return new Response("", { status: 410 });
        observedCursor = new Headers(init?.headers).get("Last-Event-ID");
        return sse(
          event({
            event_id: "event-next",
            sequence: 9,
            event_type: "operation.status_changed",
            payload: {
              operation_type: "repair",
              status_schema: "v1",
              status: "arrived",
            },
          }),
        );
      },
    });
    await followTimeline(
      api,
      final,
      (state) => {
        final = state;
        if (state.cursor === "event-next") stop.abort();
      },
      stop.signal,
    );
    expect(observedCursor).toBe("snapshot-A");
    expect(final.messages).toHaveLength(1);
  });
  test("UI029 denied stream stops and clears its cursor", async () => {
    let final = createTimeline(binding);
    const api = createTimelineApi({
      baseUrl: "/workforce/v1/partner",
      getAccessToken: () => null,
      fetchImpl: async () => new Response("", { status: 403 }),
    });
    await expect(
      followTimeline(
        api,
        final,
        (state) => {
          final = state;
        },
        new AbortController().signal,
      ),
    ).rejects.toThrow();
    expect(final.connection).toBe("blocked");
  });
  test("UI030 close API rejects other ticket before fetch", async () => {
    let calls = 0;
    const api = createTimelineApi({
      baseUrl: "/workforce/v1/partner",
      getAccessToken: () => null,
      fetchImpl: async () => {
        calls++;
        return Response.json({});
      },
    });
    expect(() =>
      api.close(binding, {
        schema_version: "1",
        external_request_id: "close-A",
        external_user_id: "user-1",
        external_conversation_id: "chat-A",
        external_ticket_id: "ticket-B",
        expected_revision: 2,
        reason: "Done",
        stop_tracking_only: false,
      }),
    ).toThrow();
    expect(calls).toBe(0);
  });
  test("UI031 close API uses exact workflow and revision", async () => {
    let path = "";
    let body: unknown;
    const api = createTimelineApi({
      baseUrl: "/workforce/v1/partner",
      getAccessToken: () => null,
      fetchImpl: async (input, init) => {
        path = String(input);
        body = JSON.parse(String(init?.body));
        return Response.json(receipt());
      },
    });
    await api.close(binding, {
      schema_version: "1",
      external_request_id: "close-A",
      external_user_id: "user-1",
      external_conversation_id: "chat-A",
      external_ticket_id: "ticket-A",
      expected_revision: 2,
      reason: "Done",
      stop_tracking_only: false,
    });
    expect(path).toEndWith("/workflows/workflow-A/close");
    expect(body).toHaveProperty("expected_revision", 2);
  });
  test("UI032 abort during snapshot never updates detached chat", async () => {
    const stop = new AbortController();
    const updates: string[] = [];
    const api = createTimelineApi({
      baseUrl: "/workforce/v1/partner",
      getAccessToken: () => null,
      fetchImpl: async (input) => {
        if (!String(input).includes("/events?")) {
          stop.abort();
          return Response.json(snapshot());
        }
        return new Response("", { status: 410 });
      },
    });
    await followTimeline(
      api,
      createTimeline(binding),
      (state) => updates.push(state.connection),
      stop.signal,
    );
    expect(updates).toEqual(["connecting"]);
  });
});
