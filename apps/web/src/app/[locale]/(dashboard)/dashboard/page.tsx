import { ConversationsRail } from "@/components/dashboard/conversations-rail";
import { DashboardHomeHero } from "@/components/dashboard/home-hero";
import { requireUser } from "@/lib/session";

export default async function OverviewPage() {
  const user = await requireUser();

  return (
    // The conversations rail is fixed-positioned and overlays content on
    // hover (same chrome as the main sidebar). To keep the collapsed 5rem
    // out of the content area, the wrapper reserves inline-end padding on
    // lg+. The rail renders as a sibling so it sits over the gap.
    //
    // Email-verify and phone-reminder banners used to sit above the hero
    // here — they were intrusive every-load nags on the only page the
    // user spends time on. The settings page still surfaces both, and an
    // unverified email or missing phone doesn't block any feature today,
    // so reminding from the home doesn't earn its space.
    <>
      <div className="lg:pe-20 transition-[padding] duration-300">
        <div className="container max-w-6xl py-6 sm:py-8 space-y-6">
          {/* The hero now owns its own quick-action tiles (expanded in
              empty state, compact pills above the chat in conversation
              mode), so QuickActions isn't rendered here directly. */}
          <DashboardHomeHero userName={user.full_name} />
        </div>
      </div>

      {/* Conversations history — sits on the inline-end side, which is
          the visual left in Arabic (RTL). Icon-only at rest, expands on
          hover. The component handles its own fetching, URL syncing via
          `?c=`, and active-row highlight. */}
      <ConversationsRail />
    </>
  );
}
