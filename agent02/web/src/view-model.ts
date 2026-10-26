import type { Task, ToolCall } from "./api";

export const statuses: Record<string, string> = {
  CREATED: "已创建", RUNNING: "执行中", WAITING_TOOL: "等待工具", WAITING_APPROVAL: "待审批",
  COMPLETED: "已完成", FAILED: "执行失败", TIMEOUT: "执行超时",
};

export const toolNames: Record<string, string> = {
  knowledge: "企业知识检索", calculator: "数值计算", calendar: "工作日规划", task: "创建任务",
  search: "信息搜索", mcp_company_policy: "企业制度查询", failure_demo: "故障恢复演示",
};

export function titleOf(task: Task): string {
  return task.message || String(task.tool_calls.find(call => typeof call.arguments.title === "string")?.arguments.title || task.answer || "未命名任务");
}

export function executionOf(task: Task, call: ToolCall) {
  const result = [...task.tool_results].reverse().find(item => item.call_id === call.call_id);
  if (result) return { status: result.success ? "success" : "failed", label: result.success ? "已执行" : "调用失败", result };
  const pending = task.tool_calls[task.current_step]?.call_id === call.call_id;
  if (pending && task.status === "WAITING_APPROVAL") return { status: "waiting", label: "待审批", result };
  if (pending && ["RUNNING", "WAITING_TOOL"].includes(task.status)) return { status: "running", label: "执行中", result };
  return { status: "pending", label: "未执行", result };
}

export type TaskFilter = "all" | "approval" | "failed" | "completed" | "running";
export function filterTasks(tasks: Task[], filter: TaskFilter, query: string): Task[] {
  const text = query.trim().toLocaleLowerCase();
  return tasks.filter(task => {
    const match = filter === "all"
      || (filter === "approval" && task.status === "WAITING_APPROVAL")
      || (filter === "failed" && ["FAILED", "TIMEOUT"].includes(task.status))
      || (filter === "completed" && task.status === "COMPLETED")
      || (filter === "running" && ["CREATED", "RUNNING", "WAITING_TOOL"].includes(task.status));
    return match && (!text || `${titleOf(task)} ${task.task_id} ${task.answer}`.toLocaleLowerCase().includes(text));
  });
}

export function taskStats(tasks: Task[]) {
  const completed = tasks.filter(task => task.status === "COMPLETED").length;
  const failed = tasks.filter(task => ["FAILED", "TIMEOUT"].includes(task.status) && task.error?.error_type !== "approval_rejected").length;
  const waiting = tasks.filter(task => task.status === "WAITING_APPROVAL").length;
  const settled = completed + failed;
  return { completed, failed, waiting, successRate: settled ? Math.round(100 * completed / settled) : null };
}

export function safeSourceUrl(value: unknown): string | undefined {
  if (typeof value !== "string") return;
  try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) ? url.href : undefined; } catch { return; }
}

export function formatTime(value?: string, withDate = true): string {
  if (!value) return "刚刚";
  const normalized = /T\d{2}:\d{2}/.test(value) && !/Z$|[+-]\d{2}:\d{2}$/.test(value) ? `${value}Z` : value;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return "时间未知";
  return new Intl.DateTimeFormat("zh-CN", { ...(withDate ? { month: "2-digit", day: "2-digit" } : {}), hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
}
