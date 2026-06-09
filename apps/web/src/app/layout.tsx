import type { Metadata } from "next";

import "@/styles/globals.css";

export const metadata: Metadata = {
  title: {
    default: "مستشاري AI — Mostashari AI",
    template: "%s · مستشاري AI",
  },
  description:
    "مستشارك القانوني الذكي في المملكة العربية السعودية — بحث قانوني، صياغة، مراجعة عقود، تحليل قضايا، وإدارة العملاء بقدرات الذكاء الاصطناعي.",
  icons: {
    icon: "/favicon.png",
    apple: "/favicon.png",
  },
  openGraph: {
    title: "مستشاري AI — Mostashari AI",
    description:
      "Your intelligent legal counsel for Saudi Arabia. Research, drafting, contract review, case analysis, and CRM — all in one bilingual workspace.",
    images: ["/logo.png"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
