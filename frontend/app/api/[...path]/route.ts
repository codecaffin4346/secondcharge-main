export const dynamic = "force-dynamic";

function backendUrl(): string {
  const configured =
    process.env.BACKEND_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "https://secondcharge-api.onrender.com";
  return configured.includes("://") ? configured : `https://${configured}`;
}

async function handler(request: Request) {
  const incoming = new URL(request.url);
  const path = incoming.pathname.replace(/^\/api\/?/, "");
  const target = new URL(`/api/${path}${incoming.search}`, backendUrl());

  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("content-length");

  const init: RequestInit = {
    method: request.method,
    headers,
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  try {
    const response = await fetch(target, init);
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown proxy error";
    return Response.json({ detail: `API proxy could not reach the backend: ${message}` }, { status: 502 });
  }
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
