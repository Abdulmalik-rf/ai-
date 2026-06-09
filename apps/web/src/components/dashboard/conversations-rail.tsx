"use client";

/**
 * Conversations history rail — mirrors the main sidebar's behavior on the
 * opposite edge: an icon-only column at rest (5rem wide), expands to 18rem
 * on hover via `group-hover`. Fixed-positioned so expansion overlays the
 * main content instead of pushing it (no layout shift).
 *
 * Placement:
 *   - `end-0` puts the rail on the inline-end side of the viewport, which
 *     is the visual LEFT in Arabic/RTL and the visual right in LTR.
 *   - `top-16 bottom-0` keeps it below the topbar so its expansion never
 *     covers the user-menu / theme-toggle controls in the topbar's end
 *     edge.
 *
 * Behavior:
 *   - URL is the source of truth. Selecting a row writes `?c=<id>`; the
 *     home hero observes the param and rehydrates the thread from
 *     `/v1/chat/conversations/<id>/messages`.
 *   - The "+ محادثة جديدة" header strips the param to start fresh.
 *   - The list refetches on window focus and on the custom
 *     `conversations:refresh` event the hero dispatches after a brand-new
 *     thread is created. No polling.
 */
import { MessageSquare, Plus } from "lucide-react";
import { useLocale } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { cn } from "@/lib/utils";

interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export function ConversationsRail() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const locale = useLocale();
  const isAr = locale === "ar";
  const activeId = searchParams.get("c");

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/chat/conversations?limit=50", {
        cache: "no-store",
      });
      if (!res.ok) return;
      const data = (await res.json()) as Conversation[];
      setConversations(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const onFocus = () => load();
    const onCustom = () => load();
    window.addEventListener("focus", onFocus);
    window.addEventListener("conversations:refresh", onCustom);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("conversations:refresh", onCustom);
    };
  }, [load]);

  function select(id: string | null) {
    const params = new URLSearchParams(Array.from(searchParams.entries()));
    if (id) params.set("c", id);
    else params.delete("c");
    const qs = params.toString();
    // Use the *full* path so the replace is unambiguous. A bare `?` href
    // sometimes failed to re-fire useSearchParams() in the hero — pinning
    // the pathname forces a clean param swap every time.
    const path =
      typeof window !== "undefined" ? window.location.pathname : "/dashboard";
    router.replace(qs ? `${path}?${qs}` : path, { scroll: false });

    // Clearing the selection means "I want to start a new conversation."
    // Tell the hero so it focuses the composer + scrolls to the top, even
    // if its thread was already empty (so the button never feels silent).
    if (id === null && typeof window !== "undefined") {
      window.dispatchEvent(new Event("conversation:new"));
    }
  }

  return (
    <aside
      // `group/conv-rail` lets every child opt-in to "fade in only when the
      // user is hovering the rail" — same trick the main sidebar uses.
      className={cn(
        "group/conv-rail fixed top-16 end-0 bottom-0 z-20 hidden lg:flex",
        "w-20 hover:w-72 focus-within:w-72",
        "transition-[width] duration-300 ease-out",
        "flex-col border-s border-border/60 bg-card/80 backdrop-blur-md",
        "shadow-sm hover:shadow-xl overflow-hidden"
      )}
      aria-label={isAr ? "المحادثات السابقة" : "Previous conversations"}
    >
      {/* New conversation — icon-only when collapsed, full pill on hover. */}
      <div className="p-3 border-b border-border/60">
        <button
          type="button"
          onClick={() => select(null)}
          title={isAr ? "محادثة جديدة" : "New conversation"}
          className={cn(
            "w-full flex items-center gap-3 rounded-xl px-3 py-2.5",
            "bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm"
          )}
        >
          <Plus className="h-5 w-5 shrink-0" />
          <span
            className={cn(
              "text-sm font-medium whitespace-nowrap",
              "opacity-0 group-hover/conv-rail:opacity-100 transition-opacity duration-200"
            )}
          >
            {isAr ? "محادثة جديدة" : "New conversation"}
          </span>
        </button>
      </div>

      {/* Section label only makes sense once expanded. */}
      <div
        className={cn(
          "px-3 py-2 text-[11px] uppercase tracking-wider text-muted-foreground whitespace-nowrap",
          "opacity-0 group-hover/conv-rail:opacity-100 transition-opacity duration-200"
        )}
      >
        {isAr ? "السابقة" : "Recent"}
      </div>

      <div className="flex-1 overflow-y-auto overflow-x-hidden px-3 pb-3 space-y-1">
        {loading ? (
          <ListSkeleton />
        ) : conversations.length === 0 ? (
          <EmptyState isAr={isAr} />
        ) : (
          conversations.map((c) => (
            <ConversationRow
              key={c.id}
              conversation={c}
              active={activeId === c.id}
              isAr={isAr}
              onClick={() => select(c.id)}
            />
          ))
        )}
      </div>
    </aside>
  );
}

