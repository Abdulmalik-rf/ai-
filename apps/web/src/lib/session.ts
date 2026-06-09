/**
 * Server-only session helpers.
 *
 * Wrapped in React's request-scoped `cache()` so the layout AND the page can
 * both call them and only pay for ONE cookie read / `/v1/auth/me` round-trip
 * per render. The auth Server Actions (`login`, `signup`, `logout`) live in
 * `./auth.ts` — they need their own module because a Server-Action file
 * cannot also export `cache()`-wrapped helpers.
 */
import "server-only";
import { cache } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { api } from "./api";

const ACCESS_COOKIE = "lai_access";

export interface MeResponse {
  id: string;
  tenant_id: string | null;
  email: string;
  full_name: string;
  role: "admin" | "lawyer" | "staff" | "super_admin";
  locale: string;
  is_email_verified: boolean;
  phone_number: string | null;
}

export const getAccessToken = cache(async (): Promise<string | null> => {
  return (await cookies()).get(ACCESS_COOKIE)?.value ?? null;
});

export const getCurrentUser = cache(async (): Promise<MeResponse | null> => {
  const token = await getAccessToken();
  if (!token) return null;
  try {
    return await api<MeResponse>("/v1/auth/me", { token });
  } catch {
    return null;
  }
});

export const requireUser = cache(async (): Promise<MeResponse> => {
  const user = await getCurrentUser();
  if (!user) {
    redirect("/sign-in");
  }
  return user;
});
