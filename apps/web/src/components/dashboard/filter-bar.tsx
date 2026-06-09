"use client";

/**
 * Reusable filter row used on every dashboard list page (clients, cases,
 * tasks, hearings, contacts, documents). Composes:
 *
 *   - a free-text search input
 *   - any number of chip groups (segmented controls) — colored or neutral
 *   - an optional sort dropdown
 *   - counter line + reset link
 *
 * Each page owns its filter state — this component is purely
 * presentational. The chip groups are typed as `string` so callers can
 * still narrow at the call site if they want.
 */
import { Search, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface ChipOption<V extends string = string> {
  value: V;
  label: string;
  /** Tailwind classes applied when this chip is active. */
  activeClassName?: string;
  /** Optional icon component shown before the label when active. */
  icon?: React.ComponentType<{ className?: string }>;
}

export interface ChipGroup<V extends string = string> {
  label?: string;
  value: V;
  onChange: (v: V) => void;
  options: ChipOption<V>[];
}

export interface SortOption<V extends string = string> {
  value: V;
  label: string;
}

export function FilterBar<S extends string = string>({
  query,
  onQueryChange,
  placeholder,
  chipGroups,
  sort,
  onSortChange,
  sortOptions,
  totalCount,
  filteredCount,
  hasFilters,
  onReset,
  isAr,
  noun,
}: {
  query: string;
  onQueryChange: (v: string) => void;
  placeholder: string;
  chipGroups: ChipGroup[];
  sort?: S;
  onSortChange?: (v: S) => void;
  sortOptions?: SortOption<S>[];
  totalCount: number;
  filteredCount: number;
  hasFilters: boolean;
  onReset: () => void;
  isAr: boolean;
  /** Singular noun used in the counter ("client" / "case" / …). */
  noun: { singular: string; plural: string };
}) {
  const chipCount = chipGroups.length;
  const sortCount = sortOptions && sortOptions.length > 0 ? 1 : 0;
  // Build a dynamic grid so the search input grows and chips/sort sit
  // beside it on wide screens; everything stacks on mobile.
  const grid = `md:grid-cols-[1fr${"_auto".repeat(chipCount + sortCount)}]`;

  return (
    <div className="space-y-3">
      <div className={cn("grid grid-cols-1 gap-2", grid)}>
        <div className="relative">
          <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder={placeholder}
            className="ps-9 pe-9"
          />
          {query && (
            <button
              type="button"
              onClick={() => onQueryChange("")}
              aria-label={isAr ? "مسح البحث" : "Clear search"}
              className="absolute end-2 top-1/2 -translate-y-1/2 grid h-6 w-6 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>

        {chipGroups.map((g, i) => (
          <ChipRow key={i} group={g} />
        ))}

        {sortOptions && sortOptions.length > 0 && (
          <select
            value={sort}
            onChange={(e) => onSortChange?.(e.target.value as S)}
            className="h-10 px-3 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {sortOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
        <span>
          {filteredCount === totalCount
            ? isAr
              ? `${totalCount} ${noun.plural}`
              : `${totalCount} ${totalCount === 1 ? noun.singular : noun.plural}`
            : isAr
              ? `${filteredCount} من ${totalCount}`
              : `${filteredCount} of ${totalCount}`}
        </span>
        {hasFilters && (
          <button
            type="button"
            onClick={onReset}
            className="hover:text-foreground underline-offset-4 hover:underline"
          >
            {isAr ? "مسح المرشحات" : "Reset filters"}
          </button>
        )}
      </div>
    </div>
  );
}

function ChipRow({ group }: { group: ChipGroup }) {
  return (
    <div
      role="radiogroup"
      aria-label={group.label}
      className="inline-flex h-10 items-center rounded-md border border-input bg-background p-0.5 overflow-x-auto"
    >
      {group.options.map((o) => {
        const active = o.value === group.value;
        const Icon = o.icon;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => group.onChange(o.value)}
            className={cn(
              "h-full px-2.5 text-xs font-medium rounded-sm transition-colors whitespace-nowrap inline-flex items-center gap-1.5",
              active
                ? cn(
                    "shadow-sm",
                    o.activeClassName ?? "bg-primary/10 text-primary"
                  )
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {Icon && active && <Icon className="h-3.5 w-3.5" />}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
