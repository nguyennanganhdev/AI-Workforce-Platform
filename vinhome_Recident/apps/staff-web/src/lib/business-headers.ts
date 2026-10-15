/** The local demo backend picks its seeded actor from this header; a real backend ignores it. */
export function businessHeaders(): Record<string, string> {
  return import.meta.env.VITE_ALLOW_DEMO_BACKEND === "true"
    ? { "X-Demo-Actor": sessionStorage.getItem("operations.local-actor") || "management" }
    : {};
}
