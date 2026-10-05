import { expect, test } from "bun:test";
import { parseAgentCreationRequest } from "../src/spec";

test("Factory accepts the same name, role and description bounds as management's API", () => {
  const request = { name: "N".repeat(160), role: "R".repeat(500), description: "D".repeat(2000) };
  expect(parseAgentCreationRequest(request).ok).toBe(true);
  for (const field of ["name", "role", "description"] as const) {
    expect(parseAgentCreationRequest({ ...request, [field]: request[field] + "x" }).ok).toBe(false);
  }
});
