import { Suspense } from "react";

import { DashboardSidebar } from "@/components/dashboard/sidebar";
import { DashboardTopbar } from "@/components/dashboard/topbar";
import { requireUser } from "@/lib/session";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // The sidebar is static and ships immediately. The topbar streams in once
  // /v1/auth/me resolves; the main content streams independently. The user
  // sees the chrome in ~tens of ms instead of waiting on the API.
  return (
    <div className="min-h-screen bg-background">
      <DashboardSidebar />
      <div className="md:ms-20 flex flex-col min-h-screen">
        <Suspense fallback={<TopbarShell />}>
          <TopbarWithUser />
        </Suspense>
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}

async function TopbarWithUser() {
  const user = await requireUser();
  return <DashboardTopbar userName={user.full_name} />;
}

function TopbarShell() {
  // Mirrors DashboardTopbar's outer chrome so layout doesn't reflow when the
  // real topbar hydrates.
  return <header className="h-16 border-b border-border/60 bg-background" />;
}
