/** A technician's assignment to a work order, with who the technician is as a user. */
export type AssignmentRecord = {
  assignmentId: string;
  /** `work_assignments.status`: offered, accepted, rejected, released, completed or cancelled. */
  status: string;
  /** `users.id` of the technician, through `staff_profiles`. */
  staffUserId: string;
  acceptedAt: Date | null;
};

/**
 * A work order as the write tools need it: which ticket it belongs to, and who is working on it.
 *
 * Only returned for a work order whose ticket is in the building asked about. A work order in
 * another building and one that does not exist are the same answer to the caller, so neither
 * confirms the other's existence.
 */
export type WorkOrderContext = {
  workOrderId: string;
  ticketId: string;
  buildingId: string;
  status: string;
  assignments: AssignmentRecord[];
};

/**
 * What an id offered as evidence turned out to be.
 *
 * `file` is an upload that exists but was never registered as evidence, which is what an agent
 * holds while a photo is still uploading. The database will not let a file become evidence until it
 * is ready, so such an id is told apart here rather than being reported as unknown.
 */
export type EvidenceLookup =
  | {
      kind: "evidence";
      id: string;
      ticketId: string;
      workOrderId: string | null;
      assignmentId: string | null;
      purpose: string;
      status: string;
      fileStatus: string;
    }
  | { kind: "file"; id: string; ticketId: string | null; fileStatus: string };
