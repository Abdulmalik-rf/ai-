import Image from "next/image";

import { cn } from "@/lib/utils";

interface BrandLogoProps {
  /** Pixel size of the logo mark. */
  size?: number;
  /** Show the full logo (icon + Arabic wordmark) instead of just the mark. */
  showWordmark?: boolean;
  /** Locale — kept for API symmetry, currently unused (the image is fixed). */
  locale?: string;
  className?: string;
}

// Cache-bust query — bumped whenever the source PNGs change.
const V = "v=3";

/**
 * Brand mark for Mostashari AI / مستشاري AI.
 *
 * Two distinct assets are emitted by `scripts/transparentize_logo.py`:
 *   - `/logo.png`       — full lockup (icon + Arabic wordmark)
 *   - `/logo-mark.png`  — icon only (the speech bubble), tightly cropped
 */
export function BrandLogo({
  size = 32,
  showWordmark = false,
  className,
}: BrandLogoProps) {
  const src = showWordmark
    ? `/logo.png?${V}`
    : `/logo-mark.png?${V}`;

  return (
    <Image
      src={src}
      alt="مستشاري AI"
      width={size}
      height={size}
      className={cn(
        "object-contain shrink-0",
        // The logo's deep-emerald strokes disappear into the dark-mode
        // background; nudging brightness + saturation keeps both the green
        // and the gold accents readable on either canvas.
        "dark:brightness-[1.7] dark:saturate-110",
        className,
      )}
      priority
    />
  );
}

/**
 * Inline lockup — icon mark + custom-styled bilingual wordmark.
 * Used in nav bars where the full PNG would be too tall.
 */
export function BrandLockup({
  size = 28,
  locale = "ar",
  className,
}: {
  size?: number;
  locale?: string;
  className?: string;
}) {
  const isAr = locale === "ar";
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <BrandLogo size={size} />
      <div className="flex items-baseline gap-1.5 leading-none">
        {isAr ? (
          <>
            <span className="font-bold text-[1.05em] text-primary">
              مستشاري
            </span>
            <span className="font-semibold text-[0.9em] text-accent tracking-wide">
              AI
            </span>
          </>
        ) : (
          <>
            <span className="font-bold text-[1.05em] text-primary">
              Mostashari
            </span>
            <span className="font-semibold text-[0.9em] text-accent tracking-wide">
              AI
            </span>
          </>
        )}
      </div>
    </div>
  );
}
