"use client";

/**
 * Textarea with a built-in tap-to-talk mic button — same UX as the
 * dashboard hero / chat input. Live transcript appends to the current
 * value (so anything the user already typed is preserved). The mic
 * button hides on browsers that don't support SpeechRecognition.
 */
import { Mic, MicOff } from "lucide-react";
import { useLocale } from "next-intl";

import { Textarea } from "@/components/ui/textarea";
import { useVoiceInput } from "@/hooks/use-voice-input";
import { cn } from "@/lib/utils";

interface Props
  extends Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "onChange"> {
  value: string;
  onChange: (next: string) => void;
  /** Optional callback once recognition ends naturally. */
  onTranscribed?: (finalText: string) => void;
  containerClassName?: string;
}

export function VoiceTextarea({
  value,
  onChange,
  onTranscribed,
  containerClassName,
  className,
  placeholder,
  ...rest
}: Props) {
  const locale = useLocale();
  const isAr = locale === "ar";
  const voice = useVoiceInput(locale);

  const toggle = () => {
    if (voice.listening) {
      voice.stop();
    } else {
      voice.start({
        base: value,
        onTranscript: onChange,
        onFinish: (finalText) => {
          if (onTranscribed) onTranscribed(finalText);
        },
      });
    }
  };

  return (
    <div className={cn("relative", containerClassName)}>
      <Textarea
        {...rest}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={
          voice.listening
            ? isAr
              ? "أستمع إليك…"
              : "Listening…"
            : placeholder
        }
        className={cn(
          // Reserve room for the mic in the end-bottom corner so the
          // user's text doesn't slide under it.
          "pe-10 pb-2",
          voice.listening && "ring-2 ring-destructive/40",
          className,
        )}
      />
      {voice.supported !== false && (
        <button
          type="button"
          onClick={toggle}
          aria-label={
            voice.listening
              ? isAr
                ? "إيقاف التسجيل"
                : "Stop voice input"
              : isAr
                ? "تحدث لإضافة نص"
                : "Dictate"
          }
          aria-pressed={voice.listening}
          className={cn(
            "absolute end-2 bottom-2 grid h-8 w-8 place-items-center rounded-full transition-colors shadow-sm",
            voice.listening
              ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
              : "bg-background border border-border text-muted-foreground hover:bg-muted hover:text-foreground"
          )}
        >
          <Mic className="h-4 w-4" />
          {voice.listening && (
            <span className="pointer-events-none absolute inset-0 rounded-full ring-2 ring-destructive/40 animate-ping" />
          )}
        </button>
      )}
      {(voice.error || voice.supported === false) && (
        <p className="mt-1 text-xs text-destructive flex items-center gap-1.5">
          <MicOff className="h-3 w-3" />
          {voice.error ??
            (isAr
              ? "متصفحك لا يدعم الإدخال الصوتي."
              : "Voice input not supported in this browser.")}
        </p>
      )}
    </div>
  );
}
