import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { Inter, Tajawal } from "next/font/google";
import { notFound } from "next/navigation";

import { ChunkErrorRecovery } from "@/components/chunk-error-recovery";
import { ThemeProvider } from "@/components/theme-provider";
import { routing, type Locale } from "@/i18n/routing";

// Latin face — clean modern sans, pairs well with the wordmark.
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

// Arabic face — Tajawal renders Arabic legal terms cleanly with proper kerning.
const tajawal = Tajawal({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "700", "800"],
  variable: "--font-arabic",
  display: "swap",
});

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: Locale }>;
}) {
  const { locale } = await params;
  if (!routing.locales.includes(locale)) notFound();

  const messages = await getMessages();
  const dir = locale === "ar" ? "rtl" : "ltr";

  return (
    <html
      lang={locale}
      dir={dir}
      className={`${inter.variable} ${tajawal.variable}`}
      suppressHydrationWarning
    >
      <body
        className={`min-h-screen bg-background antialiased ${
          locale === "ar" ? tajawal.className : inter.className
        }`}
      >
        <NextIntlClientProvider messages={messages}>
          <ChunkErrorRecovery />
          <ThemeProvider>{children}</ThemeProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
