/**
 * Where people sign in: one page for residents and staff, served by the resident app at /login.
 * In a deployment it is on the same host; in development it is the resident dev server beside this one,
 * or VITE_LOGIN_URL when that is set.
 */
export function loginUrl(): string {
  const configured = import.meta.env.VITE_LOGIN_URL;
  if (configured) return configured;
  const here = new URL(location.href);
  if (["localhost", "127.0.0.1", "[::1]"].includes(here.hostname) && here.port === "3020") here.port = "3011";
  here.pathname = "/login";
  here.search = "";
  here.hash = "";
  return here.toString();
}
