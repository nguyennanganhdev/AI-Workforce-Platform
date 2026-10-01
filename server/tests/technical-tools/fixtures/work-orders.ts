import { BUILDING, id, USER } from "./world";

export const MANAGEMENT_UNIT = id("74000000", 1);

/** The technicians' operational profiles, which is how an assignment names a person. */
export const STAFF = {
  first: { id: id("75000000", 1), userId: USER.technician, code: "KT-001" },
  second: {
    id: id("75000000", 2),
    userId: USER.secondTechnician,
    code: "KT-002",
  },
  third: {
    id: id("75000000", 3),
    userId: USER.thirdTechnician,
    code: "KT-003",
  },
} as const;

export type WorkFixture = {
  key: string;
  ticketId: string;
  channelId: string;
  buildingId: string;
  title: string;
  workOrderId: string;
  assignmentId: string;
  staffId: string;
  assignmentStatus: "accepted" | "released";
  acceptedAt: Date;
  endedAt: Date | null;
  /** What this job is in the set to prove. */
  proves: string;
};

const work = (
  n: number,
  fixture: Omit<
    WorkFixture,
    "ticketId" | "channelId" | "workOrderId" | "assignmentId"
  >,
): WorkFixture => ({
  ...fixture,
  ticketId: id("53000000", n),
  channelId: `fixture-ticket-${fixture.key.toLowerCase()}`,
  workOrderId: id("54000000", n),
  assignmentId: id("55000000", n),
});

/**
 * Five jobs a technician could be recording against on 30/09/2026, each there for one thing the
 * write tools could get wrong.
 *
 * Every assignment is `accepted` or `released`, never `offered`: the database checks an offer's
 * expiry against its own clock, which is the real date, not the fixed `NOW` these tests run at.
 */
export const WORK: Record<string, WorkFixture> = {
  ac: work(1, {
    key: "WO-AC",
    buildingId: BUILDING.a1,
    title: "Điều hòa phòng khách A1-1205 chảy nước",
    staffId: STAFF.first.id,
    assignmentStatus: "accepted",
    acceptedAt: new Date("2026-09-30T07:30:00Z"),
    endedAt: null,
    proves: "the happy path: a job with a photo before and after the work",
  }),
  leak: work(2, {
    key: "WO-LEAK",
    buildingId: BUILDING.a1,
    title: "Rò nước âm tường phòng tắm A1-1205",
    staffId: STAFF.first.id,
    assignmentStatus: "accepted",
    acceptedAt: new Date("2026-09-30T07:40:00Z"),
    endedAt: null,
    proves: "a job with a photo from before the work and none from after",
  }),
  breaker: work(3, {
    key: "WO-BREAKER",
    buildingId: BUILDING.a1,
    title: "Cầu dao A1-1205 tóe lửa",
    staffId: STAFF.second.id,
    assignmentStatus: "accepted",
    acceptedAt: new Date("2026-09-30T08:00:00Z"),
    endedAt: null,
    proves:
      "a job another technician holds, with one photo still uploading when the result is sent",
  }),
  old: work(4, {
    key: "WO-OLD",
    buildingId: BUILDING.a1,
    title: "Sửa cửa sổ A1-1205 (đã chuyển người khác)",
    staffId: STAFF.first.id,
    assignmentStatus: "released",
    acceptedAt: new Date("2026-09-20T02:00:00Z"),
    endedAt: new Date("2026-09-21T02:00:00Z"),
    proves: "a technician released from a job may no longer record against it",
  }),
  b1: work(5, {
    key: "WO-B1",
    buildingId: BUILDING.b1,
    title: "Điều hòa B1-0501 chảy nước",
    staffId: STAFF.third.id,
    assignmentStatus: "accepted",
    acceptedAt: new Date("2026-09-30T07:00:00Z"),
    endedAt: null,
    proves: "a job in a building the agent was not asked about",
  }),
};

export type EvidenceFixture = {
  key: string;
  evidenceId: string;
  fileId: string;
  objectId: string;
  work: WorkFixture;
  purpose: "before" | "after";
  withdrawn: boolean;
};

const photo = (
  n: number,
  key: string,
  job: WorkFixture,
  purpose: "before" | "after",
  withdrawn = false,
): EvidenceFixture => ({
  key,
  evidenceId: id("56000000", n),
  fileId: id("57000000", n),
  objectId: id("58000000", n),
  work: job,
  purpose,
  withdrawn,
});

/** Photos registered as evidence: uploaded, scanned, verified. */
export const EVIDENCE = {
  acBefore: photo(1, "EV-AC-BEFORE", WORK.ac as WorkFixture, "before"),
  acAfter: photo(2, "EV-AC-AFTER", WORK.ac as WorkFixture, "after"),
  // Taken, then withdrawn: the wrong unit was photographed.
  acWithdrawn: photo(
    3,
    "EV-AC-WITHDRAWN",
    WORK.ac as WorkFixture,
    "after",
    true,
  ),
  leakBefore: photo(4, "EV-LEAK-BEFORE", WORK.leak as WorkFixture, "before"),
  breakerAfter: photo(
    5,
    "EV-BREAKER-AFTER",
    WORK.breaker as WorkFixture,
    "after",
  ),
  b1After: photo(6, "EV-B1-AFTER", WORK.b1 as WorkFixture, "after"),
} as const;

/**
 * A photo still uploading on the breaker job. The database will not register a file as evidence
 * until it is ready, so all an agent can hold is the upload's id, and that is what it sends.
 */
export const STAGED_UPLOAD = {
  fileId: id("57000000", 99),
  work: WORK.breaker as WorkFixture,
};
