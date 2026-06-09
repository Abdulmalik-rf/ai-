import { MarketingFooter } from "@/components/marketing/footer";
import { MarketingNav } from "@/components/marketing/nav";

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // bg-ai-canvas spans the entire shell so every section sits on the same
  // continuous emerald→gold wash + neural-network dot pattern. Section
  // backgrounds inside the page should stay transparent.
  return (
    <div className="flex min-h-screen flex-col bg-ai-canvas">
      <MarketingNav />
      <main className="flex-1">{children}</main>
      <MarketingFooter />
    </div>
  );
}
