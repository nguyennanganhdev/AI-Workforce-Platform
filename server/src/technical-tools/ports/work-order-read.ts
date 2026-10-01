import type {
  EvidenceLookup,
  TicketRecord,
  WorkOrderContext,
} from "../domain/work-order";

export type WorkOrderReadPort = {
  /**
   * The work order, if its ticket is in this building of this tenant.
   *
   * `null` otherwise, whether it belongs somewhere else or nowhere: the caller answers both the
   * same way, so neither can be used to learn that the other exists.
   */
  getWorkOrder(query: {
    tenantId: string;
    buildingId: string;
    workOrderId: string;
  }): Promise<WorkOrderContext | null>;

  /**
   * The ticket, if it is in this building of this tenant; `null` otherwise, for the same reason.
   */
  getTicket(query: {
    tenantId: string;
    buildingId: string;
    ticketId: string;
  }): Promise<TicketRecord | null>;

  /** Every work order raised for the ticket, each as `getWorkOrder` reports it. */
  listWorkOrders(query: {
    tenantId: string;
    buildingId: string;
    ticketId: string;
  }): Promise<WorkOrderContext[]>;

  /**
   * What each id is: registered evidence, an upload that is not evidence yet, or nothing.
   *
   * Ids the tenant has no record of are simply absent from the answer. The caller reports them as
   * unknown without learning whether they exist in another tenant.
   */
  findEvidence(query: {
    tenantId: string;
    ids: readonly string[];
  }): Promise<EvidenceLookup[]>;
};
