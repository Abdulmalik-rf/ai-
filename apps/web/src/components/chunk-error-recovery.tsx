"use client";

/**
 * Dev-time chunk-load recovery.
 *
 * Next.js hot-recompiles in dev produce fresh chunk hashes and prune the old
 * ones. Any tab loaded before a recompile is still pointing at the old hashes
 * — clicking a Link triggers a dynamic import that 404s, and React/Next.js
 * either surfaces a `ChunkLoadError` (caught by `error.tsx`) OR an
 * unhandled-promise rejection that bypasses the React boundary entirely and
 * shows the red dev overlay.
 *
 * This component installs window-level listeners that catch the rejection
 * BEFORE the overlay sees it and forces a single hard reload, recovering
 * the page transparently. A 10-second cooldown prevents infinite reload
 * loops if the chunks are genuinely broken (not just stale).
 *
 * Active only when navigator is online, to avoid reloading into the same
 * offline failure.
 */
import { useEffect } from "react";

const COOLDOWN_KEY = "lai_chunk_recover_at";
const COOLDOWN_MS = 10_000;

function looksLikeChunkError(value: unknown): boolean {
  if (!value) return false;
  const err =
    value instanceof Error
      ? value
      : typeof value === "object" && value !== null && "message" in value
        ? (value as { message?: unknown; name?: unknown })
        : null;
  if (!err) {
    return typeof value === "string" && /ChunkLoadError|Loading chunk/.test(value);
  }
  const msg = String(err.message ?? "");
  const name = String((err as { name?: unknown }).name ?? "");
  return (
    name === "ChunkLoadError" ||
    msg.includes("ChunkLoadError") ||
    msg.includes("Loading chunk") ||
    msg.includes("Failed to fetch dynamically imported module") ||
    msg.includes("error loading dynamically imported module") ||
    msg.includes("Importing a module script failed")
  );
}

function shouldRecover(): boolean {
  if (typeof window === "undefined") return false;
  if (navigator && navigator.onLine === false) return false;
  try {
    const last = Number(sessionStorage.getItem(COOLDOWN_KEY) || "0");
    if (Number.isFinite(last) && Date.now() - last < COOLDOWN_MS) return false;
    sessionStorage.setItem(COOLDOWN_KEY, String(Date.now()));
  } catch {
    /* sessionStorage blocked — recover anyway */
  }
  return true;
}

function reload() {
  // Tiny delay so other queued events finish first.
  window.setTimeout(() => window.location.reload(), 30);
}

export function ChunkErrorRecovery() {
  useEffect(() => {
    const onRejection = (e: PromiseRejectionEvent) => {
      if (!looksLikeChunkError(e.reason)) return;
      if (!shouldRecover()) return;
      e.preventDefault();
      reload();
    };

    const onError = (e: ErrorEvent) => {
      // Webpack-style chunk failures come in as ErrorEvent with `error` set.
      if (!looksLikeChunkError(e.error ?? e.message)) return;
      if (!shouldRecover()) return;
      e.preventDefault();
      reload();
    };

    window.addEventListener("unhandledrejection", onRejection);
    window.addEventListener("error", onError, true);

    return () => {
      window.removeEventListener("unhandledrejection", onRejection);
      window.removeEventListener("error", onError, true);
    };
  }, []);

  return null;
}
