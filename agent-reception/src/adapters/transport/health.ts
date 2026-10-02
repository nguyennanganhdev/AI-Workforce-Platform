/** PH01 liveness only. PH02 owns authenticated run/read/resume routes. */
export function handleReceptionRequest(request: Request): Response {
  const url = new URL(request.url);
  if (request.method === "GET" && url.pathname === "/health") {
    return Response.json(
      { status: "ok" },
      {
        headers: { "Cache-Control": "no-store" },
      },
    );
  }
  return new Response("Not Found", { status: 404 });
}
