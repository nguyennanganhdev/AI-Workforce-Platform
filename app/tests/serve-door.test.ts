import { describe, expect, test } from "bun:test";
import { businessHeaders, fieldRedirect, reachesOpenBot } from "../serve";

describe("the front door a deployment's app server stands for", () => {
  test("the server names its own door to the business API, over whatever the browser sent", () => {
    const sent = new Headers({ cookie: "vinhomes_staff_session=abc", "X-Vinhomes-Surface": "operations" });
    const forwarded = businessHeaders(sent, "field");
    expect(forwarded.get("x-vinhomes-surface")).toBe("field");
    expect(forwarded.get("cookie")).toBe("vinhomes_staff_session=abc");
  });

  test("a server with no door set forwards none, even one the browser claimed", () => {
    const forwarded = businessHeaders(new Headers({ "x-vinhomes-surface": "field" }), "");
    expect(forwarded.has("x-vinhomes-surface")).toBe(false);
  });

  test("the field door answers its own pages and sends every other page address to the work list", () => {
    for (const own of ["/operations", "/operations/login", "/operations/my-tasks"]) expect(fieldRedirect(own, "field")).toBeNull();
    for (const other of ["/", "/sign", "/settings/connected-accounts", "/operationsx"]) expect(fieldRedirect(other, "field")).toBe("/operations/my-tasks");
    // Built files are served as they are, and the other doors keep every page.
    expect(fieldRedirect("/assets/index-abc.js", "field")).toBeNull();
    expect(fieldRedirect("/favicon.ico", "field")).toBeNull();
    expect(fieldRedirect("/", "operations")).toBeNull();
    expect(fieldRedirect("/settings/connected-accounts", "")).toBeNull();
  });

  test("only the field door is cut off from OpenBot", () => {
    expect(reachesOpenBot("field")).toBe(false);
    expect(reachesOpenBot("operations")).toBe(true);
    expect(reachesOpenBot("")).toBe(true);
  });
});
