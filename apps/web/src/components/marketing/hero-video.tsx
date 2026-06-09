"use client";

import { Play } from "lucide-react";
import { useLocale } from "next-intl";
import { useState } from "react";

import { BrandLogo } from "@/components/brand-logo";

/**
 * Renders inside the laptop "screen" of the hero ContainerScroll.
 *
 * Behaviour:
 *   - If `apps/web/public/demo.mp4` exists, plays it (with poster + controls).
 *   - Otherwise shows a branded placeholder with a play button — clicking it
 *     attempts to load the video anyway, in case it was just dropped in.
 *
 * To replace with a real demo: drop the file at `apps/web/public/demo.mp4`
 * (and optionally `apps/web/public/demo-poster.png`) and refresh.
 */
export function HeroVideo() {
  const locale = useLocale();
  const [showVideo, setShowVideo] = useState(false);

  if (showVideo) {
    return (
      <div className="relative h-full w-full bg-black rounded-xl overflow-hidden">
        <video
          className="h-full w-full object-cover"
          src="/demo.mp4"
          poster="/demo-poster.png"
          controls
          autoPlay
          playsInline
        />
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setShowVideo(true)}
      className="group relative h-full w-full overflow-hidden rounded-xl text-start"
      aria-label={locale === "ar" ? "تشغيل الفيديو" : "Play demo video"}
    >
      {/* Branded backdrop */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(ellipse 60% 70% at 50% 0%, hsl(160 65% 22% / 0.45), transparent 70%)," +
            "radial-gradient(ellipse 80% 60% at 100% 100%, hsl(36 55% 47% / 0.30), transparent 70%)," +
            "linear-gradient(180deg, hsl(165 30% 7%), hsl(165 35% 5%))",
        }}
      />

      {/* Faint grid */}
      <div
        className="absolute inset-0 opacity-40"
        style={{
          backgroundImage:
            "linear-gradient(hsl(40 30% 96% / 0.04) 1px, transparent 1px), linear-gradient(90deg, hsl(40 30% 96% / 0.04) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
        }}
      />

      {/* Content */}
      <div className="relative h-full w-full flex flex-col items-center justify-center gap-5 p-8 text-center">
        <BrandLogo size={64} className="opacity-95" />

        <div className="space-y-2">
          <div className="text-white/95 text-xl md:text-2xl font-semibold">
            {locale === "ar"
              ? "شاهد كيف يعمل مستشاري AI"
              : "See Mostashari AI in action"}
          </div>
          <div className="text-white/55 text-sm md:text-base max-w-md mx-auto">
            {locale === "ar"
              ? "بحث قانوني، صياغة عقود، وتحليل قضايا — كل ذلك بنقرة واحدة."
              : "Legal research, contract drafting, and case analysis — one click away."}
          </div>
        </div>

        <div
          className="mt-2 grid place-items-center h-16 w-16 rounded-full bg-accent text-accent-foreground shadow-lg ring-4 ring-accent/20 group-hover:scale-110 transition-transform"
          style={{ boxShadow: "0 10px 40px hsl(36 55% 47% / 0.45)" }}
        >
          <Play className="h-7 w-7 translate-x-0.5 fill-current" />
        </div>

        <div className="text-white/40 text-xs">
          {locale === "ar" ? "٢ دقائق · OST" : "2 min demo"}
        </div>
      </div>

      {/* Webcam dot — laptop-screen detail */}
      <div className="absolute top-3 left-1/2 -translate-x-1/2 h-1.5 w-1.5 rounded-full bg-white/30" />
    </button>
  );
}
