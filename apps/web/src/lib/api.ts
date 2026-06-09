/**
 * Thin fetch wrapper around the FastAPI backend.
 *
 * Uses the Next.js rewrite at /api/v1 → backend so we never expose the API
 * URL to the browser directly. On the server side, calls go straight to
 * `process.env.API_BASE_URL` for lower latency.
 */
const isServer = typeof window === "undefined";

// Server-side base URL for the FastAPI backend. `API_BASE_URL` overrides it
// (set in .env.local for local dev). The default points at the deployed
// Hugging Face backend so a host with no env config (e.g. Hostinger) still
// reaches it out of the box.
const SERVER_BASE =
  process.env.API_BASE_URL ||
  "https://abdulmalik1113456789-ai-law-backend.hf.space";
const CLIENT_BASE = "/api"; // proxied via next.config rewrites

export class ApiError extends Error {
  constructor(public status: number, public body: unknown, message: string) {
    super(message);
  }
}

export interface ApiOptions extends RequestInit {
  token?: string | null;
  json?: unknown;
}

export async function api<T = unknown>(
  path: string,
  opts: ApiOptions = {}
): Promise<T> {
  const base = isServer ? SERVER_BASE : CLIENT_BASE;
  const url = `${base}${path.startsWith("/") ? "" : "/"}${path}`;

  const headers = new Headers(opts.headers);
  if (opts.json !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (opts.token) {
    headers.set("Authorization", `Bearer ${opts.token}`);
  }

  const init: RequestInit = {
    ...opts,
    headers,
    body:
      opts.json !== undefined
        ? JSON.stringify(opts.json)
        : (opts.body as BodyInit | null | undefined),
    cache: "no-store",
  };

  const res = await fetch(url, init);
  const text = await res.text();
  const body = text ? safeJson(text) : null;
  if (!res.ok) {
    const detail =
      (body as { detail?: string } | null)?.detail ?? res.statusText;
    throw new ApiError(res.status, body, detail);
  }
  return body as T;
}

function safeJson(text: string) {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}
