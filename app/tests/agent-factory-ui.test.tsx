import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  test,
} from "bun:test";
import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, render, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { AgentDialog } from "@/components/agents/agent-dialog";
import { AgentProfile as AgentProfileCard } from "@/components/agents/agent-profile";
import { CreateAgentDialog } from "@/components/agents/create-agent-dialog";
import type {
  AgentFactoryService,
  FactoryUseCaseResult,
} from "../../server/src/agents/factory";
import { createAgentFactoryRoutes } from "../../server/src/agents/factory-routes";
import type { AgentProfileStore } from "../../server/src/agents/profile-store";
import type { AgentProfile } from "../../server/src/agents/profile-types";
import { createAgentRoutes } from "../../server/src/agents/routes";
import type {
  AgentSpec,
  FactoryIssue,
  FactoryReadiness,
} from "../../agent-factory/src/contracts";

/**
 * C01–C08: the generated-coworker UI against the server's own factory and agent routes, mounted
 * behind `fetch` the way `agent-dialog-built-in-edit.test.tsx` mounts them. The factory service is
 * a stub returning the use-case results the real one returns, so every status and envelope the
 * screen reads is the one `factory-routes.ts` actually serializes. Grants are HTTP-shaped: who may
 * grant is the server's decision and is covered by A10/A11 in `agent-factory-routes.test.ts`.
 */

beforeAll(() => GlobalRegistrator.register());
afterEach(cleanup);
afterAll(() => GlobalRegistrator.unregister());

const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});

const HASH = "a".repeat(64);
const SEARCH = "drive/search_files";
const DELETE = "drive/delete_file";
const source = {
  kind: "request",
  field: "description",
  quote: "receipts",
} as const;
const spec: AgentSpec = {
  schemaVersion: 1,
  identity: {
    name: "Expenses",
    role: "Finance assistant",
    description: "Categorize receipts.",
  },
  goal: "Categorize the receipts people send.",
  responsibilities: [{ statement: "Categorize each receipt.", source }],
  constraints: [],
  procedure: ["Find the receipt.", "Categorize it."],
  requirements: [
    { id: "r1", need: "Find receipts.", fulfillment: "tool", source },
  ],
  resources: [SEARCH, DELETE].map((ref) => ({
    kind: "tool" as const,
    ref,
    requirementIds: ["r1"],
    fingerprint: `fingerprint-${ref}`,
    argumentSources: [],
  })),
  inputContract: {
    transport: "ag_ui_messages",
    schema: { type: "string", minLength: 1 },
    inputFacts: [],
  },
  outputContract: {
    transport: "ag_ui_messages",
    schema: { type: "string", minLength: 1 },
    expectations: ["A categorized list."],
    enforcement: "prompt_only",
  },
  acceptanceCriteria: ["Every receipt is categorized."],
  runtimeProfile: "openbot_builtin_v1",
  compilerVersion: 1,
};
const verification = {
  specHash: HASH,
  construction: "PASS" as const,
  issues: [],
  warnings: [],
  attempts: 1 as const,
  semanticReview: {
    verdict: "PASS" as const,
    modelRef: "fixture/model",
    criterionFindings: [],
  },
};
const PLUGINS = {
  catalogue: [],
  botsMayCallBack: true,
  composioConfigured: false,
  redirectUri: null,
  skills: [],
  servers: [
    {
      id: "drive",
      title: "Drive",
      tools: [
        {
          ref: SEARCH,
          name: "search_files",
          effect: "read",
          destructive: false,
        },
        {
          ref: DELETE,
          name: "delete_file",
          effect: "write",
          destructive: true,
        },
      ],
    },
  ],
};

type State = FactoryReadiness["state"];
const blocker = (code: string, index: number): FactoryIssue => ({
  code,
  path: `resources.${index}`,
  sourceStage: "access",
  evidenceRefs: [spec.resources[index]?.ref ?? ""],
  message: "Required resource has not been granted to this agent.",
});
const failure = (
  code: string,
  sourceStage: FactoryIssue["sourceStage"],
  message: string,
  path = "",
): FactoryUseCaseResult => ({
  ok: false,
  constructionId: "agent_factory_x",
  issues: [{ code, path, sourceStage, evidenceRefs: [], message }],
});

