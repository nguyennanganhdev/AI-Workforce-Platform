import type { AuthService } from "./guards";

/** The business service owns the password/session. OpenBot verifies it on every request. */
export function businessAuthority(value: string): string {
  const url = new URL(value);
  if (url.username || url.password || url.search || url.hash || url.pathname !== "/" ||
    (url.protocol !== "https:" && !(url.protocol === "http:" && ["api", "localhost", "127.0.0.1", "[::1]"].includes(url.hostname)))) {
    throw new Error("OPENBOT_BUSINESS_AUTH_URL requires an HTTPS origin or the private api/loopback HTTP origin");
  }
  return url.origin;
}

export function createBusinessAuth(base: string, origins: string[], request = fetch): AuthService {
  const authority = businessAuthority(base);
  const cookie = (headers: Headers) => headers.get("cookie")?.split(";")
    .map((part) => part.trim()).find((part) => /^vinhomes_session=[A-Za-z0-9_-]{32,128}$/.test(part));
  const getSession: AuthService["api"]["getSession"] = async ({ headers }) => {
    const sessionCookie = cookie(headers);
    if (!sessionCookie) return null;
    const response = await request(`${authority}/auth/session`, { headers: { cookie: sessionCookie },
      redirect: "error", signal: AbortSignal.timeout(5000) });
    if ([401, 403].includes(response.status)) return null;
    if (!response.ok) throw new Error("Business authentication is unavailable");
    const body = await response.json() as { user?: { id?: unknown; email?: unknown; name?: unknown }; membershipStatus?: string };
    if (body.membershipStatus !== "active") return null;
    if (typeof body.user?.id !== "string" || !body.user.id || typeof body.user.email !== "string")
      throw new Error("Business authentication returned an invalid identity");
    return { user: { id: body.user.id, email: body.user.email,
      name: typeof body.user.name === "string" ? body.user.name : null } };
  };
  return { api: { getSession }, async handler(incoming) {
    const path = new URL(incoming.url).pathname;
    if (incoming.method === "GET" && path === "/api/auth/get-session")
      return Response.json(await getSession({ headers: incoming.headers }), { headers: { "cache-control": "no-store" } });
    if (incoming.method === "POST" && path === "/api/auth/sign-out") {
      const origin = incoming.headers.get("origin");
      if (!origin || !origins.includes(origin)) return Response.json({ error: "Origin refused" }, { status: 403 });
      const response = await request(`${authority}/auth/logout`, { method: "POST", headers: {
        origin, cookie: cookie(incoming.headers) ?? "" }, redirect: "error", signal: AbortSignal.timeout(5000) });
      const answer = new Headers({ "cache-control": "no-store" });
      for (const value of response.headers.getSetCookie()) answer.append("set-cookie", value);
      return Response.json({ success: response.ok }, { status: response.status, headers: answer });
    }
    return Response.json({ error: "Use the Operations sign-in page" }, { status: 404 });
  } };
}
