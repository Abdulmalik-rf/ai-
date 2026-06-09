/**
 * Legacy redirect — the standalone "Ask Assistant" page used to live at
 * `/dashboard/chat`. We removed it once the conversation moved inline on
 * the dashboard home. This stub keeps old bookmarks and stale browser tabs
 * working: anyone landing here is bounced straight to `/dashboard`, where
 * the same chat experience now runs.
 *
 * The locale prefix is preserved by `next-intl`'s middleware on the
 * redirect target — `redirect("/dashboard")` lands on `/ar/dashboard` or
 * `/en/dashboard` depending on the user's current locale.
 */
import { redirect } from "@/i18n/routing";
import { getLocale } from "next-intl/server";

export default async function LegacyChatRedirect() {
  const locale = await getLocale();
  redirect({ href: "/dashboard", locale });
}
