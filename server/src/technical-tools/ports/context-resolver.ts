import type { AuditInitiator } from "../../audit";
import type { ResolvedIdentity } from "../contracts/context";

/** Who the signed agent callback proved is calling: the fields `DeploymentToolCaller` is handed. */
export type ToolCaller = {
  botId: string;
  actorId: string;
  initiator?: AuditInitiator;
};

/**
 * Turns a verified caller into a tenant, a run and a grant.
 *
 * The production implementation belongs to the runtime gateway (task C06): it reads the run's
 * binding, the principal's scoped roles and the agent release's tool grants. `null` means the
 * caller maps to no identity this deployment recognises, and the host refuses without touching any
 * data.
 */
export type ContextResolver = (
  caller: ToolCaller,
) => Promise<ResolvedIdentity | null>;
