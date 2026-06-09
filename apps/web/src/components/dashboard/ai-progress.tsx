"use client";

/**
 * Staged progress indicator for single-call AI operations (case analysis,
 * drafting, etc.) where we can't track sub-steps server-side. Shows an
 * elapsed timer + an animated bar + a rotating stage label so the user
 * sees motion instead of a frozen spinner.
 *
 * Multi-advisor flows (consultations, memo review, final review, contract
 * review) use real server-polled progress instead — this is only for the
 * genuinely single-shot calls.
 */
import { Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

interface Props {
  /** Stage labels cycled through while the call runs. */
  stages: string[];
  /** Rough seconds the operation usually takes — drives the bar fill. */
  estimateSeconds?: number;
  className?: string;
}

export function AiProgress({ stages, estimateSeconds = 30, className }: Props) {
  const [elapsed, setElapsed] = useState(0);
  const [stageIdx, setStageIdx] = useState(0);
  const startedRef = useRef<number | null>(null);

  useEffect(() => {
    // Date.now is fine in the browser; this never runs server-side.
    startedRef.current = Date.now();
    const tick = setInterval(() => {
      if (startedRef.current != null) {
        setElapsed(Math.floor((Date.now() - startedRef.current) / 1000));
      }
    }, 500);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    if (stages.length <= 1) return;
    const every = Math.max(3, Math.floor(estimateSeconds / stages.length));
    const rot = setInterval(() => {
      // Advance but never past the last stage (it lingers until done).
      setStageIdx((i) => Math.min(i + 1, stages.length - 1));
    }, every * 1000);
    return () => clearInterval(rot);
  }, [stages.length, estimateSeconds]);

  // Asymptotic fill: approaches but never reaches 100% until the caller
  // unmounts the component on completion. Feels honest (it's an estimate).
  const pct = Math.min(95, Math.round((1 - Math.exp(-elapsed / Math.max(1, estimateSeconds * 0.6))) * 100));
  const mm = Math.floor(elapsed / 60);
  const ss = String(elapsed % 60).padStart(2, "0");

  return (
    <div className={cn("w-full rounded-lg border border-border/60 bg-muted/30 p-3 space-y-2", className)}>
      <div className="flex items-center justify-between text-xs">
        <span className="flex items-center gap-1.5 font-medium">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
          {stages[stageIdx] ?? stages[0]}
        </span>
        <span className="text-muted-foreground tabular-nums">
          {mm}:{ss}
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-border/60 overflow-hidden">
        <div className="h-full bg-primary transition-all duration-700 ease-out" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
