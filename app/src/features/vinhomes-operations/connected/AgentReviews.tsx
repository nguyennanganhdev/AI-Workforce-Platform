import { useCallback, useEffect, useState } from "react";

type EvaluationCase = {
  name: string;
  expected: string;
  actual: string;
  passed: boolean;
  explanation: string;
};
type Review = {
  id: string;
  version: number;
  name: string;
  created_at: string;
  configuration: {
    instructions?: string;
    description?: string;
    service_categories?: string[];
    mcp_tools?: { name: string }[];
  };
  evaluation: { evaluator: string; cases: EvaluationCase[] };
};
type Release = {
  agent_id: string;
  name: string;
  version_no: number;
  published_at: string;
  workspace: string | null;
  service_categories: string[] | null;
  tools: { name: string }[] | null;
};

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/business${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...(body ? { method: "POST", body: JSON.stringify(body) } : {}),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Không thực hiện được thao tác.",
    );
  return data;
}

const list = (values?: string[] | null) =>
  values?.length ? values.join(", ") : "không có";

/**
 * The platform admin's part of the agent flow: what is waiting for a decision, and what a
 * Supervisor may invite now. Approval publishes the version; revoking stops it at once, also in
 * sessions that already invited it. Drafting an agent and running its evaluation happen
 * elsewhere; this screen only shows their result.
 */
export function AgentReviews() {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [releases, setReleases] = useState<Release[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [pending, published] = await Promise.all([
      api<{ items: Review[] }>("/admin/agent-reviews?status=pending"),
      api<{ items: Release[] }>("/admin/agent-releases"),
    ]);
    setReviews(pending.items);
    setReleases(published.items);
  }, []);
  useEffect(() => {
    void load().catch((e) => setError(e.message));
  }, [load]);
  async function run(action: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await action();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lỗi kết nối.");
    } finally {
      setBusy(false);
    }
  }
  const note = (key: string) => notes[key]?.trim() ?? "";
  const noteField = (key: string, label: string) => (
    <label>
      {label}
      <input
        value={notes[key] ?? ""}
        maxLength={2000}
        onChange={(e) => setNotes({ ...notes, [key]: e.target.value })}
      />
    </label>
  );

  return (
    <>
      {error && (
        <p role="alert" className="live-error">
          {error}
        </p>
      )}
      <section className="ws-card">
        <h2>Agent chờ duyệt ({reviews.length})</h2>
        <p>
          Duyệt là phát hành: Supervisor được mời phiên bản này vào phòng của
          các ticket thuộc danh mục agent phục vụ.
        </p>
        {reviews.map((review) => {
          const cases = review.evaluation.cases;
          const passed = cases.filter((c) => c.passed).length;
          return (
            <article className="live-order" key={review.id}>
              <h3>{review.name}</h3>
              <p>{review.configuration.description}</p>
              <p>
                Danh mục phục vụ:{" "}
                {list(review.configuration.service_categories)} · Tool được cấp:{" "}
                {list(review.configuration.mcp_tools?.map((t) => t.name))}
              </p>
              <details>
                <summary>Chỉ dẫn của agent</summary>
                <p className="live-reply">
                  {review.configuration.instructions}
                </p>
              </details>
              <details>
                <summary>
                  Kết quả đánh giá: {passed}/{cases.length} ca đạt (
                  {review.evaluation.evaluator})
                </summary>
                {cases.map((c) => (
                  <div key={c.name}>
                    <p>
                      <strong>
                        {c.passed ? "Đạt" : "Không đạt"} · {c.name}
                      </strong>
                      : {c.expected}
                    </p>
                    <p className="live-reply">{c.actual}</p>
                  </div>
                ))}
              </details>
              <div className="live-actions">
                {noteField(review.id, "Ghi chú quyết định")}
                <button
                  type="button"
                  disabled={busy || !note(review.id)}
                  onClick={() =>
                    void run(() =>
                      api(`/admin/agent-reviews/${review.id}/decision`, {
                        decision: "approve",
                        version: review.version,
                        note: note(review.id),
                      }),
                    )
                  }
                >
                  Duyệt và phát hành
                </button>
                <button
                  type="button"
                  disabled={busy || !note(review.id)}
                  onClick={() =>
                    void run(() =>
                      api(`/admin/agent-reviews/${review.id}/decision`, {
                        decision: "reject",
                        version: review.version,
                        note: note(review.id),
                      }),
                    )
                  }
                >
                  Từ chối
                </button>
              </div>
            </article>
          );
        })}
      </section>
      <section className="ws-card">
        <h2>Agent đã phát hành ({releases.length})</h2>
        {releases.map((release) => (
          <article className="live-order" key={release.agent_id}>
            <h3>
              {release.name} · phiên bản {release.version_no}
            </h3>
            <p>
              {release.workspace ?? "Không rõ workspace"} · phát hành{" "}
              {new Date(release.published_at).toLocaleString("vi-VN")}
            </p>
            <p>
              Danh mục phục vụ: {list(release.service_categories)} · Tool được
              cấp: {list(release.tools?.map((t) => t.name))}
            </p>
            <div className="live-actions">
              {noteField(release.agent_id, "Lý do thu hồi")}
              <button
                type="button"
                disabled={busy || !note(release.agent_id)}
                onClick={() =>
                  void run(() =>
                    api(`/admin/agents/${release.agent_id}/release/revoke`, {
                      note: note(release.agent_id),
                    }),
                  )
                }
              >
                Thu hồi
              </button>
            </div>
          </article>
        ))}
      </section>
    </>
  );
}
