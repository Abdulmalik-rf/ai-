"use client";

import { useTranslations, useLocale } from "next-intl";
import { Check, Plus, X } from "lucide-react";
import { useMemo, useState, useTransition } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { FilterBar, type ChipGroup } from "@/components/dashboard/filter-bar";
import { formatDate, cn } from "@/lib/utils";

const STATUSES = ["open", "in_progress", "blocked", "completed"] as const;
type Status = (typeof STATUSES)[number];
type Priority = "low" | "medium" | "high" | "urgent";

interface Task {
  id: string;
  title: string;
  description: string | null;
  status: Status | "cancelled";
  priority: Priority;
  case_id: string | null;
  assignee_id: string | null;
  due_date: string | null;
  created_at: string;
}

interface CaseRef {
  id: string;
  reference: string;
  title: string;
}

interface StaffRef {
  id: string;
  full_name: string;
}

export function TasksWorkspace({
  initialTasks,
  cases,
  staff,
}: {
  initialTasks: Task[];
  cases: CaseRef[];
  staff: StaffRef[];
}) {
  const t = useTranslations("dashboard.crm.tasks");
  const tCommon = useTranslations("dashboard.crm.common");
  const locale = useLocale();
  const [tasks, setTasks] = useState<Task[]>(initialTasks);
  const [showCreate, setShowCreate] = useState(false);
  const [, startTransition] = useTransition();
  const isAr = locale === "ar";

  // --- Filters (search + priority + case) ---------------------------------
  const [query, setQuery] = useState("");
  const [priorityFilter, setPriorityFilter] = useState<"all" | Priority>("all");
  const [caseFilter, setCaseFilter] = useState<string>("all");
  const [mineOnly, setMineOnly] = useState<"all" | "mine">("all");

  const filteredTasks = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tasks.filter((t) => {
      if (priorityFilter !== "all" && t.priority !== priorityFilter) return false;
      if (caseFilter !== "all" && t.case_id !== caseFilter) return false;
      if (mineOnly === "mine" && !t.assignee_id) return false; // soft "assigned"
      if (q) {
        const hay = `${t.title} ${t.description ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [tasks, query, priorityFilter, caseFilter, mineOnly]);

  const grouped = STATUSES.reduce<Record<Status, Task[]>>(
    (acc, s) => {
      acc[s] = filteredTasks.filter((task) => task.status === s);
      return acc;
    },
    { open: [], in_progress: [], blocked: [], completed: [] }
  );

  async function markComplete(taskId: string) {
    const res = await fetch(`/api/v1/tasks/${taskId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "completed" }),
    });
    if (res.ok) {
      const updated = (await res.json()) as Task;
      setTasks((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    }
  }

  async function deleteTask(taskId: string) {
    const res = await fetch(`/api/v1/tasks/${taskId}`, { method: "DELETE" });
    if (res.ok) {
      setTasks((prev) => prev.filter((p) => p.id !== taskId));
    }
  }

  function handleCreated(task: Task) {
    setTasks((prev) => [task, ...prev]);
    setShowCreate(false);
  }

  const chipGroups: ChipGroup[] = [
    {
      value: priorityFilter,
      onChange: (v) => setPriorityFilter(v as typeof priorityFilter),
      options: [
        { value: "all", label: isAr ? "كل الأولويات" : "All priorities" },
        {
          value: "urgent",
          label: isAr ? "عاجلة" : "Urgent",
          activeClassName: "bg-red-100 text-red-900 dark:bg-red-900/30 dark:text-red-200",
        },
        {
          value: "high",
          label: isAr ? "عالية" : "High",
          activeClassName: "bg-orange-100 text-orange-900 dark:bg-orange-900/30 dark:text-orange-200",
        },
        { value: "medium", label: isAr ? "متوسطة" : "Medium" },
        { value: "low", label: isAr ? "منخفضة" : "Low" },
      ],
    },
    {
      value: mineOnly,
      onChange: (v) => setMineOnly(v as typeof mineOnly),
      options: [
        { value: "all", label: isAr ? "الكل" : "All" },
        { value: "mine", label: isAr ? "مُسندة" : "Assigned" },
      ],
    },
  ];

  return (
    <>
      <FilterBar
        query={query}
        onQueryChange={setQuery}
        placeholder={isAr ? "ابحث في المهام…" : "Search tasks…"}
        chipGroups={chipGroups}
        totalCount={tasks.length}
        filteredCount={filteredTasks.length}
        hasFilters={
          query.trim() !== "" ||
          priorityFilter !== "all" ||
          caseFilter !== "all" ||
          mineOnly !== "all"
        }
        onReset={() => {
          setQuery("");
          setPriorityFilter("all");
          setCaseFilter("all");
          setMineOnly("all");
        }}
        isAr={isAr}
        noun={{ singular: "task", plural: isAr ? "مهام" : "tasks" }}
      />

      {/* Case filter as a discrete dropdown — long list */}
      {cases.length > 0 && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{isAr ? "القضية:" : "Case:"}</span>
          <select
            value={caseFilter}
            onChange={(e) => setCaseFilter(e.target.value)}
            className="h-8 px-2 rounded-md border border-input bg-background text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="all">{isAr ? "كل القضايا" : "All cases"}</option>
            {cases.map((c) => (
              <option key={c.id} value={c.id}>
                {c.reference} — {c.title.slice(0, 40)}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4 me-1" /> {t("new")}
        </Button>
      </div>

      {showCreate && (
        <CreateTaskCard
          cases={cases}
          staff={staff}
          onCancel={() => setShowCreate(false)}
          onCreated={(task) => startTransition(() => handleCreated(task))}
        />
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {STATUSES.map((status) => (
          <Card key={status} className="p-4 flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold capitalize">{t(`byStatus.${status}`)}</h2>
              <span className="text-xs text-muted-foreground tabular-nums">
                {grouped[status].length}
              </span>
            </div>
            <ul className="space-y-2 flex-1 min-h-[60px]">
              {grouped[status].length === 0 && (
                <li className="text-xs text-muted-foreground py-4 text-center">—</li>
              )}
              {grouped[status].map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  cases={cases}
                  staff={staff}
                  onComplete={() => markComplete(task.id)}
                  onDelete={() => deleteTask(task.id)}
                  locale={locale}
                  tMarkComplete={t("markComplete")}
                  tDelete={tCommon("delete")}
                />
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </>
  );
}


function TaskCard({
  task,
  cases,
  staff,
  onComplete,
  onDelete,
  locale,
  tMarkComplete,
  tDelete,
}: {
  task: Task;
  cases: CaseRef[];
  staff: StaffRef[];
  onComplete: () => void;
  onDelete: () => void;
  locale: string;
  tMarkComplete: string;
  tDelete: string;
}) {
  const matchedCase = cases.find((c) => c.id === task.case_id);
  const assignee = task.assignee_id
    ? staff.find((s) => s.id === task.assignee_id)
    : null;
  return (
    <li className="rounded-md border bg-card p-3 text-sm space-y-1.5 group">
      <div className="flex items-start justify-between gap-2">
        <p className="font-medium leading-snug">{task.title}</p>
        <PriorityBadge priority={task.priority} />
      </div>
      {matchedCase && (
        <p className="text-xs text-muted-foreground truncate">
          {matchedCase.reference} · {matchedCase.title}
        </p>
      )}
      {assignee && (
        <p className="text-xs text-muted-foreground truncate">👤 {assignee.full_name}</p>
      )}
      {task.due_date && (
        <p className="text-xs text-muted-foreground">📅 {formatDate(task.due_date, locale)}</p>
      )}
      <div className="flex gap-2 pt-1 opacity-0 group-hover:opacity-100 transition-opacity">
        {task.status !== "completed" && (
          <button
            onClick={onComplete}
            className="text-xs text-primary hover:underline"
          >
            ✓ {tMarkComplete}
          </button>
        )}
        <button
          onClick={onDelete}
          className="text-xs text-destructive hover:underline ms-auto"
        >
          {tDelete}
        </button>
      </div>
    </li>
  );
}


function CreateTaskCard({
  cases,
  staff,
  onCancel,
  onCreated,
}: {
  cases: CaseRef[];
  staff: StaffRef[];
  onCancel: () => void;
  onCreated: (task: Task) => void;
}) {
  const t = useTranslations("dashboard.crm.tasks");
  const tCommon = useTranslations("dashboard.crm.common");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [caseId, setCaseId] = useState("");
  const [assigneeId, setAssigneeId] = useState("");
  const [priority, setPriority] = useState<Priority>("medium");
  const [dueDate, setDueDate] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          description: description || null,
          case_id: caseId || null,
          assignee_id: assigneeId || null,
          priority,
          due_date: dueDate || null,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `HTTP ${res.status}`);
      }
      const task = (await res.json()) as Task;
      onCreated(task);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <Card className="p-5">
      <form onSubmit={submit} className="space-y-3">
        <h3 className="font-semibold">{t("createTitle")}</h3>
        <Input
          placeholder={t("fieldTitle")}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          autoFocus
        />
        <Textarea
          placeholder={t("fieldDescription")}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as Priority)}
            className="rounded-md border bg-background px-3 py-2 text-sm"
            aria-label={t("fieldPriority")}
          >
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
            <option value="urgent">urgent</option>
          </select>
          <select
            value={caseId}
            onChange={(e) => setCaseId(e.target.value)}
            className="rounded-md border bg-background px-3 py-2 text-sm"
            aria-label={t("fieldCase")}
          >
            <option value="">— {t("fieldCase")} —</option>
            {cases.map((c) => (
              <option key={c.id} value={c.id}>
                {c.reference} · {c.title.slice(0, 40)}
              </option>
            ))}
          </select>
          <select
            value={assigneeId}
            onChange={(e) => setAssigneeId(e.target.value)}
            className="rounded-md border bg-background px-3 py-2 text-sm"
            aria-label={t("fieldAssignee")}
            disabled={staff.length === 0}
          >
            <option value="">
              {staff.length === 0
                ? t("fieldAssigneeNoStaff")
                : t("fieldAssigneeNone")}
            </option>
            {staff.map((s) => (
              <option key={s.id} value={s.id}>
                {s.full_name}
              </option>
            ))}
          </select>
          <Input
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            aria-label={t("fieldDue")}
          />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="flex gap-2 justify-end">
          <Button type="button" variant="outline" size="sm" onClick={onCancel}>
            {tCommon("cancel")}
          </Button>
          <Button type="submit" size="sm" disabled={pending}>
            {pending ? "…" : tCommon("create")}
          </Button>
        </div>
      </form>
    </Card>
  );
}


function PriorityBadge({ priority }: { priority: Priority }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "text-[10px] uppercase tracking-wider",
        priority === "urgent" && "border-destructive text-destructive",
        priority === "high" && "border-orange-500 text-orange-600 dark:text-orange-400",
        priority === "low" && "text-muted-foreground"
      )}
    >
      {priority}
    </Badge>
  );
}
