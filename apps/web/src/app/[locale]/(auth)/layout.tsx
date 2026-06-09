import { Link } from "@/i18n/routing";
import { getLocale } from "next-intl/server";

import { BrandLogo } from "@/components/brand-logo";

export default async function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = await getLocale();
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-gradient-emerald">
      <Link
        href="/"
        className="mb-8 flex flex-col items-center gap-2"
        aria-label="مستشاري AI"
      >
        <BrandLogo size={64} locale={locale} />
        <div className="flex items-baseline gap-1.5 leading-none mt-1">
          {locale === "ar" ? (
            <>
              <span className="font-bold text-xl text-primary">مستشاري</span>
              <span className="font-semibold text-base text-accent tracking-wide">
                AI
              </span>
            </>
          ) : (
            <>
              <span className="font-bold text-xl text-primary">Mostashari</span>
              <span className="font-semibold text-base text-accent tracking-wide">
                AI
              </span>
            </>
          )}
        </div>
      </Link>
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}
