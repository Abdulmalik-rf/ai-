"use client";

/**
 * Lightweight modal scaffold used by the three "quick-create" launchers on
 * the dashboard home: New case, New consultation, New memo. Each variant
 * fills in its own copy and posts a different shape to the API, but the
 * chrome (overlay + escape-to-close + error banner + create button) is
 * identical so the user gets a consistent micro-interaction.
 */
import { Loader2, X } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  submitLabel: string;
  cancelLabel: string;
  submitting: boolean;
  error: string | null;
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
  children: React.ReactNode;
}

export function QuickCreateDialog({
  open,
  onClose,
  title,
  submitLabel,
  cancelLabel,
  submitting,
  error,
  onSubmit,
  children,
}: Props) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/50 backdrop-blur-sm p-4 overflow-y-auto"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="relative w-full max-w-lg rounded-2xl border border-border/60 bg-card shadow-2xl my-8"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 pt-5 pb-3 border-b border-border/40 sticky top-0 bg-card rounded-t-2xl">
          <h2 className="text-xl font-bold tracking-tight">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            aria-label={cancelLabel}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={onSubmit} className="px-6 pb-6 pt-4 space-y-4">
          {children}

          {error && (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={submitting}
            >
              {cancelLabel}
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {submitLabel}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-foreground/90 mb-1.5 block">
        {label}
      </span>
      {children}
    </label>
  );
}
