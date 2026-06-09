"use client";

import {
  ArrowUp,
  BookOpen,
  BookText,
  Check,
  FileText,
  Loader2,
  Mic,
  MicOff,
  MessageSquare,
  Paperclip,
  RotateCcw,
  SlidersHorizontal,
  Sparkles,
  X,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { QuickActions } from "@/components/dashboard/quick-actions";
import { useVoiceInput } from "@/hooks/use-voice-input";
import { cn } from "@/lib/utils";

type AskMode = "ask" | "search";

interface AttachedFile {
  id: string;
  file: File;
  /** Set once the file has been uploaded to /v1/documents. */
  documentId?: string;
  status: "pending" | "uploading" | "done" | "failed";
  error?: string;
}

interface Citation {
  document_id: string;
  chunk_id: string;
  title: string;
  page_number: number | null;
  snippet: string;
  score: number;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  citations?: Citation[];
}

interface ErrorState {
  kind: "ai" | "other";
  msg: string;
}

export function DashboardHomeHero({ userName }: { userName: string }) {
  const t = useTranslations("dashboard.home");
  const locale = useLocale();
  const isAr = locale === "ar";
  const searchParams = useSearchParams();
  const router = useRouter();
  const urlConversationId = searchParams.get("c");
  const [greeting, setGreeting] = useState<string>("");
  const [value, setValue] = useState("");

  useEffect(() => {
    const hour = new Date().getHours();
    const isMorning = hour >= 5 && hour < 17;
    setGreeting(isMorning ? t("greetingMorning") : t("greetingEvening"));
  }, [t]);

  const sep = isAr ? "، " : ", ";

  // --- Inline conversation state -------------------------------------------
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ErrorState | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const heroRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll the thread when new messages arrive.
  useEffect(() => {
    if (!threadRef.current) return;
    threadRef.current.scrollTo({
      top: threadRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, busy]);

  // The rail's "+ محادثة جديدة" button dispatches this — we clear the
  // thread, scroll the hero into view, and put the cursor in the input so
  // the click never feels silent even when the thread was already empty.
  useEffect(() => {
    const onNew = () => {
      setMessages([]);
      setActiveId(null);
      setError(null);
      heroRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      // Defer focus until after the layout has settled — autofocus during
      // a scroll animation can yank the viewport unpredictably on some
      // browsers.
      window.setTimeout(() => inputRef.current?.focus(), 250);
    };
    window.addEventListener("conversation:new", onNew);
    return () => window.removeEventListener("conversation:new", onNew);
  }, []);

  // --- URL-driven conversation rehydration ---------------------------------
  // The Conversations rail writes `?c=<id>` when the user picks a past
  // thread. We observe it and fetch /conversations/<id>/messages, then
  // map server messages into the bubble shape. Empty / cleared param
  // resets the thread (used by the rail's "New conversation" button).
  useEffect(() => {
    if (!urlConversationId) {
      // Only reset if we currently *have* an active id — avoid clobbering
      // a brand-new in-flight conversation the user just started.
      if (activeId !== null) {
        setActiveId(null);
        setMessages([]);
        setError(null);
      }
      return;
    }
    if (urlConversationId === activeId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(
          `/api/v1/chat/conversations/${urlConversationId}/messages`,
          { cache: "no-store" }
        );
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as Array<{
          id: string;
          role: ChatMessage["role"];
          content: string;
          citations?: Citation[];
        }>;
        if (cancelled) return;
        setActiveId(urlConversationId);
        setMessages(
          data.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            citations: m.citations ?? [],
          }))
        );
        setError(null);
      } catch {
        /* swallow — the rail will let the user retry by re-selecting */
      }
    })();
    return () => {
      cancelled = true;
    };
    // We intentionally exclude activeId from deps — its update inside the
    // effect would re-trigger us. We only want to react to URL changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlConversationId]);

  // --- Options popover ------------------------------------------------------
  const [mode, setMode] = useState<AskMode>("ask");
  const [optionsOpen, setOptionsOpen] = useState(false);
  const optionsRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!optionsOpen) return;
    const onDown = (e: MouseEvent) => {
      if (!optionsRef.current?.contains(e.target as Node)) setOptionsOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [optionsOpen]);

  // --- File attach ---------------------------------------------------------
  const fileRef = useRef<HTMLInputElement>(null);
  const [attached, setAttached] = useState<AttachedFile[]>([]);

  function pickFiles() {
    fileRef.current?.click();
  }
  function onFilesPicked(e: React.ChangeEvent<HTMLInputElement>) {
    const fs = Array.from(e.target.files ?? []);
    if (fs.length === 0) return;
    setAttached((p) => [
      ...p,
      ...fs.map((f) => ({
        id: `${f.name}-${f.size}-${Math.random().toString(36).slice(2, 8)}`,
        file: f,
        status: "pending" as const,
      })),
    ]);
    e.target.value = "";
  }
  function removeAttached(id: string) {
    setAttached((p) => p.filter((a) => a.id !== id));
  }

  async function uploadAttachments(): Promise<string[]> {
    if (attached.length === 0) return [];
    const ids: string[] = [];
    setAttached((p) =>
      p.map((a) => (a.status === "pending" ? { ...a, status: "uploading" } : a)),
    );
    await Promise.all(
      attached.map(async (a) => {
        if (a.documentId) {
          ids.push(a.documentId);
          return;
        }
        const fd = new FormData();
        fd.append("file", a.file);
        try {
          const res = await fetch("/api/v1/documents", {
            method: "POST",
            body: fd,
          });
          if (!res.ok) throw new Error(await res.text());
          const data = (await res.json()) as { document: { id: string } };
          const docId = data.document.id;
          ids.push(docId);
          setAttached((p) =>
            p.map((x) =>
              x.id === a.id ? { ...x, status: "done", documentId: docId } : x,
            ),
          );
        } catch (err) {
          setAttached((p) =>
            p.map((x) =>
              x.id === a.id
                ? { ...x, status: "failed", error: (err as Error).message }
                : x,
            ),
          );
        }
      }),
    );
    return ids;
  }

  // --- Inline send: posts to /api/v1/chat/agent and renders the response ---
  const submit = useCallback(
    async (text?: string) => {
      const raw = (text ?? value).trim();
      if (!raw || busy) return;
      setBusy(true);
      setError(null);

      // Compose the actual message we send to the agent. Mode / attached
      // docs are encoded as inline annotations the way the chat workspace
      // forwards them via URL params.
      let docIds: string[] = [];
      try {
        docIds = await uploadAttachments();
      } catch {
        /* upload errors surface on the chips themselves */
      }
      let message = raw;
      if (mode === "search") message = `[search-mode] ${message}`;
      if (docIds.length > 0) {
        message += `\n\n[attached docs: ${docIds.join(",")}]`;
      }

      // Optimistic user bubble.
      const tempUser: ChatMessage = {
        id: `temp-${Date.now()}`,
        role: "user",
        content: raw,
      };
      setMessages((m) => [...m, tempUser]);
      setValue("");
      // Clear successfully-attached chips; keep failed ones so the user
      // can see what didn't upload.
      setAttached((p) => p.filter((a) => a.status === "failed"));

      try {
        const res = await fetch("/api/v1/chat/agent", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            conversation_id: activeId,
            message,
            locale,
          }),
        });
        if (!res.ok) {
          const text = await res.text();
          let detail = text;
          try {
            const j = JSON.parse(text);
            detail = j?.detail || text;
          } catch {
            /* keep raw */
          }
          const isAi =
            res.status === 502 ||
            String(detail).includes("AI provider") ||
            String(detail).includes("ChatGPT");
          setError({
            kind: isAi ? "ai" : "other",
            msg: String(detail) || `HTTP ${res.status}`,
          });
          return;
        }
        const data = (await res.json()) as {
          conversation_id: string;
          message: ChatMessage;
        };
        const wasNewConversation = activeId === null;
        setActiveId(data.conversation_id);
        setMessages((m) => [...m, data.message]);
        // Nudge the conversations rail to refetch so a brand-new thread
        // pops in immediately. Existing conversations don't need this —
        // only the title might update, which is acceptable as stale.
        if (wasNewConversation && typeof window !== "undefined") {
          window.dispatchEvent(new Event("conversations:refresh"));
        }
      } catch (err) {
        setError({
          kind: "other",
          msg: (err as Error).message || "Request failed",
        });
      } finally {
        setBusy(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [value, mode, attached, activeId, locale, busy],
  );

  const onFormSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    submit();
  };

  // --- Voice input ---------------------------------------------------------
  const voice = useVoiceInput(locale);
  const toggleMic = () => {
    if (voice.listening) {
      voice.stop();
    } else {
      voice.start({
        base: value,
        onTranscript: setValue,
        onFinish: (finalText) => {
          if (finalText.trim()) submit(finalText);
        },
      });
    }
  };

  function clearConversation() {
    setMessages([]);
    setActiveId(null);
    setError(null);
    // Also drop ?c=… from the URL so the rail's active highlight clears
    // and a reload doesn't snap back to the previous thread.
    if (urlConversationId) {
      const params = new URLSearchParams(Array.from(searchParams.entries()));
      params.delete("c");
      const qs = params.toString();
      const path =
        typeof window !== "undefined" ? window.location.pathname : "/dashboard";
      router.replace(qs ? `${path}?${qs}` : path, { scroll: false });
    }
  }

  const hasConversation = messages.length > 0 || busy;

  // Composer form JSX, shared between the empty hero and the
  // fixed-bottom chat layout. Defined as a variable (not a sub-component)
  // so refs and closures keep working without prop drilling.
  const composerJsx = (
    <form
      onSubmit={onFormSubmit}
      className={cn(
        "flex items-center gap-2 rounded-2xl bg-background/95",
        "border border-border/60 px-3 py-2.5 shadow-sm",
        "focus-within:ring-2 focus-within:ring-primary/30",
        voice.listening && "ring-2 ring-destructive/40 border-destructive/40"
      )}
    >
      <button
        type="submit"
        aria-label={t("send")}
        disabled={busy}
        className="grid place-items-center h-9 w-9 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shrink-0 disabled:opacity-60"
      >
        {busy ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <ArrowUp className="h-4 w-4" />
        )}
      </button>

      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={
          voice.listening
            ? isAr
              ? "أستمع إليك…"
              : "Listening…"
            : t("inputPlaceholder")
        }
        className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground text-end"
      />

      {voice.supported !== false && (
        <button
          type="button"
          onClick={toggleMic}
          aria-label={
            voice.listening
              ? isAr
                ? "إيقاف التسجيل"
                : "Stop voice input"
              : isAr
                ? "تحدث للمساعد"
                : "Speak to the assistant"
          }
          aria-pressed={voice.listening}
          className={cn(
            "grid place-items-center h-9 w-9 rounded-full transition-colors shrink-0 relative",
            voice.listening
              ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
              : "text-muted-foreground hover:bg-muted hover:text-foreground"
          )}
        >
          <Mic className="h-4 w-4" />
          {voice.listening && (
            <span className="pointer-events-none absolute inset-0 rounded-full ring-2 ring-destructive/40 animate-ping" />
          )}
        </button>
      )}

      {/* Options popover */}
      <div ref={optionsRef} className="relative">
        <button
          type="button"
          aria-label={t("options")}
          aria-expanded={optionsOpen}
          onClick={() => setOptionsOpen((v) => !v)}
          className={cn(
            "grid place-items-center h-9 w-9 rounded-full transition-colors shrink-0 relative",
            optionsOpen || mode !== "ask"
              ? "bg-primary/10 text-primary"
              : "text-muted-foreground hover:bg-muted hover:text-foreground"
          )}
        >
          <SlidersHorizontal className="h-4 w-4" />
          {mode !== "ask" && (
            <span className="absolute -top-0.5 -end-0.5 h-2 w-2 rounded-full bg-primary ring-2 ring-background" />
          )}
        </button>
        {optionsOpen && (
          <div
            className={cn(
              "absolute z-50 mt-2 w-64 rounded-xl border border-border bg-card shadow-2xl p-2 text-start",
              // In chat mode the popover should anchor above (not below) the
              // composer so it doesn't fall off the viewport bottom.
              hasConversation
                ? "bottom-full mb-2 start-1/2 -translate-x-1/2 sm:start-auto sm:end-0 sm:translate-x-0"
                : "start-1/2 -translate-x-1/2 sm:start-auto sm:end-0 sm:translate-x-0"
            )}
          >
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground px-2 py-1.5">
              {isAr ? "وضع السؤال" : "Ask mode"}
            </div>
            <OptionRow
              active={mode === "ask"}
              icon={MessageSquare}
              title={isAr ? "محادثة عادية" : "Conversation"}
              subtitle={
                isAr
                  ? "جواب من المساعد مباشرةً."
                  : "Direct assistant answer."
              }
              onClick={() => {
                setMode("ask");
                setOptionsOpen(false);
              }}
            />
            <OptionRow
              active={mode === "search"}
              icon={BookOpen}
              title={isAr ? "بحث في الوثائق" : "Search documents"}
              subtitle={
                isAr
                  ? "ابحث في الأنظمة السعودية ومستنداتك."
                  : "Search Saudi laws and your indexed docs."
              }
              onClick={() => {
                setMode("search");
                setOptionsOpen(false);
              }}
            />
          </div>
        )}
      </div>

      {/* Attach */}
      <button
        type="button"
        aria-label={t("attach")}
        onClick={pickFiles}
        className={cn(
          "grid place-items-center h-9 w-9 rounded-full transition-colors shrink-0 relative",
          attached.length > 0
            ? "bg-primary/10 text-primary"
            : "text-muted-foreground hover:bg-muted hover:text-foreground"
        )}
      >
        <Paperclip className="h-4 w-4" />
        {attached.length > 0 && (
          <span className="absolute -top-0.5 -end-0.5 min-w-[16px] h-4 px-1 rounded-full bg-primary text-primary-foreground text-[10px] font-medium grid place-items-center ring-2 ring-background">
            {attached.length}
          </span>
        )}
      </button>
      <input
        ref={fileRef}
        type="file"
        multiple
        accept=".pdf,.doc,.docx,.txt,.md,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
        className="hidden"
        onChange={onFilesPicked}
      />
    </form>
  );

  // ───── Conversation-active layout ─────
  //
  // Re-uses the same composer form / attached chips / mic-state strip as
  // the empty state — but flattens the gradient hero card and pins the
  // composer to the bottom of the viewport so the experience feels like
  // ChatGPT / Claude (compact action pills at top, scrollable thread,
  // sticky composer).
  if (hasConversation) {
    return (
      <div
        ref={heroRef as React.RefObject<HTMLDivElement>}
        className="space-y-4 pb-32 sm:pb-36"
      >
        {/* Tiles, now horizontal pills above the chat. */}
        <QuickActions compact />

        <div className="flex items-center justify-end text-xs text-muted-foreground">
          <button
            type="button"
            onClick={clearConversation}
            className="inline-flex items-center gap-1 hover:text-foreground"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            {isAr ? "محادثة جديدة" : "New conversation"}
          </button>
        </div>

        {/* Thread — no longer constrained to a small card; takes the
            container's max-w-6xl, then we max-w-3xl the inner column so
            lines don't get too wide for comfortable reading. */}
        <div
          ref={threadRef}
          className="mx-auto max-w-3xl space-y-5 text-start"
        >
          {messages.map((m) => (
            <Bubble key={m.id} message={m} isAr={isAr} userName={userName} />
          ))}
          {busy && <ThinkingRow isAr={isAr} />}

          {error && (
            <div
              className={cn(
                "rounded-xl border px-4 py-3 text-sm",
                error.kind === "ai"
                  ? "border-amber-500/30 bg-amber-500/5"
                  : "border-destructive/30 bg-destructive/5"
              )}
            >
              <div className="font-semibold">
                {error.kind === "ai"
                  ? isAr
                    ? "خدمة الذكاء الاصطناعي معطّلة مؤقتًا"
                    : "AI service temporarily unavailable"
                  : isAr
                    ? "تعذّر الإرسال"
                    : "Request failed"}
              </div>
              <p className="text-muted-foreground mt-0.5">
                {error.kind === "ai"
                  ? isAr
                    ? "انتهت صلاحية بيانات اعتماد المزود. تواصل مع مسؤول النظام لتحديثها."
                    : "The AI provider's credentials have expired. Ask your admin to refresh them."
                  : error.msg}
              </p>
            </div>
          )}
        </div>

        {/* Composer — fixed to the viewport bottom. Accounts for the nav
            rail on inline-start (md:start-20) and the conversations rail
            on inline-end (lg:end-20) so it never tucks under either. */}
        <div
          className={cn(
            "fixed bottom-0 start-0 end-0 z-20 md:start-20 lg:end-20",
            "border-t border-border/60 bg-card/95 backdrop-blur-md"
          )}
        >
          <div className="mx-auto max-w-3xl px-4 py-3 sm:px-6 sm:py-4 space-y-2">
            {/* Attached file chips — sit right above the form so the user
                can see what they're sending. */}
            {attached.length > 0 && (
              <ul className="flex flex-wrap gap-2 justify-end">
                {attached.map((a) => (
                  <li
                    key={a.id}
                    className={cn(
                      "inline-flex items-center gap-2 rounded-full border bg-background/95 ps-2 pe-1 py-1 text-xs shadow-sm",
                      a.status === "failed"
                        ? "border-destructive/30 text-destructive"
                        : a.status === "done"
                          ? "border-primary/30 text-foreground"
                          : "border-border/60 text-foreground"
                    )}
                    title={a.error ?? a.file.name}
                  >
                    {a.status === "uploading" ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : a.status === "done" ? (
                      <Check className="h-3 w-3 text-primary" />
                    ) : (
                      <FileText className="h-3 w-3 text-muted-foreground" />
                    )}
                    <span className="max-w-[180px] truncate" dir="ltr">
                      {a.file.name}
                    </span>
                    <span className="text-muted-foreground text-[10px] tabular-nums">
                      {formatBytes(a.file.size)}
                    </span>
                    <button
                      type="button"
                      aria-label={isAr ? "إزالة" : "Remove"}
                      onClick={() => removeAttached(a.id)}
                      className="grid h-5 w-5 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {(voice.error || voice.supported === false) && (
              <p className="text-xs text-destructive flex items-center justify-center gap-1.5">
                <MicOff className="h-3.5 w-3.5" />
                {voice.error ??
                  (isAr
                    ? "متصفحك لا يدعم الإدخال الصوتي. جرّب Chrome أو Edge."
                    : "Your browser doesn't support voice input. Try Chrome or Edge.")}
              </p>
            )}

            {composerJsx}
          </div>
        </div>
      </div>
    );
  }

  // ───── Empty state (no conversation yet) ─────
  return (
    <>
      <section
        ref={heroRef}
        className={cn(
          "relative rounded-3xl border border-border/60 bg-card overflow-hidden",
          "bg-gradient-emerald shadow-sm"
        )}
      >
      <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-3xl">
        <div className="absolute -top-24 -end-24 h-72 w-72 rounded-full bg-primary/15 blur-3xl" />
        <div className="absolute -bottom-32 -start-20 h-80 w-80 rounded-full bg-accent/10 blur-3xl" />
      </div>

      <div className="relative px-6 sm:px-10 text-center space-y-5 py-10 sm:py-14">
        <div className="space-y-2">
          <p className="inline-flex items-center gap-1.5 text-xs font-medium text-accent">
            <Sparkles className="h-3.5 w-3.5" />
            {greeting}
            {greeting && userName ? sep : ""}
            {userName}
          </p>
          <h1 className="font-bold tracking-tight text-3xl sm:text-4xl">
            {t("prompt")}
          </h1>
          <span className="block mx-auto gold-rule" />
        </div>

        <div className="mx-auto max-w-2xl">{composerJsx}</div>

        {/* Attached file chips — the user can attach files in the empty
            state too, before sending the first message. */}
        {attached.length > 0 && (
          <ul className="mx-auto max-w-2xl flex flex-wrap gap-2 justify-end">
            {attached.map((a) => (
              <li
                key={a.id}
                className={cn(
                  "inline-flex items-center gap-2 rounded-full border bg-background/95 ps-2 pe-1 py-1 text-xs shadow-sm",
                  a.status === "failed"
                    ? "border-destructive/30 text-destructive"
                    : a.status === "done"
                      ? "border-primary/30 text-foreground"
                      : "border-border/60 text-foreground"
                )}
                title={a.error ?? a.file.name}
              >
                {a.status === "uploading" ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : a.status === "done" ? (
                  <Check className="h-3 w-3 text-primary" />
                ) : (
                  <FileText className="h-3 w-3 text-muted-foreground" />
                )}
                <span className="max-w-[180px] truncate" dir="ltr">
                  {a.file.name}
                </span>
                <span className="text-muted-foreground text-[10px] tabular-nums">
                  {formatBytes(a.file.size)}
                </span>
                <button
                  type="button"
                  aria-label={isAr ? "إزالة" : "Remove"}
                  onClick={() => removeAttached(a.id)}
                  className="grid h-5 w-5 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  <X className="h-3 w-3" />
                </button>
              </li>
            ))}
          </ul>
        )}

        {(voice.error || voice.supported === false) && (
          <p className="mx-auto max-w-2xl text-xs text-destructive flex items-center justify-center gap-1.5">
            <MicOff className="h-3.5 w-3.5" />
            {voice.error ??
              (isAr
                ? "متصفحك لا يدعم الإدخال الصوتي. جرّب Chrome أو Edge."
                : "Your browser doesn't support voice input. Try Chrome or Edge.")}
          </p>
        )}

        {error && (
          <div
            className={cn(
              "mx-auto max-w-2xl rounded-xl border px-4 py-3 text-sm text-start",
              error.kind === "ai"
                ? "border-amber-500/30 bg-amber-500/5"
                : "border-destructive/30 bg-destructive/5"
            )}
          >
            <div className="font-semibold">
              {error.kind === "ai"
                ? isAr
                  ? "خدمة الذكاء الاصطناعي معطّلة مؤقتًا"
                  : "AI service temporarily unavailable"
                : isAr
                  ? "تعذّر الإرسال"
                  : "Request failed"}
            </div>
            <p className="text-muted-foreground mt-0.5">
              {error.kind === "ai"
                ? isAr
                  ? "انتهت صلاحية بيانات اعتماد المزود. تواصل مع مسؤول النظام لتحديثها."
                  : "The AI provider's credentials have expired. Ask your admin to refresh them."
                : error.msg}
            </p>
          </div>
        )}
      </div>
    </section>

      {/* Quick-create tiles below the hero — full-sized cards. */}
      <QuickActions />
    </>
  );
}

function Bubble({
  message,
  isAr,
  userName,
}: {
  message: ChatMessage;
  isAr: boolean;
  userName: string;
}) {
  const isUser = message.role === "user";

  // Two-letter avatar initials for the user; the assistant gets a fixed
  // sparkle/brand icon.
  const initials =
    (userName || (isAr ? "أنا" : "Me"))
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((w) => w[0]?.toUpperCase() ?? "")
      .join("") || (isAr ? "أ" : "M");

  return (
    <div
      className={cn(
        "flex gap-3 items-start",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "grid h-9 w-9 rounded-full place-items-center text-xs font-semibold shrink-0",
          isUser
            ? "bg-primary/15 text-primary ring-1 ring-primary/20"
            : "bg-gradient-to-br from-primary to-accent text-primary-foreground shadow-sm"
        )}
      >
        {isUser ? initials : <Sparkles className="h-4 w-4" />}
      </div>

      {/* Author + bubble column */}
      <div className={cn("min-w-0 flex-1", isUser ? "items-end" : "items-start")}>
        <div
          className={cn(
            "flex items-center gap-2 text-xs text-muted-foreground mb-1",
            isUser ? "justify-end" : "justify-start"
          )}
        >
          <span className="font-medium text-foreground/90">
            {isUser
              ? userName || (isAr ? "أنت" : "You")
              : isAr
                ? "مستشاري AI"
                : "Mostashari AI"}
          </span>
        </div>

        <div
          className={cn(
            "inline-block max-w-full rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm",
            isUser
              ? "bg-primary text-primary-foreground rounded-tr-sm"
              : "bg-muted text-foreground rounded-tl-sm border border-border/60"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          ) : (
            <div
              className={cn(
                "prose prose-sm dark:prose-invert max-w-none break-words",
                "[&>*:first-child]:mt-0 [&>*:last-child]:mb-0",
                "[&_pre]:bg-background/50 [&_pre]:border [&_pre]:border-border/60"
              )}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}
          {message.citations && message.citations.length > 0 && (
            <div className="mt-3 pt-2.5 border-t border-border/40 space-y-1">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground/80 flex items-center gap-1">
                <BookText className="h-3 w-3" />
                {isAr ? "المصادر" : "Citations"} · {message.citations.length}
              </div>
              <ul className="space-y-0.5">
                {message.citations.slice(0, 4).map((c) => (
                  <li
                    key={c.chunk_id}
                    className="text-[11px] text-muted-foreground truncate"
                    title={c.snippet}
                  >
                    · {c.title}
                    {c.page_number ? ` · p.${c.page_number}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** "Assistant is thinking" row — matches the bubble layout so the
 *  placeholder slots in naturally above the eventual reply. */
function ThinkingRow({ isAr }: { isAr: boolean }) {
  return (
    <div className="flex gap-3 items-start">
      <div className="grid h-9 w-9 rounded-full place-items-center bg-gradient-to-br from-primary to-accent text-primary-foreground shadow-sm shrink-0">
        <Sparkles className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-xs text-muted-foreground mb-1 font-medium text-foreground/90">
          {isAr ? "مستشاري AI" : "Mostashari AI"}
        </div>
        <div className="inline-flex items-center gap-2 rounded-2xl rounded-tl-sm border border-border/60 bg-muted px-4 py-3 text-sm text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          {isAr ? "يفكر…" : "Thinking…"}
        </div>
      </div>
    </div>
  );
}

function OptionRow({
  active,
  icon: Icon,
  title,
  subtitle,
  onClick,
}: {
  active: boolean;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  subtitle: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full flex items-start gap-3 px-2 py-2 rounded-lg transition-colors text-start",
        active ? "bg-primary/[0.08]" : "hover:bg-muted/50"
      )}
    >
      <div
        className={cn(
          "grid h-7 w-7 place-items-center rounded-md shrink-0",
          active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
        )}
      >
        <Icon className="h-3.5 w-3.5" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium leading-tight">{title}</div>
        <div className="text-xs text-muted-foreground mt-0.5 leading-snug">
          {subtitle}
        </div>
      </div>
      {active && <Check className="h-4 w-4 text-primary shrink-0 mt-1" />}
    </button>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
