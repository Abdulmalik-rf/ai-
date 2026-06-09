"use client";

/**
 * Web Speech API hook — tap-to-talk voice input shared between the home
 * hero and the chat workspace. Returns:
 *
 *   - `supported`: whether the browser exposes SpeechRecognition (null
 *     during SSR / first render, then true|false). Use it to hide the
 *     mic button entirely on Firefox & old WebViews.
 *   - `listening`: true while the engine is actively transcribing.
 *   - `error`: localized message when permission is denied or no mic is
 *     present; null otherwise.
 *   - `start({ base, onTranscript, onFinish })`: begin recording. Live
 *     partial results stream through `onTranscript(text)` (the full
 *     buffer, not deltas). When recognition ends — either via `stop()`
 *     or natural silence — `onFinish(finalText)` fires once.
 *   - `stop()`: terminate the current session early. `onFinish` still
 *     fires with whatever was transcribed.
 *
 * Designed to be called per-component instance; cleans up on unmount.
 */
import { useCallback, useEffect, useRef, useState } from "react";

// --- Web Speech API minimal typing ----------------------------------------

interface SpeechRecognitionAlternativeLike {
  readonly transcript: string;
}
interface SpeechRecognitionResultLike {
  readonly isFinal: boolean;
  readonly length: number;
  readonly 0: SpeechRecognitionAlternativeLike;
}
interface SpeechRecognitionEventLike extends Event {
  readonly resultIndex: number;
  readonly results: ArrayLike<SpeechRecognitionResultLike>;
}
interface SpeechRecognitionErrorEventLike extends Event {
  readonly error: string;
}
interface SpeechRecognitionLike extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult:
    | ((this: SpeechRecognitionLike, ev: SpeechRecognitionEventLike) => void)
    | null;
  onend: ((this: SpeechRecognitionLike, ev: Event) => void) | null;
  onerror:
    | ((this: SpeechRecognitionLike, ev: SpeechRecognitionErrorEventLike) => void)
    | null;
  start(): void;
  stop(): void;
  abort(): void;
}
interface SpeechRecognitionCtor {
  new (): SpeechRecognitionLike;
}
declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

export interface StartOptions {
  /** Existing input value to preserve and append the transcript to. */
  base?: string;
  /** Called on every (interim+final) result with the full buffer. */
  onTranscript: (text: string) => void;
  /** Called once after the session ends with the final assembled text. */
  onFinish?: (finalText: string) => void;
}

export interface VoiceInput {
  supported: boolean | null;
  listening: boolean;
  error: string | null;
  start: (opts: StartOptions) => void;
  stop: () => void;
}

export function useVoiceInput(locale: string): VoiceInput {
  const isAr = locale === "ar";
  const [supported, setSupported] = useState<boolean | null>(null);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Refs that survive re-renders while a recognition session is active.
  const recogRef = useRef<SpeechRecognitionLike | null>(null);
  const baseRef = useRef<string>("");
  const latestRef = useRef<string>("");
  const onFinishRef = useRef<StartOptions["onFinish"] | undefined>(undefined);
  // `true` when the session should fire onFinish — flipped off when the
  // engine returns an error or the user explicitly aborts.
  const finishOnEndRef = useRef<boolean>(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setSupported(
      Boolean(window.SpeechRecognition ?? window.webkitSpeechRecognition),
    );
  }, []);

  const stop = useCallback(() => {
    const r = recogRef.current;
    if (r) {
      try {
        r.stop();
      } catch {
        /* already stopped */
      }
    }
  }, []);

  const start = useCallback(
    ({ base = "", onTranscript, onFinish }: StartOptions) => {
      const Ctor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
      if (!Ctor) {
        setSupported(false);
        return;
      }
      setError(null);
      baseRef.current = base;
      latestRef.current = base;
      onFinishRef.current = onFinish;
      finishOnEndRef.current = true;

      const r = new Ctor();
      r.lang = isAr ? "ar-SA" : "en-US";
      r.continuous = true;
      r.interimResults = true;

      r.onresult = (ev) => {
        let transcript = "";
        for (let i = 0; i < ev.results.length; i++) {
          transcript += ev.results[i][0].transcript;
        }
        const baseText = baseRef.current;
        const sep =
          baseText && !baseText.endsWith(" ") && transcript ? " " : "";
        const next = `${baseText}${sep}${transcript}`.trimStart();
        latestRef.current = next;
        onTranscript(next);
      };

      r.onerror = (ev) => {
        const code = ev.error;
        if (code === "no-speech" || code === "aborted") {
          finishOnEndRef.current = false;
          return;
        }
        if (code === "not-allowed" || code === "service-not-allowed") {
          setError(
            isAr
              ? "تعذّر الوصول إلى المايكروفون. فعّل الإذن من إعدادات المتصفح."
              : "Mic permission denied. Enable it in your browser settings.",
          );
        } else if (code === "audio-capture") {
          setError(
            isAr
              ? "لم يتم العثور على مايكروفون."
              : "No microphone detected on this device.",
          );
        } else {
          setError(
            isAr
              ? `تعذّرت عملية الإملاء (${code}).`
              : `Voice input failed (${code}).`,
          );
        }
        finishOnEndRef.current = false;
      };

      r.onend = () => {
        setListening(false);
        recogRef.current = null;
        if (finishOnEndRef.current && onFinishRef.current) {
          onFinishRef.current(latestRef.current);
        }
        finishOnEndRef.current = false;
        onFinishRef.current = undefined;
      };

      try {
        r.start();
        recogRef.current = r;
        setListening(true);
      } catch {
        setError(isAr ? "تعذّر بدء التسجيل." : "Couldn't start recording.");
        finishOnEndRef.current = false;
      }
    },
    [isAr],
  );

  // Abort any active session if the calling component unmounts.
  useEffect(() => {
    return () => {
      const r = recogRef.current;
      if (r) {
        try {
          r.abort();
        } catch {
          /* ignore */
        }
      }
    };
  }, []);

  return { supported, listening, error, start, stop };
}
