"use client";

/**
 * Locale-level error boundary. Catches client-side render errors so the user
 * doesn't see Next.js's stark red dev overlay — and, more importantly,
 * auto-recovers from `ChunkLoadError` (the dev server pruned the chunk hash
 * the open tab was holding onto, typical after a hot recompile).
 *
 * The boundary is rendered for both marketing, auth, and dashboard subtrees
 * because it lives at `[locale]/error.tsx`. Route-level `error.tsx` files
 * can still override it for narrower behaviour.
 */
import { AlertTriangle, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

function isChunkLoadError(err: Error) {
  const msg = err?.message || "";
  const name = err?.name || "";
  return (
    name === "ChunkLoadError" ||
    msg.includes("ChunkLoadError") ||
    msg.includes("Loading chunk") ||
    msg.includes("Failed to fetch dynamically imported module") ||
    msg.includes("error loading dynamically imported module")
  );
}

const RELOAD_FLAG = "lai_chunk_reload_at";

export default function LocaleError({ error, reset }: ErrorProps) {
  const [chunk] = useState(() => isChunkLoadError(error));
  const [autoReloading, setAutoReloading] = useState(chunk);

  useEffect(() => {
    if (!chunk) return;

    // Guard against an infinite reload loop: if we already reloaded in the
    // last 10 seconds and still see a ChunkLoadError, the chunks are
    // actually broken — stop reloading and show the error UI.
    const last = Number(
      sessionStorage.getItem(RELOAD_FLAG) || "0"
    );
    if (Date.now() - last < 10_000) {
      setAutoReloading(false);
      return;
    }
    sessionStorage.setItem(RELOAD_FLAG, String(Date.now()));
    // Tiny delay so React has time to flush state before the page is yanked.
    const id = window.setTimeout(() => window.location.reload(), 50);
    return () => window.clearTimeout(id);
  }, [chunk]);

  if (autoReloading) {
    return (
      <div className="grid place-items-center min-h-[60vh] p-6">
        <div className="flex flex-col items-center gap-3 text-sm text-muted-foreground">
          <RefreshCw className="h-5 w-5 animate-spin" />
          <span>Refreshing…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="container max-w-xl py-16">
      <div className="rounded-2xl border border-border/60 bg-card p-8 text-center shadow-sm">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-destructive/10 text-destructive">
          <AlertTriangle className="h-7 w-7" />
        </div>
        <h1 className="mt-5 text-xl font-semibold tracking-tight">
          Something went wrong
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {chunk
            ? "The app couldn't load a code chunk. This usually clears with a refresh."
            : error.message || "An unexpected error occurred."}
        </p>
        {error.digest && (
          <p className="mt-2 text-xs text-muted-foreground/70 font-mono">
            ref: {error.digest}
          </p>
        )}
        <div className="mt-6 flex items-center justify-center gap-2">
          <Button onClick={() => reset()}>
            <RefreshCw className="h-4 w-4" />
            Try again
          </Button>
          <Button
            variant="outline"
            onClick={() => window.location.reload()}
          >
            Reload page
          </Button>
        </div>
      </div>
    </div>
  );
}