function profile(id: string, state?: State): AgentProfile {
  return {
    id,
    name: "Expenses",
    title: "Finance assistant",
    roleDescription: "Categorize receipts.",
    avatarSeed: id,
    visibility: "private",
    ownerUserId: "owner",
    systemOwned: false,
    hidden: false,
    deletedAt: null,
    endpoint: null,
    hasAuth: false,
    hasCallbackToken: false,
    ...(state ? { generated: { state, specHash: HASH } } : {}),
  };
}

function artifact(
  id: string,
  state: State,
  blockers: FactoryIssue[] = [],
  outcome: "created" | "replayed" | "read" | "rechecked" = "read",
): FactoryUseCaseResult {
  return {
    ok: true,
    outcome,
    constructionId: id,
    artifact: {
      agent: profile(id, state),
      spec,
      verification,
      readiness: { state, blockers },
    },
  };
}

/** Everything the server was asked, and the answers it will give. */
let viewer: { id: string; email: string; role: "admin" | "user" };
let constructions: { key: string; input: unknown }[];
let rechecks: { id: string; specHash: string }[];
let grants: { kind: string; ref: string; agentId: string }[];
let legacyCreates: unknown[];
let urls: string[];
let refuse: Record<string, string>;
let onCreate: (key: string, input: unknown) => Promise<FactoryUseCaseResult>;
let onRead: (id: string) => FactoryUseCaseResult;
let onRecheck: (id: string) => FactoryUseCaseResult;
/** Lose the next construction's answer after the server has acted on it. */
let dropNextConstruction: boolean;

beforeEach(() => {
  viewer = { id: "owner", email: "owner@example.test", role: "user" };
  constructions = [];
  rechecks = [];
  grants = [];
  legacyCreates = [];
  urls = [];
  refuse = {};
  onCreate = async (key) => artifact(`agent_factory_${key}`, "ready");
  onRead = (id) => artifact(id, "ready");
  onRecheck = (id) => artifact(id, "ready", [], "rechecked");
  dropNextConstruction = false;
  serve();
});

function serve() {
  const auth: Parameters<typeof createAgentRoutes>[1] = async (
    context,
    next,
  ) => {
    context.set("actor", viewer);
    await next();
  };
  const service = {
    create: async (_actor: unknown, input: unknown, key: string) => {
      constructions.push({ key, input });
      return onCreate(key, input);
    },
    read: async (_actor: unknown, id: string) => onRead(id),
    recheck: async (_actor: unknown, id: string, specHash: string) => {
      rechecks.push({ id, specHash });
      return onRecheck(id);
    },
  } as unknown as AgentFactoryService;
  const factory = createAgentFactoryRoutes(service, auth);
  const store = {
    // The roster's view: generated rows carry their persisted state even when the factory read fails.
    get: async (_actor: unknown, id: string) => {
      if (id.startsWith("legacy")) return profile(id);
      const read = onRead(id);
      return read.ok ? read.artifact.agent : profile(id, "pending_resources");
    },
    create: async (_actor: unknown, input: unknown) => {
      legacyCreates.push(input);
      return profile("legacy-new");
    },
  } as unknown as AgentProfileStore;
  const agents = createAgentRoutes(
    store,
    auth,
    false,
    undefined,
    new Set(),
    undefined,
    true,
    "http://localhost:4201/ag-ui",
  );
  globalThis.fetch = Object.assign(
    async (
      path: Parameters<typeof fetch>[0],
      init?: Parameters<typeof fetch>[1],
    ) => {
      const url = String(path);
      urls.push(`${init?.method ?? "GET"} ${url}`);
      const mounted = (prefix: string, routes: typeof agents) =>
        routes.request(
          new Request(
            `http://openbot.test${url.slice(prefix.length) || "/"}`,
            init,
          ),
        );
      if (url.startsWith("/api/agent-factory")) {
        const response = await mounted("/api/agent-factory", factory);
        if (url.endsWith("/constructions") && dropNextConstruction) {
          dropNextConstruction = false;
          throw new TypeError("Failed to fetch");
        }
        return response;
      }
      if (url.startsWith("/api/agents")) return mounted("/api/agents", agents);
      if (url === "/api/me")
        return Response.json({ user: { ...viewer, onboarding: null } });
      if (url === "/api/plugins") return Response.json(PLUGINS);
      if (url === "/api/plugins/grants") {
        const body = JSON.parse(String(init?.body));
        grants.push(body);
        return refuse[body.ref]
          ? Response.json({ error: refuse[body.ref] }, { status: 403 })
          : Response.json({ ok: true });
      }
      throw new Error(`unexpected ${url}`);
    },
    { preconnect: originalFetch.preconnect },
  );
}

