import createMiddleware from "next-intl/middleware";
import { NextRequest, NextResponse } from "next/server";

import { routing } from "./i18n/routing";

const intlMiddleware = createMiddleware(routing);

const ACCESS_COOKIE = "lai_access";

/**
 * Match `/dashboard` and `/dashboard/...`, optionally prefixed by a locale
 * segment we recognise (e.g. `/en/dashboard/clients`). The auth gate runs
 * BEFORE next-intl rewrites so we can short-circuit unauthenticated visits
 * without doing any RSC rendering — much faster than letting the layout
 * spin up and then throw `redirect()` from inside a Suspense boundary.
 */
const DASHBOARD_RE = /^\/(?:(?:ar|en)\/)?dashboard(?:\/|$)/;
const ADMIN_RE = /^\/(?:(?:ar|en)\/)?admin(?:\/|$)/;

export default function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const gated = DASHBOARD_RE.test(pathname) || ADMIN_RE.test(pathname);

  if (gated && !req.cookies.get(ACCESS_COOKIE)) {
    const signIn = req.nextUrl.clone();
    signIn.pathname = "/sign-in";
    signIn.search = "";
    return NextResponse.redirect(signIn);
  }

  return intlMiddleware(req);
}

export const config = {
  // Match everything except API routes, _next internals, and static files
  matcher: ["/((?!api|_next|.*\\..*).*)"],
};
