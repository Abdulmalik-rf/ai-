"use client";

import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { Link } from "@/i18n/routing";

import { BrandLogo } from "@/components/brand-logo";
import { Button } from "@/components/ui/button";

export function FeaturesFinalCta({
  locale,
  kicker,
  title,
  subtitle,
  primary,
  secondary,
}: {
  locale: string;
  kicker: string;
  title: string;
  subtitle: string;
  primary: string;
  secondary: string;
}) {
  const reduceMotion = useReducedMotion();

  return (
    <section className="container py-20 md:py-28">
      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 28 }}
        whileInView={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        className="relative max-w-4xl mx-auto overflow-hidden rounded-3xl border border-border/60 bg-card shadow-[0_28px_80px_-32px_hsl(160_65%_18%/0.45)]"
      >
        {/* Animated emerald + gold ambient gradient backdrop */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 90% 90% at 50% 100%, hsl(160 65% 22% / 0.14), transparent 70%)," +
              "radial-gradient(ellipse 60% 60% at 100% 0%, hsl(36 60% 50% / 0.10), transparent 70%)," +
              "radial-gradient(ellipse 60% 60% at 0% 0%, hsl(160 60% 35% / 0.06), transparent 70%)",
          }}
        />

        {/* Animated top border-glow */}
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          animate={reduceMotion ? undefined : { backgroundPosition: ["0% 0", "200% 0"] }}
          transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
          style={{
            backgroundImage:
              "linear-gradient(90deg, transparent 0%, hsl(36 60% 55%) 50%, transparent 100%)",
            backgroundSize: "200% 100%",
          }}
        />

        <div className="relative p-10 md:p-14 text-center">
          <div className="flex justify-center mb-5">
            <BrandLogo size={56} locale={locale} />
          </div>

          <div className="inline-flex items-center gap-2 rounded-full border border-accent/40 bg-accent/5 text-accent text-xs font-semibold uppercase tracking-[0.2em] px-3 py-1">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            {kicker}
          </div>

          <h2 className="mt-5 text-3xl md:text-4xl font-bold tracking-tight leading-tight">
            {title}
          </h2>

          <div
            aria-hidden
            className="mx-auto mt-4 h-[2px] w-16 rounded-full"
            style={{
              backgroundImage:
                "linear-gradient(90deg, transparent, hsl(36 60% 50%), transparent)",
            }}
          />

          <p className="mt-4 text-muted-foreground text-base md:text-lg max-w-xl mx-auto">
            {subtitle}
          </p>

          <div className="mt-7 flex flex-col sm:flex-row gap-3 justify-center">
            <Button asChild size="lg" className="shadow-md group/btn">
              <Link href="/sign-up">
                {primary}
                <ArrowRight className="ms-2 h-4 w-4 transition-transform duration-300 group-hover/btn:translate-x-1 rtl:group-hover/btn:-translate-x-1 rtl:scale-x-[-1]" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/about">{secondary}</Link>
            </Button>
          </div>
        </div>
      </motion.div>
    </section>
  );
}
