"use client";

/**
 * Manifesto block — calm. Just the quote, the attribution, a giant
 * decorative quotation glyph in the corner, and a gold top rule. No
 * cursor spotlight, no per-word stagger.
 */

export function Manifesto({
  kicker,
  quote,
  attribution,
}: {
  kicker: string;
  quote: string;
  attribution: string;
}) {
  return (
    <section className="container py-20 md:py-24">
      <div className="relative max-w-4xl mx-auto rounded-3xl border border-border/60 bg-card/80 overflow-hidden">
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(120% 80% at 0% 0%, hsl(36 60% 50% / 0.06), transparent 55%)," +
              "radial-gradient(120% 80% at 100% 100%, hsl(160 65% 22% / 0.06), transparent 55%)",
          }}
        />

        <div
          aria-hidden
          className="absolute inset-x-0 top-0 h-px"
          style={{
            backgroundImage:
              "linear-gradient(90deg, transparent, hsl(36 60% 50%), transparent)",
          }}
        />

        <div
          aria-hidden
          className="pointer-events-none absolute -top-6 end-6 select-none text-[160px] leading-none font-serif text-accent/15"
        >
          “
        </div>

        <div className="relative p-10 md:p-14">
          <div className="text-[11px] uppercase tracking-[0.24em] text-accent font-semibold mb-6">
            {kicker}
          </div>

          <blockquote className="text-2xl md:text-4xl font-semibold leading-snug tracking-tight text-foreground">
            {quote}
          </blockquote>

          <div className="mt-8 flex items-center gap-3">
            <div
              className="h-px w-10"
              style={{
                backgroundImage:
                  "linear-gradient(90deg, hsl(36 60% 50%), transparent)",
              }}
            />
            <div className="text-sm font-semibold text-foreground/80">
              {attribution}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
