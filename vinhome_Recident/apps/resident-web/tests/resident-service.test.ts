import { describe, expect, test } from "vitest";
import { initialState } from "../src/mocks/seed";
import {
  loadState,
  reply,
  resolveRequest,
  saveState,
  submitDraft,
} from "../src/services/resident-service";

describe("Resident request journey", () => {
  test("chat drafts do not become requests until explicit confirmation; reload preserves the same record", () => {
    let state = initialState();
    state = reply(state, "Báo sự cố");
    state = reply(state, "Vòi nước bồn rửa bị rò");
    expect(state.draft?.step).toBe("location");
    expect(state.requests).toHaveLength(1);
    state = reply(state, "Căn hộ S2.02 1208");
    expect(state.draft?.step).toBe("review");
    state = reply(state, "Nước chảy khá nhiều");
    expect(state.draft?.description).toContain("Nước chảy khá nhiều");
    state = submitDraft(state);
    expect(state.requests).toHaveLength(2);
    expect(state.requests[0].status).toBe("received");
    expect(state.messages.at(-1)?.requestId).toBe(state.requests[0].id);
    expect(() => submitDraft(state)).toThrow();
    let saved = "";
    saveState(
      {
        setItem: (_, value) => {
          saved = value;
        },
      },
      state,
    );
    expect(loadState({ getItem: () => saved })).toEqual(state);
  });
  test("rejects incomplete submission and does not create an incident from an information question", () => {
    const state = reply(initialState(), "Giờ mở cửa bể bơi?");
    expect(state.draft).toBeNull();
    expect(state.requests).toHaveLength(1);
    expect(() => submitDraft(state)).toThrow();
    expect(() => submitDraft(reply(initialState(), "Báo sự cố"))).toThrow();
  });
  test("confirmation is one-time and rework requires a reason, reflected in the timeline and chat", () => {
    const state = initialState();
    const requestId = state.requests[0].id;
    expect(() => resolveRequest(state, requestId, false, "")).toThrow();
    const redo = resolveRequest(
      state,
      requestId,
      false,
      "Đèn vẫn bị nhấp nháy",
    );
    expect(redo.requests[0].status).toBe("processing");
    expect(redo.requests[0].events.at(-1)?.note).toBe("Đèn vẫn bị nhấp nháy");
    expect(redo.messages.at(-1)?.requestId).toBe(requestId);
    const done = resolveRequest(state, requestId, true);
    expect(done.requests[0].status).toBe("completed");
    expect(() => resolveRequest(done, requestId, true)).toThrow();
  });
  test("quota/storage failures surface instead of returning success", () => {
    expect(() =>
      saveState(
        {
          setItem: () => {
            throw new Error("quota");
          },
        },
        initialState(),
      ),
    ).toThrow("Chưa lưu được");
  });
  test("validates stored data before rendering, including nested records and unsafe photo URLs", () => {
    expect(loadState({ getItem: () => null }).version).toBe(1);
    for (const invalid of [
      "{}",
      "{",
      JSON.stringify({
        version: 1,
        requests: [null],
        messages: [],
        draft: null,
      }),
    ]) {
      expect(() => loadState({ getItem: () => invalid })).toThrow();
    }
    const state = initialState();
    state.requests[0].photos = [
      { id: "a", name: "a", url: "javascript:alert(1)" },
    ];
    expect(() => loadState({ getItem: () => JSON.stringify(state) })).toThrow();
    state.requests[0].photos = [];
    state.requests[0].createdAt = "not-a-date";
    expect(() => loadState({ getItem: () => JSON.stringify(state) })).toThrow();
  });
  test("limits photos across consecutive messages without changing the prior draft", () => {
    const photo = {
      id: "a",
      name: "a.jpg",
      url: "data:image/jpeg;base64,AA==",
    };
    const state = reply(initialState(), "Vòi nước bị rò", [
      photo,
      { ...photo, id: "b" },
    ]);
    expect(() => reply(state, "Căn hộ 1208", [photo, photo])).toThrow(
      "tối đa 3 ảnh",
    );
    expect(state.draft?.photos).toHaveLength(2);
  });
});