function ConversationRow({
  conversation,
  active,
  isAr,
  onClick,
}: {
  conversation: Conversation;
  active: boolean;
  isAr: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={conversation.title || (isAr ? "بدون عنوان" : "Untitled")}
      className={cn(
        "w-full flex items-center gap-3 rounded-lg p-2 transition-colors text-start",
        "border border-transparent",
        active
          ? "bg-primary/10 border-primary/20"
          : "hover:bg-muted"
      )}
    >
      {/* The icon is the only thing visible when the rail is collapsed —
          colored when active so the user can still tell which thread is
          loaded into the hero even without expanding. */}
      <div
        className={cn(
          "grid place-items-center h-9 w-9 rounded-lg shrink-0 transition-colors",
          active
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-muted-foreground"
        )}
      >
        <MessageSquare className="h-4 w-4" />
      </div>
      <div
        className={cn(
          "flex-1 min-w-0",
          "opacity-0 group-hover/conv-rail:opacity-100 transition-opacity duration-200"
        )}
      >
        <div className="text-sm font-medium truncate">
          {conversation.title || (isAr ? "بدون عنوان" : "Untitled")}
        </div>
        <div className="text-[11px] text-muted-foreground truncate">
          {formatRelative(conversation.updated_at, isAr)}
        </div>
      </div>
    </button>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-1.5 py-1">
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-3 p-2 animate-pulse"
          style={{ animationDelay: `${i * 80}ms` }}
        >
          <div className="h-9 w-9 rounded-lg bg-muted shrink-0" />
          <div
            className={cn(
              "flex-1 min-w-0 space-y-1.5",
              "opacity-0 group-hover/conv-rail:opacity-100 transition-opacity duration-200"
            )}
          >
            <div className="h-3 w-3/4 rounded bg-muted" />
            <div className="h-2.5 w-1/3 rounded bg-muted/70" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState({ isAr }: { isAr: boolean }) {
  return (
    <div
      className={cn(
        "py-8 px-2 text-center text-xs text-muted-foreground leading-relaxed",
        "opacity-0 group-hover/conv-rail:opacity-100 transition-opacity duration-200 whitespace-normal"
      )}
    >
      <MessageSquare className="h-5 w-5 mx-auto mb-2 opacity-60" />
      {isAr
        ? "ستظهر محادثاتك هنا بمجرد بدئها."
        : "Your conversations will appear here once you start one."}
    </div>
  );
}

function formatRelative(iso: string, isAr: boolean): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diff = Math.max(0, now - then);
  const minutes = Math.floor(diff / 60_000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (minutes < 1) return isAr ? "الآن" : "Just now";
  if (minutes < 60) return isAr ? `قبل ${minutes} د` : `${minutes}m ago`;
  if (hours < 24) return isAr ? `قبل ${hours} س` : `${hours}h ago`;
  if (days < 7) return isAr ? `قبل ${days} ي` : `${days}d ago`;
  return new Date(iso).toLocaleDateString(isAr ? "ar-SA" : "en-US", {
    month: "short",
    day: "numeric",
  });
}
