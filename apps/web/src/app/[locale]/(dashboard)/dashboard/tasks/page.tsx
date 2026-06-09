import { getTranslations } from "next-intl/server";
import { Suspense } from "react";

import { TasksWorkspace } from "@/components/dashboard/tasks-workspace";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/session";

interface Task {
  id: string;
  title: string;
  description: string | null;
  status: "open" | "in_progress" | "blocked" | "completed" | "cancelled";
  priority: "low" | "medium" | "high" | "urgent";
  case_id: string | null;
  client_id: string | null;
  assignee_id: string | null;
  due_date: string | null;
  reminder_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

interface CaseRef {
  id: string;
  reference: string;
  title: string;
}

interface StaffRef {
  id: string;
  full_name: string;
  is_active: boolean;
}

export default async function TasksPage() {
  const t = await getTranslations("dashboard.crm.tasks");

  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
      </header>
      <Suspense fallback={<TasksSkeleton />}>
        <TasksBoard />
      </Suspense>
    </div>
  );
}

async function TasksBoard() {
  const token = await getAccessToken();

  let tasks: Task[] = [];
  let cases: CaseRef[] = [];
  let staff: StaffRef[] = [];
  try {
    [tasks, cases, staff] = await Promise.all([
      api<Task[]>("/v1/tasks?limit=200", { token }),
      api<CaseRef[]>("/v1/cases?limit=200", { token }),
      api<StaffRef[]>("/v1/team/users", { token }),
    ]);
  } catch {
    // first run, no auth, or DB hiccup — show empty board
  }

  return (
    <TasksWorkspace
      initialTasks={tasks}
      cases={cases}
      staff={staff.filter((s) => s.is_active)}
    />
  );
}

function TasksSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="rounded-lg border bg-card h-64" />
      ))}
    </div>
  );
}
