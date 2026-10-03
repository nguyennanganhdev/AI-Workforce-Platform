import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DialogBody,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemTitle,
} from "@/components/ui/item";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  constructAgentMutationOptions,
  FactoryRequestError,
  recheckFactoryMutationOptions,
} from "@/lib/agents/mutations";
import {
  type AgentProfile,
  type FactoryArtifact,
  factoryArtifactQueryOptions,
  factoryRunnable,
} from "@/lib/agents/queries";
import { currentUserQueryOptions } from "@/lib/auth/queries";
import { newId } from "@/lib/new-id";
import { grantPlugin, invalidatePlugins } from "@/lib/plugins/mutations";
import {
  type PluginsPage,
  pluginsPageQueryOptions,
} from "@/lib/plugins/queries";
import { readToolName } from "@/lib/plugins/tool-name";
import type { AgentCreationRequest } from "../../../../agent-factory/src/contracts";

type RequestField = keyof AgentCreationRequest;

const FIELDS: ReadonlyArray<{
  key: RequestField;
  label: string;
  placeholder: string;
  multiline?: true;
}> = [
  { key: "name", label: "Name", placeholder: "Expense Manager" },
  { key: "role", label: "Role", placeholder: "Finance operations assistant" },
  {
    key: "description",
    label: "Description",
    placeholder:
      "Review the receipts people send, categorize each expense, and prepare a weekly reimbursement summary.",
    multiline: true,
  },
];

/** What a refused construction means for the person, never the server's codes or diagnostics. */
function constructionFailure(error: Error): {
  message: string;
  fields: Partial<Record<RequestField, string>>;
} {
  if (!(error instanceof FactoryRequestError) || error.status === 0)
    return {
      message:
        "The answer was lost on the way back. Submitting again is safe: it will not create a second coworker.",
      fields: {},
    };
  const { status, body } = error;
  const code = body?.code;
  const fields: Partial<Record<RequestField, string>> = {};
  if (status === 400)
    for (const { path } of body?.issues ?? [])
      if (path === "name" || path === "role" || path === "description")
        fields[path] = "Fill this in, and keep it shorter.";
  const message =
    status === 400
      ? "Check the name, role and description, then try again."
      : status === 410
        ? "The coworker from this submission was deleted. Submit again to create a new one."
        : status === 422
          ? code === "NEEDS_INPUT"
            ? "The description leaves something essential open. Say more about what this coworker should do, then try again."
            : code === "BLOCKED_RESOURCE"
              ? "This job needs a tool this deployment does not have. Ask an administrator to add one, or change the description."
              : code === "UNSUPPORTED_CONTRACT"
                ? "The description asks for something a coworker here cannot guarantee, such as a strict output format. Rephrase it without that."
                : "A verified coworker could not be built from this description. Make it more specific, then try again."
          : status === 503
            ? "Creating coworkers is unavailable right now. Try again in a moment."
            : status === 504
              ? "Building this coworker took too long. Try again."
              : (body?.error ?? "The coworker could not be created.");
  return { message, fields };
}

/**
 * The default way to create a coworker: who it is and what it should do, nothing else.
 *
 * Its instructions, tools, checks and runtime are worked out and verified by the server. The form
 * waits for the answer before calling `onCreated`, so the dialog it opens shows ready or waiting
 * for access as the server decided, never an assumed success.
 */
