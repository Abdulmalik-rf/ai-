"use client";

/**
 * Saudi-first callout — calm version.
 *
 * The KSA polygon is drawn statically (no path-length tween, no looping
 * city pulses). Chips render in place rather than fading in one by one.
 * The visual impact comes from the abstract map outline and the
 * curated chip cloud, not from motion.
 */
const EMERALD = "hsl(160 65% 22%)";
const GOLD = "hsl(36 60% 50%)";

type City = { name: string; x: number; y: number };
// City positions placed on the KSA outline below at roughly the real
// geography. Coordinates are within the 100×80 viewBox the path uses.
//   Riyadh   — central, slightly east
//   Jeddah   — west on the Red Sea coast
//   Makkah   — just inland (east) from Jeddah
//   Madinah  — north of Jeddah, still western
//   Dammam   — Persian-Gulf east coast
//   AlKhobar — slightly south of Dammam on the same coast
// Positions are inside the path polygon and roughly correct relative to
// the real geography. Verified vs the path boundary so the dots don't
// land in the sea:
//   • Path west coast (Red Sea) at y=50 ≈ x=24.3, at y=53 ≈ x=24.6 →
//     Jeddah sits just east of that line (it's a coastal city); Makkah
//     a couple of units further inland.
//   • Path east coast (Persian Gulf) at y=23 ≈ x=66, at y=27 ≈ x=69 →
//     Dammam / AlKhobar are nudged just inside that.
const CITY_POSITIONS: { ar: string; en: string; x: number; y: number }[] = [
  { en: "Riyadh", ar: "الرياض", x: 54, y: 39 },
  { en: "Jeddah", ar: "جدة", x: 26, y: 52 },
  { en: "Makkah", ar: "مكة", x: 30, y: 54 },
  { en: "Madinah", ar: "المدينة", x: 25, y: 38 },
  { en: "Dammam", ar: "الدمام", x: 66, y: 23 },
  { en: "AlKhobar", ar: "الخبر", x: 68, y: 27 },
];

export function SaudiCallout({
  kicker,
  title,
  body,
  chips,
  locale,
}: {
  kicker: string;
  title: string;
  body: string;
  chips: string[];
  cityLabels: string[];
  locale: string;
}) {
  const cities: City[] = CITY_POSITIONS.map((c) => ({
    name: locale === "ar" ? c.ar : c.en,
    x: c.x,
    y: c.y,
  }));

  return (
    <section className="container py-20 md:py-24">
      <div className="grid lg:grid-cols-[1.05fr_1fr] gap-10 lg:gap-14 items-center">
        <div>
          <div className="text-[11px] uppercase tracking-[0.24em] text-accent font-semibold mb-4">
            {kicker}
          </div>
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight leading-tight">
            {title}
          </h2>
          <div
            className="mt-4 h-[2px] w-12"
            style={{
              backgroundImage:
                "linear-gradient(90deg, hsl(36 60% 50%), transparent)",
            }}
          />
          <p className="mt-5 text-base md:text-lg text-muted-foreground leading-relaxed max-w-xl">
            {body}
          </p>

          <ul className="mt-6 flex flex-wrap gap-2">
            {chips.map((chip) => (
              <li
                key={chip}
                className="inline-flex items-center rounded-full border border-border/70 bg-card/60 backdrop-blur-sm px-3 py-1 text-xs font-medium text-foreground hover:border-accent/50 hover:text-accent transition-colors"
              >
                {chip}
              </li>
            ))}
          </ul>
        </div>

        <KingdomGraphic cities={cities} />
      </div>
    </section>
  );
}

function KingdomGraphic({ cities }: { cities: City[] }) {
  return (
    <div className="relative aspect-[5/4] w-full max-w-xl mx-auto">
      <div
        aria-hidden
        className="absolute inset-0 rounded-2xl border border-border/60 overflow-hidden"
        style={{
          background:
            "radial-gradient(120% 80% at 100% 100%, hsl(160 65% 22% / 0.06), transparent 55%)," +
            "radial-gradient(120% 80% at 0% 0%, hsl(36 60% 50% / 0.04), transparent 55%)," +
            "hsl(var(--card))",
        }}
      >
        <div
          className="absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              "radial-gradient(circle, hsl(160 65% 22% / 0.08) 1px, transparent 1px)",
            backgroundSize: "24px 24px",
          }}
        />
      </div>

      <svg viewBox="0 0 100 80" className="relative h-full w-full" aria-hidden>
        <defs>
          <linearGradient id="kingdom-fill" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor={EMERALD} stopOpacity="0.10" />
            <stop offset="100%" stopColor={GOLD} stopOpacity="0.10" />
          </linearGradient>
          <linearGradient id="kingdom-stroke" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor={EMERALD} stopOpacity="0.55" />
            <stop offset="100%" stopColor={GOLD} stopOpacity="0.65" />
          </linearGradient>
        </defs>

        {/* Outline of the Kingdom of Saudi Arabia, hand-traced from real
            geographic borders (lon 34.6–55.7, lat 32.2–16.4) scaled into
            this 100×80 viewBox. Reads as KSA at a glance because every
            distinctive feature is in place:
              • Gulf-of-Aqaba notch in the upper-left (Tabuk corner)
              • angular Jordan / Iraq border with the neutral-zone step
              • Kuwait corner in the NE
              • Persian-Gulf east coast
              • the Qatar-peninsula bite — three short segments that
                indent into the country (KSA wraps around Qatar)
              • UAE / Empty-Quarter tripoint at the SE max
              • south-west arc of the Oman / Yemen border
              • Red-Sea west coast climbing back up to Tabuk
            Not a survey polygon but enough detail to be unmistakably KSA. */}
        <path
          d="
            M 7 21
            L 9 14
            L 18 14
            L 22 5
            L 30 7
            L 38 6
            L 50 8
            L 56 14
            L 60 17
            L 64 20
            L 68 25
            L 71 29
            L 73 32
            L 74 34
            L 72 36
            L 75 37
            L 77 39
            L 94 48
            L 92 52
            L 90 62
            L 79 65
            L 60 70
            L 45 72
            L 40 76
            L 28 65
            L 24 51
            L 19 36
            Z
          "
          fill="url(#kingdom-fill)"
          stroke="url(#kingdom-stroke)"
          strokeWidth="0.7"
          strokeLinejoin="round"
        />

        {cities.map((city) => (
          <g key={city.name}>
            <circle cx={city.x} cy={city.y} r="2.6" fill={GOLD} opacity="0.18" />
            <circle cx={city.x} cy={city.y} r="1.5" fill={GOLD} />
            <text
              x={city.x + (city.x > 50 ? -2.5 : 2.5)}
              y={city.y - 2.5}
              textAnchor={city.x > 50 ? "end" : "start"}
              fontSize="2.4"
              fontWeight="500"
              fill="hsl(var(--foreground))"
              opacity="0.85"
            >
              {city.name}
            </text>
          </g>
        ))}
      </svg>

      <div className="absolute end-4 top-4 inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/70 backdrop-blur-sm px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-foreground/80">
        <span className="h-1.5 w-1.5 rounded-full bg-accent" />
        KSA
      </div>
    </div>
  );
}
