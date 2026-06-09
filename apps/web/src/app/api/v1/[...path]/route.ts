/**
 * Catch-all proxy from /api/v1/* → backend, attaching the access token from
 * the http-only cookie. This way client components can call the backend
 * without ever seeing the bearer token in JS.
 *
 * Auto-refresh: when the upstream returns 401, we try to mint a new access
 * token with the long-lived refresh cookie, swap it in, and replay the
 * request once before giving up. This stops the 60-min access TTL from
 * surfacing as random "missing bearer" errors mid-session.
 */
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BACKEND =
  process.env.API_BASE_URL ||
  "https://abdulmalik1113456789-ai-law-backend.hf.space";

export const dynamic = "force-dynamic";

interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

async function tryRefresh(
  refreshToken: string
): Promise<TokenPair | null> {
  try {
    const r = await fetch(`${BACKEND}/v1/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${refreshToken}`,
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
    if (!r.ok) return null;
    return (await r.json()) as TokenPair;
  } catch {
    return null;
  }
}

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const url = new URL(req.url);
  const target = `${BACKEND}/v1/${path.join("/")}${url.search}`;

  const jar = await cookies();
  let access = jar.get("lai_access")?.value;
  const refresh = jar.get("lai_refresh")?.value;

  // Buffer the body once — we may replay the request after a 401.
  const bodyBuf =
    req.method === "GET" || req.method === "HEAD"
      ? undefined
      : await req.arrayBuffer();

  const buildInit = (bearer: string | undefined): RequestInit => {
    const headers = new Headers(req.headers);
    headers.delete("host");
    headers.delete("connection");
    headers.delete("content-length");
    if (bearer) headers.set("Authorization", `Bearer ${bearer}`);
    else headers.delete("Authorization");
    return {
      method: req.method,
      headers,
      body: bodyBuf,
      redirect: "manual",
      cache: "no-store",
    };
  };

  let upstream = await fetch(target, buildInit(access));
  let refreshed: TokenPair | null = null;

  if (upstream.status === 401 && refresh) {
    refreshed = await tryRefresh(refresh);
    if (refreshed) {
      upstream = await fetch(target, buildInit(refreshed.access_token));
    }
  }

  const respHeaders = new Headers(upstream.headers);
  respHeaders.delete("transfer-encoding");

  const res = new NextResponse(upstream.body, {
    status: upstream.status,
    headers: respHeaders,
  });

  // Persist the rotated tokens onto the response so the user's session
  // recovers transparently for future calls.
  if (refreshed) {
    res.cookies.set("lai_access", refreshed.access_token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: refreshed.expires_in,
    });
    res.cookies.set("lai_refresh", refreshed.refresh_token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24 * 14,
    });
  }

  return res;
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
};
