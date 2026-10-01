import { z } from "zod";

/**
 * Request metadata the tool host attaches after authentication (tools.md §1.2).
 *
 * None of it comes from the model. A tool's business input has no `tenant_id`, role or actor field,
 * and the input schemas are strict, so an agent that tries to supply one is refused rather than
 * believed.
 */
export const runtimeContextSchema = z.strictObject({
  tenant_id: z.uuid(),
  workspace_id: z.uuid().optional(),
  principal_id: z.string().min(1),
  /**
   * The application user this run acts for, where there is one, and the caller's business role in
   * scope. Both are what `document_acl` names principals by, so a document granted to a role or to
   * one person can be evaluated without the tool guessing.
   *
   * Optional because a scheduled run has a service principal and no user behind it, and because a
   * service principal is not a fifth user role. Absent means no role or user grant can match,
   * which refuses rather than opens.
   */
  user_id: z.string().min(1).optional(),
  role_code: z.enum(["admin", "management", "staff", "customer"]).optional(),
  source_run_id: z.uuid(),
  trace_id: z.string().min(1).max(128),
  agent_version: z.string().min(1).max(128),
  received_at: z.iso.datetime({ offset: true }),
});

export type RuntimeContext = z.infer<typeof runtimeContextSchema>;

/**
 * What a `ContextResolver` answers with: who is calling, and what they may touch.
 *
 * `received_at` is absent because the host stamps it from its own clock. `grants` is what the
 * caller may do and where, resolved server-side from the verified caller: each capability with
 * the `access_scopes` it holds over, a building, a zone, a site or the whole tenant, the way the
 * rest of the platform grants (the per-tool scoped grant of dev_TeamQuang, 17e5826). A
 * `building_id` in a tool's input only selects a resource; whether the grant reaches it is the
 * host's question.
 */
export const capabilityGrantSchema = z.strictObject({
  capability: z.string().min(1),
  scope_ids: z.array(z.uuid()),
});

export type CapabilityGrant = z.infer<typeof capabilityGrantSchema>;

export const resolvedIdentitySchema = runtimeContextSchema
  .omit({ received_at: true })
  .extend({ grants: z.array(capabilityGrantSchema) });

export type ResolvedIdentity = z.infer<typeof resolvedIdentitySchema>;

export type ToolContext = RuntimeContext & {
  /** The capabilities the caller holds anywhere. Where they hold them was settled by the host. */
  capabilities: ReadonlySet<string>;
};