function draw(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const root = createRootRoute({ component: Outlet });
  const router = createRouter({
    history: createMemoryHistory({ initialEntries: ["/"] }),
    routeTree: root.addChildren([
      createRoute({
        getParentRoute: () => root,
        path: "/",
        component: () => ui,
      }),
      createRoute({
        getParentRoute: () => root,
        path: "/channel/new",
        component: () => <p>New channel page</p>,
      }),
    ]),
  });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return {
    ...view,
    router,
    user: userEvent.setup({ document: view.baseElement.ownerDocument }),
  };
}

function drawCreate() {
  const created: string[] = [];
  const view = draw(
    <CreateAgentDialog
      onClose={() => {}}
      onCreated={(id) => created.push(id)}
      open
    />,
  );
  return { ...view, created };
}

async function fill(
  view: ReturnType<typeof draw>,
  values = {
    name: "Expenses",
    role: "Finance assistant",
    description: "Categorize receipts.",
  },
) {
  for (const [label, value] of [
    ["Name", values.name],
    ["Role", values.role],
    ["Description", values.description],
  ] as const) {
    const field = await view.findByLabelText(label);
    await view.user.clear(field);
    await view.user.type(field, value);
  }
}

const submit = (view: ReturnType<typeof draw>) =>
  view.user.click(view.getByRole("button", { name: "Create coworker" }));

