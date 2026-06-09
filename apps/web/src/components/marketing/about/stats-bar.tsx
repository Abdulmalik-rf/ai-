"use client";

/**
 * Stats strip — calm. Numbers render at their final value immediately,
 * no count-up animation, no per-cell stagger. Static gold top accent
 * keeps the strip visually anchored without movement.
 */

export type StatItem = {
  value: number;
  suffix?: string;
  label: string;
  decimals?: number;
};

export function StatsBar({
  kicker,
  items,
}: {
  kicker: string;
  items: StatItem[];
}) {
  return (
    <section className="container">
      <div className="relative rounded-2xl border border-border/60 bg-card/80 backdrop-blur-sm overflow-hidden">
        <div
          aria-hidden
          className="absolute inset-x-0 top-0 h-px"
          style={{
            backgroundImage:
              "linear-gradient(90deg, transparent, hsl(36 60% 50%), transparent)",
          }}
        />

        <div className="relative p-8 md:p-10">
          {kicker && (
            <div className="text-center text-[11px] uppercase tracking-[0.24em] text-accent font-semibold mb-6">
              {kicker}
            </div>
          )}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-y-8 gap-x-6">
            {items.map((item) => (
              <StatCell key={item.label} item={item} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function StatCell({ item }: { item: StatItem }) {
  const formatted = item.decimals
    ? item.value.toFixed(item.decimals)
    : Math.round(item.value).toLocaleString();

  return (
    <div className="text-center">
      <div className="flex items-baseline justify-center gap-0.5">
        <span className="text-4xl md:text-5xl font-bold tracking-tight tabular-nums text-foreground">
          {formatted}
        </span>
        {item.suffix && (
          <span className="text-2xl md:text-3xl font-semibold text-accent">
            {item.suffix}
          </span>
        )}
      </div>
      <div
        aria-hidden
        className="mx-auto mt-3 h-px w-12"
        style={{
          backgroundImage:
            "linear-gradient(90deg, transparent, hsl(36 60% 50%), transparent)",
        }}
      />
      <div className="mt-3 text-xs md:text-sm text-muted-foreground leading-snug">
        {item.label}
      </div>
    </div>
  );
}
