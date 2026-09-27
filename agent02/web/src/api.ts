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
  error?: { error_type: string; message: string; retryable: boolean };
  latency_ms: number;
  retry_count: number;
}

export interface Task {
  request_id: string;
  task_id: string;
  session_id: string;
  status: string;
  answer: string;
  sources: Array<Record<string, unknown>>;
  tool_calls: ToolCall[];
  tool_results: ToolResult[];
  current_step: number;
  max_steps: number;
  error?: { error_type: string; message: string; retryable: boolean };
  created_at?: string;
  updated_at?: string;
}

export interface StreamEvent {
  type: string;
  data: Record<string, unknown>;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail?.error ?? body.error ?? `HTTP ${response.status}`;
    throw new Error(String(detail));
  }
  return response.json() as Promise<T>;
}

export class ApiClient {
  constructor(private token: string) {}

  private headers(): HeadersInit {
    return { Authorization: `Bearer ${this.token}`, "Content-Type": "application/json" };
  }

  static async devToken(subject: string, tenantId: string, roles: Role[]): Promise<string> {
    const response = await fetch("/api/v2/auth/dev-token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject, tenant_id: tenantId, roles }),
    });
    const body = await parseResponse<{ access_token: string }>(response);
    return body.access_token;
  }

  async listTasks(): Promise<Task[]> {
    return parseResponse(await fetch("/api/v2/tasks", { headers: this.headers() }));
  }

  async getTask(taskId: string): Promise<Task> {
    return parseResponse(await fetch(`/api/v2/tasks/${taskId}`, { headers: this.headers() }));
  }

  async streamTask(message: string, onEvent: (event: StreamEvent) => void): Promise<void> {
    const response = await fetch("/api/v2/agent/chat/stream", {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ message, session_id: crypto.randomUUID() }),
    });
    if (!response.ok || !response.body) await parseResponse(response);
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const type = block.match(/^event:\s*(.+)$/m)?.[1];
        const raw = block.match(/^data:\s*(.+)$/m)?.[1];
        if (type && raw) onEvent({ type, data: JSON.parse(raw) });
      }
    }
  }

  async approve(taskId: string, payload?: Record<string, unknown>): Promise<Task> {
    return parseResponse(await fetch(`/api/v2/tasks/${taskId}/approve`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ modified_payload: payload ?? null }),
    }));
  }

  async reject(taskId: string, reason: string): Promise<Task> {
    return parseResponse(await fetch(`/api/v2/tasks/${taskId}/reject`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ reason }),
    }));
  }
}
