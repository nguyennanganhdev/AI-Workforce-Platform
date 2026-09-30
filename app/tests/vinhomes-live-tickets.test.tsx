import { afterAll, afterEach, beforeAll, expect, test } from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import { LiveTicketInbox } from "../src/features/vinhomes-operations/components/live-ticket-inbox";

beforeAll(() => GlobalRegistrator.register());
const originalFetch = global.fetch;
afterEach(() => {
  global.fetch = originalFetch;
  cleanup();
});
afterAll(() => GlobalRegistrator.unregister());

function renderInbox() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <LiveTicketInbox />
    </QueryClientProvider>,
  );
}

test("shows a ticket returned by the authenticated API", async () => {
  global.fetch = Object.assign(
    async (url: RequestInfo | URL) => {
      expect(url).toBe("/api/vinhomes/tickets");
      return Response.json({
        tickets: [
          {
            id: "ticket-1",
            code: "VH-001",
            title: "Rò rỉ nước",
            status: "new",
            priority: null,
            severity: "unknown",
            triageStatus: "pending",
            createdAt: "2026-09-30T00:00:00.000Z",
          },
        ],
      });
    },
    { preconnect: originalFetch.preconnect },
  );
  const view = renderInbox();
  expect(await view.findByText("Rò rỉ nước")).toBeTruthy();
  expect(view.getByText("VH-001")).toBeTruthy();
});

test("shows an API error instead of treating it as an empty ticket list", async () => {
  global.fetch = Object.assign(
    async () =>
      Response.json({ error: "Authentication required." }, { status: 401 }),
    { preconnect: originalFetch.preconnect },
  );
  const view = renderInbox();
  expect((await view.findByRole("alert")).textContent).toBe(
    "Authentication required.",
  );
});
