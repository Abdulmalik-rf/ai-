/**
 * Auth server actions — login, signup, logout.
 *
 * Read helpers (`getAccessToken`, `getCurrentUser`, `requireUser`) live in
 * `./session.ts` because they need React's `cache()` (which isn't allowed in
 * a Server Action module) and `server-only` (which isn't allowed in a module
 * imported by Client Components like the sidebar's logout form).
 */
"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ApiError, api } from "./api";

const ACCESS_COOKIE = "lai_access";
const REFRESH_COOKIE = "lai_refresh";

interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

/** Shape returned by `login`/`signup` to be consumed via `useActionState`. */
export interface AuthFormState {
  error: string | null;
}

/**
 * Returns a stable error CODE the client can translate via `useTranslations`.
 * Keeping the action locale-agnostic means the same server response works
 * for Arabic and English users without duplicating strings server-side.
 *
 * Codes: `wrong_credentials`, `email_taken`, `validation`, `unknown`,
 * `network`. Anything beginning with `raw:` is a fallback that the client
 * should render verbatim (used for unexpected API errors).
 */
function friendlyAuthError(err: unknown, kind: "login" | "signup"): string {
  if (err instanceof ApiError) {
    const body = err.body as { detail?: unknown } | null;
    if (Array.isArray(body?.detail) && body.detail.length > 0) {
      return "validation";
    }
    if (kind === "login" && err.status === 401) return "wrong_credentials";
    if (kind === "signup" && err.status === 409) return "email_taken";
    return `raw:${err.message || "unknown"}`;
  }
  return "network";
}

export async function login(
  _prevState: AuthFormState,
  formData: FormData
): Promise<AuthFormState> {
  const email = formData.get("email") as string;
  const password = formData.get("password") as string;
  let tokens: TokenPair;
  try {
    tokens = await api<TokenPair>("/v1/auth/login", {
      method: "POST",
      json: { email, password },
    });
  } catch (err) {
    return { error: friendlyAuthError(err, "login") };
  }
  await persistTokens(tokens);
  // redirect() throws NEXT_REDIRECT — it must run OUTSIDE the try/catch.
  redirect("/dashboard");
}

export async function signup(
  _prevState: AuthFormState,
  formData: FormData
): Promise<AuthFormState> {
  let tokens: TokenPair;
  try {
    tokens = await api<TokenPair>("/v1/auth/signup", {
      method: "POST",
      json: {
        firm_name: formData.get("firm_name"),
        full_name: formData.get("full_name"),
        email: formData.get("email"),
        password: formData.get("password"),
        locale: formData.get("locale") || "ar",
      },
    });
  } catch (err) {
    return { error: friendlyAuthError(err, "signup") };
  }
  await persistTokens(tokens);
  redirect("/dashboard");
}

export async function logout() {
  const jar = await cookies();
  jar.delete(ACCESS_COOKIE);
  jar.delete(REFRESH_COOKIE);
  redirect("/");
}

async function persistTokens(tokens: TokenPair) {
  const jar = await cookies();
  jar.set(ACCESS_COOKIE, tokens.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: tokens.expires_in,
  });
  jar.set(REFRESH_COOKIE, tokens.refresh_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 14,
  });
}
