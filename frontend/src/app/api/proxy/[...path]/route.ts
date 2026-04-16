/**
 * Proxy generico: repassa requests client-side pro backend Railway.
 *
 * O browser chama /api/proxy/kb/docs (mesmo dominio, cookie enviado).
 * Este handler valida a sessao server-side via Better Auth e faz
 * fetch pro backend com o service token + headers de usuario.
 *
 * Resolve o problema de cross-origin: cookie Better Auth so e
 * enviado pro dominio do frontend, nao pro Railway.
 */
import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { headers } from "next/headers";

const BACKEND_URL =
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";
const SERVICE_TOKEN = process.env.INTERNAL_SERVICE_TOKEN || "";

async function proxyRequest(
  request: NextRequest,
  params: { path: string[] },
) {
  // Valida sessao Better Auth
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) {
    return NextResponse.json(
      { detail: "Not authenticated" },
      { status: 401 },
    );
  }

  const path = params.path.join("/");
  const url = new URL(`/api/${path}`, BACKEND_URL);

  // Preserva query string
  request.nextUrl.searchParams.forEach((value, key) => {
    url.searchParams.set(key, value);
  });

  const baseHeaders: Record<string, string> = {
    Authorization: `Bearer ${SERVICE_TOKEN}`,
    "X-User-Id": session.user.id,
    "X-User-Email": session.user.email,
  };

  const contentType = request.headers.get("content-type") || "";
  let body: BodyInit | undefined;

  if (request.method !== "GET" && request.method !== "HEAD") {
    if (contentType.includes("multipart/form-data")) {
      // File upload — re-stream the formData; don't set Content-Type
      // so fetch generates the boundary automatically.
      body = await request.formData();
    } else {
      baseHeaders["Content-Type"] = contentType || "application/json";
      body = await request.text();
    }
  }

  // For multipart, omit Content-Type so fetch sets boundary
  const fetchHeaders = contentType.includes("multipart/form-data")
    ? {
        Authorization: baseHeaders.Authorization,
        "X-User-Id": baseHeaders["X-User-Id"],
        "X-User-Email": baseHeaders["X-User-Email"],
      }
    : baseHeaders;

  try {
    const backendRes = await fetch(url.toString(), {
      method: request.method,
      headers: fetchHeaders,
      body,
    });

    // Stream binary responses (file downloads) as-is
    const resContentType =
      backendRes.headers.get("Content-Type") || "application/json";

    const responseBody = await backendRes.arrayBuffer();

    const resHeaders: Record<string, string> = {
      "Content-Type": resContentType,
    };
    // Forward Content-Disposition for downloads
    const disposition = backendRes.headers.get("Content-Disposition");
    if (disposition) {
      resHeaders["Content-Disposition"] = disposition;
    }

    return new NextResponse(responseBody, {
      status: backendRes.status,
      headers: resHeaders,
    });
  } catch (error) {
    console.error("[PROXY] Backend request failed:", error);
    return NextResponse.json(
      { detail: "Backend unavailable" },
      { status: 502 },
    );
  }
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, await context.params);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, await context.params);
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, await context.params);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, await context.params);
}
