# Frontend reference

## Stack

- Next.js 14 (App Router, TypeScript, server components by default).
- `next-intl` for AR/EN with automatic RTL/LTR via `<html dir>`.
- `next-themes` for dark / light / system theme.
- Tailwind CSS + a tiny set of shadcn-style primitives (`Button`, `Card`,
  `Input`, `Badge`, `Textarea`).
- `react-markdown` + `remark-gfm` for rendering AI answers.
- `@tanstack/react-query` is included for future client-side caching;
  current pages mostly use server components + form actions.

## Route map

```
/[locale]/                                            (marketing) landing
/[locale]/pricing                                     (marketing) pricing
/[locale]/sign-in                                     (auth) login
/[locale]/sign-up                                     (auth) signup
/[locale]/dashboard                                   (dashboard) overview
/[locale]/dashboard/chat                              (dashboard) AI chat
/[locale]/dashboard/documents                         (dashboard) documents
/[locale]/dashboard/contracts                         (dashboard) contract review
/[locale]/dashboard/cases                             (dashboard) cases
/[locale]/dashboard/clients                           (dashboard) clients
/[locale]/dashboard/drafting                          (dashboard) drafting studio
/[locale]/dashboard/billing                           (dashboard) billing
/[locale]/dashboard/settings                          (dashboard) settings
/[locale]/admin                                       (admin) platform metrics
/[locale]/admin/tenants                               (admin) tenant management
/[locale]/admin/datasets                              (admin) Saudi datasets
```

`(marketing)`, `(auth)`, `(dashboard)`, `(admin)` are Next.js route groups,
so they don't add a path segment — they exist to share layouts.

The default locale is `ar` (Arabic). Visiting `/dashboard` serves Arabic;
`/en/dashboard` serves English.

## Auth flow

- `lib/auth.ts` is a server action module: `login`, `signup`, `logout`
  call the FastAPI auth endpoints and persist tokens in http-only cookies.
- `lib/api.ts` is a thin fetch wrapper used by both server and client code.
  - On the server it calls `process.env.API_BASE_URL` directly.
  - On the client it calls `/api/v1/...` which is proxied by
    `app/api/v1/[...path]/route.ts` — that proxy attaches the bearer token
    from the cookie. Browser JS never sees the token.

## RTL & i18n

- `messages/{ar,en}.json` hold all user-facing strings.
- Locale layout sets `<html dir="rtl">` for Arabic.
- Tailwind utilities use logical properties where possible: `me-` /
  `ms-` / `border-s-` / `border-e-`. Arrows in CTAs use `rtl:rotate-180`.

## Theming

- `next-themes` sets the `class="dark"` toggle on `<html>`.
- CSS variables in `src/styles/globals.css` define colors for both modes.
- Tailwind reads them via `hsl(var(--primary))` etc.

## Adding a page

1. Create `src/app/[locale]/(group)/your-page/page.tsx`.
2. If the page is a server component (default), fetch with `api(...)` +
   the access token from `getAccessToken()`.
3. If interactive, mark client components with `"use client"`.
4. Add new strings to both `messages/ar.json` and `messages/en.json`.