function deferred<T>() {
  let resolve: (value: T) => void = () => {};
  const promise = new Promise<T>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

describe("creating", () => {
  test("C01 the default form asks exactly name, role and description, and posts only those with a key", async () => {
    const view = drawCreate();
    await view.findByText("New coworker");
    const boxes = view.getAllByRole("textbox");
    expect(boxes).toHaveLength(3);
    expect(
      boxes.map(
        (box) =>
          view.baseElement.querySelector(`label[for="${box.id}"]`)?.textContent,
      ),
    ).toEqual(["Name", "Role", "Description"]);
    for (const role of [
      "combobox",
      "checkbox",
      "radio",
      "switch",
      "spinbutton",
    ])
      expect(view.queryAllByRole(role)).toHaveLength(0);

    // Empty fields are caught before anything is sent.
    await submit(view);
    expect(view.getAllByText("Required.")).toHaveLength(3);
    expect(constructions).toHaveLength(0);

    await fill(view, {
      name: "  Expenses ",
      role: "Finance assistant",
      description: "Categorize receipts.",
    });
    await submit(view);
    await waitFor(() => expect(view.created).toHaveLength(1));
    expect(constructions).toHaveLength(1);
    expect(constructions[0]?.input).toEqual({
      name: "Expenses",
      role: "Finance assistant",
      description: "Categorize receipts.",
    });
    expect(constructions[0]?.key).toMatch(/^[0-9a-f-]{36}$/);
    // Never the legacy create.
    expect(urls.filter((url) => url.startsWith("POST /api/agents"))).toEqual(
      [],
    );
    expect(legacyCreates).toEqual([]);
  });

  test("C02 submitting shows progress, disables the form and a double click sends one request", async () => {
    const answer = deferred<FactoryUseCaseResult>();
    onCreate = () => answer.promise;
    const view = drawCreate();
    await fill(view);
    await view.user.dblClick(
      view.getByRole("button", { name: "Create coworker" }),
    );
    expect(
      (await view.findByRole("status")).textContent?.includes(
        "Building and verifying",
      ),
    ).toBe(true);
    const busy = view.getByRole("button", { name: "Creating…" });
    expect(busy.hasAttribute("disabled")).toBe(true);
    expect(view.getByLabelText("Name").hasAttribute("disabled")).toBe(true);
    await view.user.click(busy);
    expect(constructions).toHaveLength(1);
    // Nothing is reported as created until the server has answered.
    expect(view.created).toEqual([]);
    answer.resolve(artifact("agent_factory_one", "ready", [], "created"));
    await waitFor(() => expect(view.created).toEqual(["agent_factory_one"]));
    expect(constructions).toHaveLength(1);
  });

  test("C03 a 201 hands over the id, and the ready coworker offers Start, which opens a channel", async () => {
    onCreate = async () =>
      artifact("agent_factory_ready", "ready", [], "created");
    const view = drawCreate();
    await fill(view);
    await submit(view);
    await waitFor(() => expect(view.created).toEqual(["agent_factory_ready"]));
    cleanup();

    const dialog = draw(
      <AgentDialog agentId="agent_factory_ready" onClose={() => {}} open />,
    );
    expect(await dialog.findByText("Ready")).toBeTruthy();
    const start = dialog.getByRole("button", { name: "Start" });
    expect(start.hasAttribute("disabled")).toBe(false);
    expect(dialog.queryByRole("button", { name: "Approve access" })).toBeNull();
    await dialog.user.click(start);
    await waitFor(() =>
      expect(dialog.router.state.location.pathname).toBe("/channel/new"),
    );
    expect(dialog.router.state.location.search).toEqual({
      agent: "agent_factory_ready",
    });
  });

  test("C04 a 202 hands over the id, and the coworker stays visibly blocked with what it needs", async () => {
    const pending = [
      blocker("GRANT_REQUIRED", 0),
      blocker("GRANT_REQUIRED", 1),
    ];
    onCreate = async () =>
      artifact(
        "agent_factory_pending",
        "pending_resources",
        pending,
        "created",
      );
    onRead = (id) => artifact(id, "pending_resources", pending);
    const view = drawCreate();
    await fill(view);
    await submit(view);
    await waitFor(() =>
      expect(view.created).toEqual(["agent_factory_pending"]),
    );
    expect(constructions).toHaveLength(1);
    cleanup();

    const dialog = draw(
      <AgentDialog agentId="agent_factory_pending" onClose={() => {}} open />,
    );
    expect(await dialog.findByText("Waiting for access")).toBeTruthy();
    expect(
      dialog.getByRole("button", { name: "Start" }).hasAttribute("disabled"),
    ).toBe(true);
    // Exact resources, by name and effect, each with what it needs; no refs or codes.
    expect(await dialog.findByText("Search files (Drive)")).toBeTruthy();
    expect(dialog.getByText("Tool · reads")).toBeTruthy();
    expect(dialog.getByText("Tool · can delete")).toBeTruthy();
    expect(dialog.getAllByText("Needs approval")).toHaveLength(2);
    // Not an administrator: the tools are named as needing one, and nothing offers to approve them.
    expect(
      dialog.getByText("An administrator needs to approve its tools."),
    ).toBeTruthy();
    expect(dialog.queryByRole("button", { name: "Approve access" })).toBeNull();
    const text = dialog.baseElement.textContent ?? "";
    expect(text).not.toContain("GRANT_REQUIRED");
    expect(text).not.toContain("fingerprint-");
  });

  test("C05 refusals, dependency failures, timeouts and lost answers read as sentences, never internals", async () => {
    const cases: [(() => Promise<FactoryUseCaseResult>) | "drop", string][] = [
      [
        async () =>
          failure(
            "NEEDS_INPUT",
            "draft",
            "Clarification is required before compilation.",
          ),
        "The description leaves something essential open",
      ],
      [
        async () =>
          failure("INTENT_MISMATCH", "draft", "reviewer: SECRET_REVIEW_TEXT"),
        "A verified coworker could not be built",
      ],
      [
        async () =>
          failure("BLOCKED_RESOURCE", "resources", "No tool for SECRET_REF."),
        "needs a tool this deployment does not have",
      ],
      [
        async () =>
          failure(
            "DEPENDENCY_UNAVAILABLE",
            "dependency",
            "upstream said SECRET_PROVIDER_BODY",
          ),
        "Creating coworkers is unavailable right now",
      ],
      [
        async () =>
          failure(
            "DEADLINE_EXCEEDED",
            "dependency",
            "Construction deadline exceeded.",
          ),
        "Building this coworker took too long",
      ],
      ["drop", "The answer was lost on the way back"],
    ];
    for (const [answer, expected] of cases) {
      if (answer === "drop") dropNextConstruction = true;
      else onCreate = answer;
      const view = drawCreate();
      await fill(view);
      await submit(view);
      const alert = await view.findByRole("alert");
      expect(alert.textContent).toContain(expected);
      const text = view.baseElement.textContent ?? "";
      for (const internal of [
        "SECRET",
        "NEEDS_INPUT",
        "INTENT_MISMATCH",
        "BLOCKED_RESOURCE",
        "DEPENDENCY_UNAVAILABLE",
        "DEADLINE_EXCEEDED",
        "agent_factory_x",
      ])
        expect(text).not.toContain(internal);
      expect(view.created).toEqual([]);
      // Correctable: the description is still there and the form is enabled again.
      expect(view.getByLabelText("Description").hasAttribute("disabled")).toBe(
        false,
      );
      expect(
        (view.getByLabelText("Description") as HTMLTextAreaElement).value,
      ).toBe("Categorize receipts.");
      cleanup();
    }
    // A 400 names the field the server refused.
    onCreate = async () =>
      failure(
        "INVALID_SCHEMA",
        "request",
        "Invalid or unexpected field.",
        "name",
      );
    const view = drawCreate();
    await fill(view);
    await submit(view);
    expect(
      (await view.findByText("Fill this in, and keep it shorter.")).closest(
        '[data-slot="field"]',
      )?.textContent,
    ).toContain("Name");
    expect(
      view.getByText("Check the name, role and description, then try again."),
    ).toBeTruthy();
  });

  test("C06 a lost answer is retried with the same key and makes one coworker; changed input gets a new key", async () => {
    const made = new Map<string, string>();
    onCreate = async (key) => {
      if (made.has(key))
        return artifact(made.get(key) ?? "", "ready", [], "replayed");
      made.set(key, `agent_factory_${made.size}`);
      return artifact(made.get(key) ?? "", "ready", [], "created");
    };
    dropNextConstruction = true;
    const view = drawCreate();
    await fill(view);
    await submit(view);
    expect((await view.findByRole("alert")).textContent).toContain(
      "will not create a second coworker",
    );
    expect(view.created).toEqual([]);
    await submit(view);
    await waitFor(() => expect(view.created).toEqual(["agent_factory_0"]));
    expect(constructions.map(({ key }) => key)).toEqual([
      constructions[0]?.key ?? "",
      constructions[0]?.key ?? "",
    ]);
    // Duplicate submission made exactly one coworker.
    expect(made.size).toBe(1);
    cleanup();

    constructions = [];
    let calls = 0;
    onCreate = async (key) =>
      ++calls < 3
        ? failure("DEPENDENCY_UNAVAILABLE", "dependency", "down")
        : artifact(`agent_factory_${key}`, "ready", [], "created");
    const edited = drawCreate();
    await fill(edited);
    await submit(edited);
    await edited.findByRole("alert");
    await submit(edited);
    await waitFor(() => expect(constructions).toHaveLength(2));
    await edited.user.type(edited.getByLabelText("Description"), " Weekly.");
    await submit(edited);
    await waitFor(() => expect(edited.created).toHaveLength(1));
    const [first, unchanged, changed] = constructions.map(({ key }) => key);
    expect(unchanged).toBe(first ?? "");
    expect(changed).not.toBe(first ?? "");
    expect(constructions[2]?.input).toMatchObject({
      description: "Categorize receipts. Weekly.",
    });
  });
});

describe("a generated coworker", () => {
  test("C07 is read-only where a legacy coworker is editable, and cannot be copied but can be hidden or deleted", async () => {
    const generated = draw(
      <AgentDialog agentId="agent_factory_ready" onClose={() => {}} open />,
    );
    expect(await generated.findByText("Ready")).toBeTruthy();
    expect(
      generated.getByText(/Built from a verified specification/),
    ).toBeTruthy();
    for (const label of ["Edit name", "Edit title", "Edit role"])
      expect(generated.queryByRole("button", { name: label })).toBeNull();
    expect(generated.queryAllByRole("combobox")).toHaveLength(0);
    expect(generated.queryAllByRole("textbox")).toHaveLength(0);
    expect(
      generated.getByText("Categorize the receipts people send."),
    ).toBeTruthy();
    await generated.user.click(
      generated.getAllByRole("button", { name: "Manage" })[0] as HTMLElement,
    );
    expect(
      generated
        .getByRole("button", { name: "Duplicate" })
        .hasAttribute("disabled"),
    ).toBe(true);
    expect(
      generated.getByRole("button", { name: "Hide" }).hasAttribute("disabled"),
    ).toBe(false);
    expect(
      generated
        .getByRole("button", { name: "Delete" })
        .hasAttribute("disabled"),
    ).toBe(false);
    cleanup();

    urls = [];
    const legacy = draw(
      <AgentDialog agentId="legacy-one" onClose={() => {}} open />,
    );
    expect(
      await legacy.findByRole("button", { name: "Edit name" }),
    ).toBeTruthy();
    expect(
      legacy.getByRole("button", { name: "Start" }).hasAttribute("disabled"),
    ).toBe(false);
    await legacy.user.click(
      legacy.getAllByRole("button", { name: "Manage" })[0] as HTMLElement,
    );
    expect(
      legacy
        .getByRole("button", { name: "Duplicate" })
        .hasAttribute("disabled"),
    ).toBe(false);
    // A legacy coworker never asks the factory anything.
    expect(urls.some((url) => url.includes("/api/agent-factory"))).toBe(false);
  });

  test("C08 approval grants exactly the listed set, a partial refusal stays blocked and names what failed", async () => {
    viewer = { ...viewer, id: "admin", role: "admin" };
    // Readiness follows the grants the (HTTP-shaped) grant route accepted.
    onRead = (id) =>
      artifact(
        id,
        "pending_resources",
        [SEARCH, DELETE].flatMap((ref, index) =>
          grants.some((grant) => grant.ref === ref && !refuse[ref])
            ? []
            : [blocker("GRANT_REQUIRED", index)],
        ),
      );
    onRecheck = (id) => onRead(id);
    refuse = { [DELETE]: "The vendor refused this grant." };
    const view = draw(
      <AgentDialog agentId="agent_factory_pending" onClose={() => {}} open />,
    );
    await view.user.click(
      await view.findByRole("button", { name: "Approve access" }),
    );
    await waitFor(() => expect(rechecks).toHaveLength(1));
    expect(grants).toEqual([
      { kind: "mcp", ref: SEARCH, agentId: "agent_factory_pending" },
      { kind: "mcp", ref: DELETE, agentId: "agent_factory_pending" },
    ]);
    expect(rechecks).toEqual([{ id: "agent_factory_pending", specHash: HASH }]);
    expect(
      await view.findByText(
        "One item was not approved, so it is still waiting.",
      ),
    ).toBeTruthy();
    expect(
      view.getByText("Not approved: The vendor refused this grant."),
    ).toBeTruthy();
    await waitFor(() =>
      expect(view.getAllByText("Needs approval")).toHaveLength(1),
    );
    expect(view.getByText("Waiting for access")).toBeTruthy();
    expect(
      view.getByRole("button", { name: "Start" }).hasAttribute("disabled"),
    ).toBe(true);
    // A pending recheck answer is the status above, not an error.
    expect(view.baseElement.textContent).not.toContain("conflicts");
  });

  test("approving everything and rechecking makes it ready without rebuilding it", async () => {
    viewer = { ...viewer, id: "admin", role: "admin" };
    let approved = false;
    onRead = (id) =>
      approved
        ? artifact(id, "ready")
        : artifact(id, "pending_resources", [
            blocker("GRANT_REQUIRED", 0),
            blocker("GRANT_REQUIRED", 1),
          ]);
    onRecheck = (id) => {
      approved = true;
      return artifact(id, "ready", [], "rechecked");
    };
    const view = draw(
      <AgentDialog agentId="agent_factory_pending" onClose={() => {}} open />,
    );
    await view.user.click(
      await view.findByRole("button", { name: "Approve access" }),
    );
    expect(await view.findByText("Ready")).toBeTruthy();
    expect(
      view.getByRole("button", { name: "Start" }).hasAttribute("disabled"),
    ).toBe(false);
    expect(grants).toHaveLength(2);
    expect(constructions).toHaveLength(0);
  });

  test("a missing account links to the existing connection screen for its owner", async () => {
    onRead = (id) =>
      artifact(id, "pending_resources", [blocker("CONNECTION_REQUIRED", 0)]);
    const view = draw(
      <AgentDialog agentId="agent_factory_pending" onClose={() => {}} open />,
    );
    expect(await view.findByText("Connect your account")).toBeTruthy();
    // Base UI's Button keeps role="button" on the anchor it renders, as "New agent" does.
    expect(
      view
        .getByRole("button", { name: "Connect accounts" })
        .getAttribute("href"),
    ).toBe("/settings/connected-accounts");
    expect(view.queryByRole("button", { name: "Approve access" })).toBeNull();
  });
});

describe("the conversation sidebar", () => {
  test("Start new channel waits for a fresh ready assessment and stays available for legacy coworkers", async () => {
    const start = (view: ReturnType<typeof draw>) =>
      view.findByRole("button", { name: "Start new channel" });
    for (const [id, read, enabled] of [
      [
        "agent_factory_pending",
        (agentId: string) =>
          artifact(agentId, "pending_resources", [
            blocker("GRANT_REQUIRED", 0),
          ]),
        false,
      ],
      [
        "agent_factory_ready",
        (agentId: string) => artifact(agentId, "ready"),
        true,
      ],
      [
        "agent_factory_unreadable",
        () => failure("STORAGE_FAILURE", "dependency", "down"),
        false,
      ],
    ] as const) {
      onRead = read;
      const view = draw(<AgentProfileCard agentId={id} />);
      await waitFor(async () =>
        expect((await start(view)).hasAttribute("disabled")).toBe(!enabled),
      );
      await waitFor(() =>
        expect(
          urls.some((url) => url.startsWith("GET /api/agent-factory/")),
        ).toBe(true),
      );
      expect((await start(view)).hasAttribute("disabled")).toBe(!enabled);
      if (!enabled) expect(view.getByText(/It cannot start yet/)).toBeTruthy();
      expect(
        view.getByRole("button", { name: "Manage coworker" }),
      ).toBeTruthy();
      cleanup();
      urls = [];
    }

    const legacy = draw(<AgentProfileCard agentId="legacy-one" />);
    expect((await start(legacy)).hasAttribute("disabled")).toBe(false);
    expect(urls.some((url) => url.includes("/api/agent-factory"))).toBe(false);
  });
});

describe("the legacy path", () => {
  test("Connect an existing agent is the unchanged wizard posting to /api/agents", async () => {
    const view = drawCreate();
    await view.user.click(
      await view.findByRole("button", { name: "Connect an existing agent" }),
    );
    expect(await view.findByText("Who is this coworker?")).toBeTruthy();
    await view.user.type(view.getByLabelText("Name"), "Legacy");
    await view.user.type(view.getByLabelText("Title"), "Ops");
    await view.user.type(view.getByLabelText("Role"), "Answer questions.");
    await view.user.click(view.getByRole("button", { name: "Continue" }));
    expect(await view.findByText("Who can see it?")).toBeTruthy();
    await view.user.click(view.getByRole("button", { name: "Continue" }));
    expect(await view.findByText("Where does it run?")).toBeTruthy();
    await view.user.click(view.getByRole("radio", { name: /Built-in/ }));
    await view.user.click(
      view.getByRole("button", { name: "Create coworker" }),
    );
    await waitFor(() => expect(view.created).toEqual(["legacy-new"]));
    expect(legacyCreates).toEqual([
      expect.objectContaining({
        name: "Legacy",
        title: "Ops",
        roleDescription: "Answer questions.",
        visibility: "private",
      }),
    ]);
    expect(constructions).toEqual([]);
  });
});
