import type { ToolDependencies } from "../../technical-tools/tool";
import type { CleaningDependencies } from "../tool";

/** Reuse the existing ports and rules, changing only the specialist's workforce/domain. */
export function cleaningTechnicalDependencies(
  deps: CleaningDependencies,
): ToolDependencies {
  const isCleaningProfile = (code: string, version: number) =>
    deps.sopProfiles
      .find(code, version)
      ?.issueCodes.some((issue) => issue.startsWith("CLEAN.")) ?? false;
  return {
    ...deps,
    workOrders: {
      getTicket: (q) => deps.workOrders.getTicket(q),
      findEvidence: (q) => deps.workOrders.findEvidence(q),
      getWorkOrder: async (q) =>
        (await deps.isCleaningWorkOrder(
          q.tenantId,
          q.buildingId,
          q.workOrderId,
        ))
          ? deps.workOrders.getWorkOrder(q)
          : null,
      listWorkOrders: async (q) => {
        const orders = await deps.workOrders.listWorkOrders(q);
        const allowed = await Promise.all(
          orders.map((w) =>
            deps.isCleaningWorkOrder(q.tenantId, q.buildingId, w.workOrderId),
          ),
        );
        return orders.filter((_w, i) => allowed[i]);
      },
    },
    sop: {
      listForBuilding: async (q) => {
        const records = await deps.sop.listForBuilding(q);
        return records === null
          ? null
          : records.filter(
              (r) =>
                r.activeVersion &&
                isCleaningProfile(r.code, r.activeVersion.versionNo),
            );
      },
    },
    sopProfiles: {
      find: (code, version) =>
        isCleaningProfile(code, version)
          ? deps.sopProfiles.find(code, version)
          : undefined,
    },
    vendors: {
      findBySpecialty: async (q) =>
        (await deps.isCleaningSpecialty(q.tenantId, q.specialtyCode))
          ? deps.vendors.findBySpecialty(q)
          : [],
    },
  };
}