export function CreateGeneratedAgentForm({
  onCancel,
  onCreated,
  onConnectExisting,
}: {
  onCancel: () => void;
  onCreated: (agentId: string) => void;
  /** The legacy wizard, for an agent somebody already hosts. */
  onConnectExisting: () => void;
}) {
  const queryClient = useQueryClient();
  const construct = useMutation(constructAgentMutationOptions(queryClient));
  const [values, setValues] = useState<AgentCreationRequest>({
    name: "",
    role: "",
    description: "",
  });
  const [tried, setTried] = useState(false);
  /** The key and the exact input it was issued for; any change to the input earns a new key. */
  const submission = useRef<{ key: string; input: string } | null>(null);
  /** Two clicks inside one render would both see `isPending` false. */
  const inFlight = useRef(false);

  const request: AgentCreationRequest = {
    name: values.name.trim(),
    role: values.role.trim(),
    description: values.description.trim(),
  };
  const failure = construct.error ? constructionFailure(construct.error) : null;

  const submit = async () => {
    if (inFlight.current) return;
    if (!request.name || !request.role || !request.description) {
      setTried(true);
      return;
    }
    const input = JSON.stringify(request);
    if (submission.current?.input !== input)
      submission.current = { key: newId(), input };
    inFlight.current = true;
    try {
      const { artifact } = await construct.mutateAsync({
        request,
        idempotencyKey: submission.current.key,
      });
      onCreated(artifact.agent.id);
    } catch (error) {
      // A deleted result can never be replayed under its key; the next submit builds anew.
      if (error instanceof FactoryRequestError && error.status === 410)
        submission.current = null;
    } finally {
      inFlight.current = false;
    }
  };

  return (
    <>
      <DialogHeader>
        <DialogTitle>New coworker</DialogTitle>
        <DialogDescription>
          Describe the job. Its instructions and tools are worked out and
          checked for you.
        </DialogDescription>
      </DialogHeader>
      <DialogBody>
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <FieldGroup className="pt-4">
            {FIELDS.map(({ key, label, placeholder, multiline }) => {
              const error =
                tried && !request[key] ? "Required." : failure?.fields[key];
              const control = {
                "aria-invalid": error ? true : undefined,
                disabled: construct.isPending,
                id: `generated-agent-${key}`,
                placeholder,
                value: values[key],
                onChange: (event: { target: { value: string } }) =>
                  setValues((current) => ({
                    ...current,
                    [key]: event.target.value,
                  })),
              };
              return (
                <Field data-invalid={error ? true : undefined} key={key}>
                  <FieldLabel htmlFor={control.id}>{label}</FieldLabel>
                  {multiline ? (
                    <Textarea rows={5} {...control} />
                  ) : (
                    <Input {...control} />
                  )}
                  {error ? <FieldError errors={[{ message: error }]} /> : null}
                </Field>
              );
            })}
          </FieldGroup>

          {construct.isPending ? (
            <p className="mt-4 text-sm text-muted-foreground" role="status">
              Building and verifying your coworker. This can take up to a minute
              and a half.
            </p>
          ) : failure ? (
            <p className="mt-4 text-sm text-destructive" role="alert">
              {failure.message}
            </p>
          ) : null}

          <div className="mt-6 flex flex-wrap items-center justify-between gap-2">
            <Button
              disabled={construct.isPending}
              onClick={onConnectExisting}
              type="button"
              variant="ghost"
            >
              Connect an existing agent
            </Button>
            <div className="flex gap-2">
              <Button onClick={onCancel} type="button" variant="outline">
                Cancel
              </Button>
              <Button disabled={construct.isPending} type="submit">
                {construct.isPending ? "Creating…" : "Create coworker"}
              </Button>
            </div>
          </div>
        </form>
      </DialogBody>
    </>
  );
}

type Resource = FactoryArtifact["spec"]["resources"][number];

/** Names and effects from the catalogue a signed-in person can already read; the ref otherwise. */
function describeResource(
  resource: Resource,
  plugins: PluginsPage | undefined,
) {
  if (resource.kind === "skill") {
    const skill = plugins?.skills.find(({ slug }) => slug === resource.ref);
    return { name: skill?.title ?? resource.ref, kind: "Skill" };
  }
  const [serverId = "", ...rest] = resource.ref.split("/");
  const server = plugins?.servers.find(({ id }) => id === serverId);
  const tool = server?.tools.find(({ ref }) => ref === resource.ref);
  const { label } = readToolName(`mcp__${serverId}__${rest.join("/")}`);
  return {
    name: server ? `${label} (${server.title})` : label,
    kind: !tool
      ? "Tool"
      : tool.destructive
        ? "Tool · can delete"
        : tool.effect === "write"
          ? "Tool · makes changes"
          : "Tool · reads",
  };
}

const ACTION_FOR: Record<string, string> = {
  GRANT_REQUIRED: "Needs approval",
  CONFIGURATION_REQUIRED:
    "An administrator needs to finish setting up this app",
  RESOURCE_CHANGED: "Changed since it was built",
  RESOURCE_MISSING: "No longer available",
};

