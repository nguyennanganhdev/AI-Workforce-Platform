import type { ToolContext } from "../contracts/context";
import type { ExecutorResult } from "../domain/executor-result";
import type { SopBasis, Verification } from "../domain/verification";
import type { WorkOrderContext } from "../domain/work-order";
import type { ToolDependencies } from "../tool";
import type { AclSubject } from "./sop-rules";
import { verify } from "./verification-rules";

/** Who is asking, as `document_acl` names principals. */
export function aclSubjectOf(context: ToolContext): AclSubject {
  return {
    ...(context.role_code ? { roleCode: context.role_code } : {}),
    ...(context.user_id ? { userId: context.user_id } : {}),
    ...(context.workspace_id ? { workspaceId: context.workspace_id } : {}),
  };
}

/**
 * Verifies a result against what the records say now.
 *
 * Shared by `technical.verify_resolution` and `maintenance_history.append`, so the decision to
 * record a repair in an asset's history is the same decision that recommends accepting it, made the
 * same way at the moment of writing, and never one an agent reports on the other's behalf.
 */
export async function verifyFromSources(
  context: ToolContext,
  { workOrders, measurements }: ToolDependencies,
  {
    workOrder,
    result,
    sops,
  }: { workOrder: WorkOrderContext; result: ExecutorResult; sops: SopBasis[] },
): Promise<Verification> {
  const [evidence, cited] = await Promise.all([
    result.evidenceIds.length > 0
      ? workOrders.findEvidence({
          tenantId: context.tenant_id,
          ids: [...result.evidenceIds],
        })
      : Promise.resolve([]),
    result.measurementIds.length > 0
      ? measurements.findByIds(context.tenant_id, [...result.measurementIds])
      : Promise.resolve([]),
  ]);
  const assignment = workOrder.assignments.find(
    (candidate) => candidate.assignmentId === result.assignmentId,
  );

  return verify({
    result,
    evidence,
    measurements: cited,
    ticketId: workOrder.ticketId,
    assignmentAcceptedAt: assignment?.acceptedAt ?? null,
    sops,
  });
}

/** A verification as the tool contracts report it. */
export function checksOutput(verification: Verification) {
  return verification.checks.map((item) => ({
    criterion: item.criterion,
    status: item.status,
    source_refs: [...item.sourceRefs],
  }));
}
