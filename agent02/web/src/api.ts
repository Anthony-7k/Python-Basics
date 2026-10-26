export type Role = "viewer" | "operator" | "approver" | "admin";

export interface ToolCall {
  call_id: string;
  name: string;
  arguments: Record<string, unknown>;
  selection_reason: string;
}

export interface ToolResult {
  call_id: string;
  tool_name: string;
  success: boolean;
  data: Record<string, unknown>;
  sources: Array<Record<string, unknown>>;
  error?: { error_type: string; message: string; retryable: boolean } | null;
  latency_ms: number;
  retry_count: number;
}

export interface Task {
  request_id: string;
  task_id: string;
  session_id: string;
  status: string;
  message?: string;
  answer: string;
  sources: Array<Record<string, unknown>>;
  tool_calls: ToolCall[];
  tool_results: ToolResult[];
  current_step: number;
  max_steps: number;
  error?: { error_type: string; message: string; retryable: boolean } | null;
  token_usage?: { input_tokens: number | null; output_tokens: number | null };
  created_at?: string;
  updated_at?: string;
}

export interface Workspace {
  subject: string;
  tenant_id: string;
  roles: Role[];
  permissions: string[];
  environment: string;
  planner_mode: string;
  knowledge_backend: string;
}

export interface StreamEvent {
  type: string;
  data: Record<string, unknown>;
  receivedAt?: number;
}

const errorMessages: Record<string, string> = {
  missing_token: "请登录后再操作。",
  invalid_token: "登录已过期，请重新登录。",
  permission_denied: "当前角色没有此操作权限，请切换到有权限的账号。",
  task_not_found: "任务不存在或已不可访问，请刷新任务列表。",
  invalid_task_state: "任务状态已发生变化，请刷新详情后再操作。",
  internal_server_error: "服务暂时无法完成请求，请稍后重试。",
  llm_timeout: "模型响应超时，可以从任务详情尝试恢复。",
  llm_connection_error: "暂时无法连接模型服务，请检查连接后重试。",
  llm_rate_limited: "模型请求过于频繁，请稍后恢复任务。",
  llm_http_401: "模型服务认证失败，请检查服务端的模型配置。",
  approval_rejected: "该操作已被审批人拒绝。",
};

export class ApiError extends Error {
  constructor(message: string, public status: number, public code: string, public requestId?: string) {
    super(message);
    this.name = "ApiError";
  }
}

export function friendlyError(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  if (cause instanceof TypeError) return "暂时无法连接服务，请检查网络后重试。";
  if (cause instanceof Error && cause.name === "TimeoutError") return "请求超时，请刷新任务确认执行状态，避免重复提交。";
  return cause instanceof Error ? cause.message : "操作失败，请稍后重试。";
}

export function errorDescription(code?: string, fallback?: string): string {
  return (code && errorMessages[code]) || fallback || "执行出现问题，请查看详细信息。";
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const code = body.detail?.error ?? body.error ?? `http_${response.status}`;
    let message = errorMessages[code];
    if (!message && response.status === 422) message = "填写内容不符合要求，请检查任务长度、日期和参数格式。";
    if (!message && response.status === 404) message = "服务接口暂不可用，请确认后端已更新并启动。";
    throw new ApiError(message || "请求失败，请稍后重试。", response.status, code, body.request_id ?? response.headers.get("X-Request-ID") ?? undefined);
  }
  return response.json() as Promise<T>;
}

// Handles CRLF, multi-line data, split UTF-8 chunks and final un-delimited events.
export class EventStreamDecoder {
  private buffer = "";
  private decoder = new TextDecoder();

  read(chunk?: Uint8Array, done = false): StreamEvent[] {
    this.buffer += this.decoder.decode(chunk, { stream: !done });
    const blocks: string[] = [];
    let match: RegExpExecArray | null;
    while ((match = /\r?\n\r?\n/.exec(this.buffer)) !== null) {
      blocks.push(this.buffer.slice(0, match.index));
      this.buffer = this.buffer.slice(match.index + match[0].length);
    }
    if (done && this.buffer.trim()) { blocks.push(this.buffer); this.buffer = ""; }
    return blocks.flatMap((block) => {
      let type = "message";
      const data: string[] = [];
      for (const line of block.split(/\r?\n/)) {
        if (line.startsWith("event:")) type = line.slice(6).trim();
        if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
      }
      if (!data.length) return [];
      return [{ type, data: JSON.parse(data.join("\n")) as Record<string, unknown>, receivedAt: Date.now() }];
    });
  }
}

export class ApiClient {
  constructor(private token: string, private signal?: AbortSignal) {}

  private async request<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(`/api/v2${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { Authorization: `Bearer ${this.token}`, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: this.signal ? AbortSignal.any([this.signal, AbortSignal.timeout(30000)]) : AbortSignal.timeout(30000),
    });
    return parseResponse<T>(response);
  }

  static async devToken(subject: string, tenantId: string, roles: Role[]): Promise<string> {
    const response = await fetch("/api/v2/auth/dev-token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject, tenant_id: tenantId, roles }),
      signal: AbortSignal.timeout(15000),
    });
    const body = await parseResponse<{ access_token: string }>(response);
    return body.access_token;
  }

  workspace(): Promise<Workspace> { return this.request("/workspace"); }
  listTasks(): Promise<Task[]> { return this.request("/tasks?limit=100"); }
  getTask(id: string): Promise<Task> { return this.request(`/tasks/${encodeURIComponent(id)}`); }

  async streamTask(message: string, onEvent: (event: StreamEvent) => void): Promise<void> {
    const response = await fetch("/api/v2/agent/chat/stream", {
      method: "POST",
      headers: { Authorization: `Bearer ${this.token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: crypto.randomUUID() }),
      signal: this.signal,
    });
    if (!response.ok) await parseResponse(response);
    if (!response.body) throw new Error("无法建立执行连接，请刷新任务列表确认状态。");
    const reader = response.body!.getReader();
    const decoder = new EventStreamDecoder();
    let terminal = false;
    try {
      while (true) {
        const { value, done } = await reader.read();
        for (const event of decoder.read(value, done)) {
          if (["completed", "failed", "approval_required"].includes(event.type)) terminal = true;
          onEvent(event);
        }
        if (done) break;
      }
    } finally { reader.releaseLock(); }
    if (!terminal) throw new Error("执行连接已断开。任务可能仍在运行，请刷新详情确认，不要重复提交。");
  }

  approve(id: string, payload?: Record<string, unknown>): Promise<Task> {
    return this.request(`/tasks/${encodeURIComponent(id)}/approve`, { modified_payload: payload ?? null });
  }
  reject(id: string, reason: string): Promise<Task> {
    return this.request(`/tasks/${encodeURIComponent(id)}/reject`, { reason });
  }
  resume(id: string): Promise<Task> {
    return this.request(`/tasks/${encodeURIComponent(id)}/resume`, {});
  }
}