/**
 * A generated coworker's General section: read-only identity, what it was built to do, the exact
 * resources it needs and what is still missing. Approval grants exactly the listed set through the
 * existing grant route and then rechecks; the server stays the authority on who may approve, and a
 * refusal leaves the coworker waiting with the refused items named.
 */
export function GeneratedAgentSetup({
  agentId,
  profile,
}: {
  agentId: string;
  profile: AgentProfile;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const artifact = useQuery(factoryArtifactQueryOptions(agentId));
  const plugins = useQuery(pluginsPageQueryOptions());
  const { data: user } = useQuery(currentUserQueryOptions());
  const recheck = useMutation(recheckFactoryMutationOptions(queryClient));
  const [approving, setApproving] = useState(false);
  const [refused, setRefused] = useState<{ ref: string; reason: string }[]>([]);

  const data = artifact.data;
  const runnable = factoryRunnable(data);
  const blockers = data?.readiness.blockers ?? [];
  const codes = new Set(blockers.map(({ code }) => code));
  const stale = codes.has("RESOURCE_CHANGED") || codes.has("RESOURCE_MISSING");
  const resources = (data?.spec.resources ?? []).map((resource, index) => ({
    resource,
    codes: blockers
      .filter(({ path }) => path === `resources.${index}`)
      .map(({ code }) => code),
  }));
  const general = blockers.filter(({ path }) => !path.startsWith("resources."));
  const needsGrant = resources.filter(({ codes }) =>
    codes.includes("GRANT_REQUIRED"),
  );
  // MCP approval is an administrator's; a person may approve their own skills. The server decides.
  const approvable = needsGrant.filter(
    ({ resource }) => user?.role === "admin" || resource.kind === "skill",
  );
  const recheckError =
    recheck.error instanceof FactoryRequestError &&
    recheck.error.body?.code === "RESOURCES_PENDING"
      ? null
      : recheck.error;

  const checkAgain = (specHash: string) =>
    recheck.mutateAsync({ agentId, specHash }).catch(() => undefined);

  /** Not atomic, and not rolled back: a grant that went through was a real decision. */
  const approve = async (specHash: string) => {
    setApproving(true);
    const failures: { ref: string; reason: string }[] = [];
    try {
      for (const { resource } of approvable) {
        try {
          await grantPlugin({
            kind: resource.kind === "tool" ? "mcp" : "skill",
            ref: resource.ref,
            agentId,
          });
        } catch (error) {
          failures.push({
            ref: resource.ref,
            reason: error instanceof Error ? error.message : "Not approved.",
          });
        }
      }
      setRefused(failures);
      await invalidatePlugins(queryClient);
      await checkAgain(specHash);
    } finally {
      setApproving(false);
    }
  };

  const status = artifact.isPending
    ? null
    : !data
      ? {
          title: "Setup could not be checked",
          description: "It cannot be started from here until it can be.",
        }
      : runnable
        ? { title: "Ready", description: "Verified and ready to start." }
        : stale
          ? {
              title: "Needs to be created again",
              description:
                "Something it was built on has changed or been removed, so it will not run. Create a new coworker from the same description.",
            }
          : data.readiness.state === "ready"
            ? {
                title: "Access is in place",
                description: "Check again to finish setting it up.",
              }
            : {
                title: "Waiting for access",
                description:
                  "It was verified, but it will not run until everything below is approved or connected.",
              };

  return (
    <>
      <div className="flex flex-col gap-2">
        {(
          [
            ["Name", profile.name],
            ["Role", profile.title],
            ["Description", profile.roleDescription],
          ] as const
        ).map(([label, value]) => (
          <Item key={label} variant="muted">
            <ItemContent>
              <ItemTitle>{label}</ItemTitle>
            </ItemContent>
            <ItemActions className="min-w-0">
              <span className="line-clamp-3 whitespace-pre-wrap text-right text-sm text-muted-foreground">
                {value}
              </span>
            </ItemActions>
          </Item>
        ))}
        <p className="text-xs text-muted-foreground">
          Built from a verified specification, so it cannot be edited. Create a
          new coworker to change it.
        </p>
      </div>

      {artifact.isPending ? (
        <div className="flex flex-col gap-2" role="status">
          <span className="sr-only">Checking its setup…</span>
          <Skeleton className="h-14 w-full" />
        </div>
      ) : status ? (
        <Item variant="muted">
          <ItemContent>
            <ItemTitle>{status.title}</ItemTitle>
            <ItemDescription
              className="line-clamp-none"
              role={data ? "status" : "alert"}
            >
              {status.description}
            </ItemDescription>
          </ItemContent>
          <ItemActions>
            <Button
              disabled={!runnable}
              onClick={() =>
                void navigate({
                  search: { agent: agentId },
                  to: "/channel/new",
                })
              }
              size="sm"
            >
              Start
            </Button>
          </ItemActions>
        </Item>
      ) : null}

      {data ? (
        <>
          <section className="grid gap-2">
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              What it does
            </h3>
            <p className="text-sm">{data.spec.goal}</p>
            <ul className="ml-4 list-disc text-sm text-muted-foreground">
              {data.spec.responsibilities.map(({ statement }) => (
                <li key={statement}>{statement}</li>
              ))}
            </ul>
          </section>

          {resources.length || general.length ? (
            <section className="grid gap-2">
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                What it needs
              </h3>
              {resources.map(({ resource, codes }) => {
                const { name, kind } = describeResource(resource, plugins.data);
                const refusal = refused.find(({ ref }) => ref === resource.ref);
                const actions = codes.map((code) =>
                  code === "CONNECTION_REQUIRED"
                    ? profile.mine
                      ? "Connect your account"
                      : "Its creator needs to connect their account"
                    : (ACTION_FOR[code] ?? "Not available yet"),
                );
                return (
                  <Item
                    key={`${resource.kind}:${resource.ref}`}
                    variant="muted"
                  >
                    <ItemContent>
                      <ItemTitle>{name}</ItemTitle>
                      <ItemDescription className="line-clamp-none">
                        {kind}
                      </ItemDescription>
                      {refusal ? (
                        <p className="text-sm text-destructive">
                          Not approved: {refusal.reason}
                        </p>
                      ) : null}
                    </ItemContent>
                    <ItemActions>
                      <span className="text-right text-sm text-muted-foreground">
                        {actions.length ? actions.join(". ") : "Available"}
                      </span>
                    </ItemActions>
                  </Item>
                );
              })}
              {general.map(({ code, message }) => (
                <p className="text-sm text-muted-foreground" key={code}>
                  {message}
                </p>
              ))}
            </section>
          ) : null}

          {!runnable && !stale ? (
            <div className="flex flex-col gap-2">
              {approvable.length ? (
                <p className="text-sm text-muted-foreground">
                  Approving grants this coworker exactly the{" "}
                  {approvable.length === 1 ? "item" : "items"} marked as needing
                  approval, and nothing else.
                </p>
              ) : null}
              {needsGrant.length > approvable.length ? (
                <p className="text-sm text-muted-foreground">
                  An administrator needs to approve its tools.
                </p>
              ) : null}
              {refused.length ? (
                <p className="text-sm text-destructive" role="alert">
                  {refused.length === 1
                    ? "One item was not approved"
                    : `${refused.length} items were not approved`}
                  , so it is still waiting.
                </p>
              ) : null}
              {recheckError ? (
                <p className="text-sm text-destructive" role="alert">
                  {recheckError.message}
                </p>
              ) : null}
              <div className="flex flex-wrap gap-2">
                {approvable.length ? (
                  <Button
                    disabled={approving || recheck.isPending}
                    onClick={() => void approve(data.verification.specHash)}
                    size="sm"
                  >
                    {approving ? "Approving…" : "Approve access"}
                  </Button>
                ) : null}
                {codes.has("CONNECTION_REQUIRED") && profile.mine ? (
                  <Button
                    render={(props) => (
                      <Link to="/settings/connected-accounts" {...props} />
                    )}
                    size="sm"
                    variant="outline"
                  >
                    Connect accounts
                  </Button>
                ) : null}
                <Button
                  disabled={approving || recheck.isPending}
                  onClick={() => void checkAgain(data.verification.specHash)}
                  size="sm"
                  variant="outline"
                >
                  {recheck.isPending && !approving
                    ? "Checking…"
                    : "Check again"}
                </Button>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </>
  );
}
