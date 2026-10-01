import { describe, expect, test } from "bun:test";
import {
  describeTechnicalTools,
  responseEnvelopeSchema,
} from "../../src/technical-tools";
import {
  apartmentEntryInputSchema,
  apartmentEntryOutputSchema,
  vendorDispatchInputSchema,
  vendorDispatchOutputSchema,
} from "../../src/technical-tools/contracts/entry-vendor";
import entryGolden from "./golden/apartment_entry.request.json";
import vendorGolden from "./golden/vendor_dispatch.request.json";

/**
 * Whether the last two tools accept and return the shapes docs/teams/quang/tools.md §6.3 and
 * §6.4 specify, and what those shapes leave no room for: a code to open a door, a cost, a booking,
 * a chosen vendor, or any status but PENDING_APPROVAL.
 */
describe("the specification's own examples", () => {
  test.each([
    [
      "apartment_entry.request",
      apartmentEntryInputSchema,
      apartmentEntryOutputSchema,
      entryGolden,
    ],
    [
      "vendor_dispatch.request",
      vendorDispatchInputSchema,
      vendorDispatchOutputSchema,
      vendorGolden,
    ],
  ] as const)("%s", (_name, input, output, golden) => {
    expect(input.safeParse(golden.request).success).toBe(true);
    expect(responseEnvelopeSchema.safeParse(golden.response).success).toBe(
      true,
    );
    expect(output.safeParse(golden.response.data).success).toBe(true);
  });
});

describe("the JSON Schema a caller is handed", () => {
  const required = (name: string) => [
    ...((
      describeTechnicalTools().find((tool) => tool.name === name)
        ?.input_schema as { required?: string[] } | undefined
    )?.required ?? []),
  ];

  test("apartment_entry.request requires what tools.md §6.3 requires", () => {
    expect(required("apartment_entry.request").sort()).toEqual(
      [
        "building_id",
        "incident_id",
        "unit_id",
        "reason",
        "contact_attempts",
        "idempotency_key",
      ].sort(),
    );
  });

  test("vendor_dispatch.request requires what tools.md §6.4 requires", () => {
    expect(required("vendor_dispatch.request").sort()).toEqual(
      [
        "building_id",
        "incident_id",
        "service",
        "reason",
        "urgency",
        "idempotency_key",
      ].sort(),
    );
  });
});

const entry = entryGolden.request;
const dispatch = vendorGolden.request;

describe("what an entry request has no room for", () => {
  test.each([
    { door_code: "4821" },
    { access_code: "4821" },
    { lock_password: "x" },
    { status: "approved" },
    { required_approvals: ["none"] },
  ])("%o", (extra) => {
    expect(
      apartmentEntryInputSchema.safeParse({ ...entry, ...extra }).success,
    ).toBe(false);
  });

  test("an attempt carries how, when, outcome and a reference: not what was said", () => {
    const [first] = entry.contact_attempts;
    expect(
      apartmentEntryInputSchema.safeParse({
        ...entry,
        contact_attempts: [{ ...first, message_body: "Mã cửa 4821" }],
      }).success,
    ).toBe(false);
  });

  test("at least one attempt, with a known channel and outcome", () => {
    expect(
      apartmentEntryInputSchema.safeParse({ ...entry, contact_attempts: [] })
        .success,
    ).toBe(false);
    const [first] = entry.contact_attempts;
    expect(
      apartmentEntryInputSchema.safeParse({
        ...entry,
        contact_attempts: [{ ...first, outcome: "probably_away" }],
      }).success,
    ).toBe(false);
  });

  test("a window that ends after it starts", () => {
    const parsed = apartmentEntryInputSchema.safeParse({
      ...entry,
      requested_window: {
        from: "2026-09-30T12:00:00Z",
        to: "2026-09-30T10:00:00Z",
      },
    });
    expect(parsed.error?.issues[0]?.path).toEqual(["requested_window", "to"]);
  });

  test("the answer names at least one approver, and is only ever pending", () => {
    expect(
      apartmentEntryOutputSchema.safeParse({
        ...entryGolden.response.data,
        required_approvals: [],
      }).success,
    ).toBe(false);
    expect(
      apartmentEntryOutputSchema.safeParse({
        ...entryGolden.response.data,
        approval_status: "APPROVED",
      }).success,
    ).toBe(false);
  });
});

describe("what a dispatch request has no room for", () => {
  test.each([
    { budget: 5000000 },
    { approved_cost: 5000000 },
    { booking_time: "2026-09-30T14:00:00Z" },
    { vendor_id: "VEN-21" },
    { priority: "critical" },
  ])("%o", (extra) => {
    expect(
      vendorDispatchInputSchema.safeParse({ ...dispatch, ...extra }).success,
    ).toBe(false);
  });

  test("urgency is routine, soon or immediate", () => {
    expect(
      vendorDispatchInputSchema.safeParse({ ...dispatch, urgency: "asap" })
        .success,
    ).toBe(false);
  });

  test("a candidate is an id, a name and a qualification, and nothing more", () => {
    const [candidate] = vendorGolden.response.data.eligible_vendors;
    expect(
      vendorDispatchOutputSchema.safeParse({
        ...vendorGolden.response.data,
        eligible_vendors: [{ ...candidate, contact_phone: "+84912345021" }],
      }).success,
    ).toBe(false);
    expect(
      vendorDispatchOutputSchema.safeParse({
        ...vendorGolden.response.data,
        eligible_vendors: [{ ...candidate, qualification_status: "booked" }],
      }).success,
    ).toBe(false);
  });
});
