import { formatApiError } from "./presentation";

export type DocumentItem = {
  id: string;
  original_name: string;
  kind: string;
  size_bytes: number;
  scan_status: string;
  parse_status: string;
  classification?: string;
  classification_confidence?: number;
  page_count?: number;
};

export type ReviewCase = {
  id: string;
  title: string;
  description: string;
  status: string;
  version: number;
  created_at: string;
  documents: DocumentItem[];
};

export type Job = {
  id: string;
  case_id: string;
  status: string;
  stage: string;
  progress: number;
  trace_id: string;
  error_message?: string;
};

export type WorkbenchPage = { items: ReviewCase[]; jobs: Record<string, Job>; reports: Record<string, Report>; total: number; offset: number; limit: number };

export type TenantChoice = { id: string; name: string; roles: string[] };
export type JobEvent = { id: string; sequence: number; event_type: string; trace_id: string; payload: { stage?: string; progress?: number; message?: string }; occurred_at: string };
export type AuditEntry = { id: string; actor_id?: string; action: string; resource_type: string; resource_id?: string; outcome: string; trace_id: string; before?: Record<string, unknown>; after?: Record<string, unknown>; created_at: string };
export type AuditPage = { items: AuditEntry[]; total: number; offset: number; limit: number };
export type LoginResult = {
  access_token?: string;
  selection_token?: string;
  requires_tenant_selection: boolean;
  tenants: TenantChoice[];
};

export type ExtractionField = {
  id: string;
  field_name: string;
  raw_value: string;
  normalized_value: string;
  confidence: number;
  version: number;
  source: string;
  evidence: { page_number: number; bbox: number[]; text_hash: string; snippet: string };
};

export type Extraction = {
  id: string;
  document_id: string;
  status: string;
  extractor_version: string;
  schema_version: string;
  processing_metadata?: {
    provider?: string;
    model?: string | null;
    page_methods?: string[];
    total_latency_ms?: number;
    input_tokens?: number | null;
    output_tokens?: number | null;
    cost?: number | null;
  };
  classification?: string;
  classification_confidence?: number;
  fields: ExtractionField[];
};

export type Risk = {
  id: string;
  risk_type: string;
  severity: string;
  status: string;
  explanation: string;
  score: number;
  evidence_ids: string[];
  policy_citations: PolicyCitation[];
  version: number;
  resolution_reason?: string;
  resolved_by?: string;
  resolved_at?: string;
  created_at: string;
};

export type PolicyCitation = {
  policy_id: string;
  policy_title: string;
  policy_version: string;
  chunk_id: string;
  page_number: number;
  excerpt: string;
  score: number;
  effective_on: string;
};

export type Policy = {
  id: string;
  title: string;
  version: string;
  status: string;
  effective_on: string;
  expires_on?: string;
  original_name: string;
  content_hash: string;
  chunk_count: number;
  created_at: string;
};

export type Approval = {
  id: string;
  case_id: string;
  decision: string;
  reason: string;
  actor_id: string;
  case_version: number;
  created_at: string;
};

export type Report = {
  id: string;
  case_id: string;
  case_version: number;
  report_version: number;
  status: string;
  content_hash?: string;
  content_type: string;
  error_message?: string;
  created_at: string;
  generated_at?: string;
  replayed?: boolean;
};

export type DashboardSummary = {
  period: { start?: string; end?: string };
  total_cases: number;
  status_counts: Record<string, number>;
  total_documents: number;
  total_jobs: number;
  job_success_rate: number;
  average_processing_seconds: number;
  manual_review_rate: number;
  rule_hit_rate: number;
  risk_by_severity: Record<string, number>;
  risk_by_status: Record<string, number>;
  approval_counts: Record<string, number>;
  ready_reports: number;
};

export type Comparison = {
  case_id: string;
  columns: Array<{
    document_type: string;
    match_status: "MATCHED" | "MISSING" | "AMBIGUOUS" | "UNAVAILABLE";
    candidates: Array<{ document_id: string; original_name: string; parse_status: string }>;
    document_id?: string;
    original_name?: string;
    fields: Record<string, { value: string; confidence: number; evidence_id: string }>;
  }>;
};

const API = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, token?: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API}${path}`, { ...init, headers });
  if (!response.ok) {
    if (response.status === 401 && token) window.dispatchEvent(new Event("docflow-session-expired"));
    const body = await response.json().catch(() => ({ message: response.statusText }));
    const detail = Array.isArray(body.detail) ? body.detail.map((item: {msg: string}) => item.msg).join("；") : body.detail;
    throw new Error(formatApiError(body.message ?? detail, body.trace_id));
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const api = {
  workbench: (token: string, q = "", status = "", offset = 0) => request<WorkbenchPage>(`/api/v1/workbench?${new URLSearchParams({q, ...(status ? {status} : {}), offset: String(offset), limit: "12"})}`, token),
  login: (email: string, password: string) =>
    request<LoginResult>("/api/v1/auth/login", undefined, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  selectTenant: (selectionToken: string, tenantId: string) =>
    request<LoginResult>("/api/v1/auth/select-tenant", undefined, {
      method: "POST",
      body: JSON.stringify({ selection_token: selectionToken, tenant_id: tenantId }),
    }),
  me: (token: string) => request<{ display_name: string; tenant_name: string; roles: string[] }>("/api/v1/auth/me", token),
  cases: (token: string, q = "", status = "") => request<ReviewCase[]>(`/api/v1/cases?${new URLSearchParams({q, ...(status ? {status} : {})})}`, token),
  caseJobs: (token: string, caseId: string) => request<Job[]>(`/api/v1/cases/${caseId}/jobs`, token),
  caseReports: (token: string, caseId: string) => request<Report[]>(`/api/v1/cases/${caseId}/reports`, token),
  jobHistory: (token: string, jobId: string) => request<JobEvent[]>(`/api/v1/jobs/${jobId}/history`, token),
  deleteDocument: (token: string, documentId: string) => request<void>(`/api/v1/documents/${documentId}`, token, {method: "DELETE"}),
  retryReport: (token: string, reportId: string) => request<Report>(`/api/v1/reports/${reportId}/retry`, token, {method: "POST"}),
  audit: (token: string, action = "", offset = 0) => request<AuditPage>(`/api/v1/audit-logs?${new URLSearchParams({...(action ? {action} : {}), offset: String(offset), limit: "20"})}`, token),
  createCase: (token: string, title: string, description: string) =>
    request<ReviewCase>("/api/v1/cases", token, {
      method: "POST",
      body: JSON.stringify({ title, description }),
    }),
  upload: (token: string, caseId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<DocumentItem>(`/api/v1/cases/${caseId}/documents`, token, { method: "POST", body });
  },
  submit: (token: string, caseId: string) =>
    request<Job>(`/api/v1/cases/${caseId}/submit`, token, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
    }),
  job: (token: string, jobId: string) => request<Job>(`/api/v1/jobs/${jobId}`, token),
  extraction: (token: string, documentId: string) =>
    request<Extraction>(`/api/v1/documents/${documentId}/extraction`, token),
  risks: (token: string, caseId: string) =>
    request<Risk[]>(`/api/v1/cases/${caseId}/risks`, token),
  comparison: (token: string, caseId: string) =>
    request<Comparison>(`/api/v1/cases/${caseId}/comparison`, token),
  rerunReview: (token: string, caseId: string) =>
    request<{ run_group_id: string; rules: number; risks: number }>(`/api/v1/cases/${caseId}/review`, token, { method: "POST" }),
  correctField: (token: string, fieldId: string, expectedVersion: number, normalizedValue: string, reason: string) =>
    request<ExtractionField>(`/api/v1/fields/${fieldId}`, token, {
      method: "PATCH",
      body: JSON.stringify({ expected_version: expectedVersion, normalized_value: normalizedValue, reason }),
    }),
  resolveRisk: (token: string, riskId: string, expectedVersion: number, disposition: "RESOLVED" | "ACCEPTED", reason: string) =>
    request<Risk>(`/api/v1/risks/${riskId}/resolve`, token, {
      method: "POST",
      body: JSON.stringify({ expected_version: expectedVersion, disposition, reason }),
    }),
  policies: (token: string) => request<Policy[]>("/api/v1/policies", token),
  uploadPolicy: (token: string, file: File, title: string, version: string, effectiveOn: string, expiresOn?: string) => {
    const body = new FormData();
    body.append("file", file);
    body.append("title", title);
    body.append("version", version);
    body.append("effective_on", effectiveOn);
    if (expiresOn) body.append("expires_on", expiresOn);
    return request<Policy>("/api/v1/policies", token, { method: "POST", body });
  },
  approve: (token: string, caseId: string, expectedVersion: number, decision: "APPROVED" | "REJECTED", reason: string) =>
    request<Approval>(`/api/v1/cases/${caseId}/approvals`, token, {
      method: "POST",
      body: JSON.stringify({ expected_version: expectedVersion, decision, reason }),
    }),
  requestReport: (token: string, caseId: string, expectedVersion: number) =>
    request<Report>(`/api/v1/cases/${caseId}/reports`, token, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ expected_version: expectedVersion }),
    }),
  report: (token: string, reportId: string) => request<Report>(`/api/v1/reports/${reportId}`, token),
  downloadReport: async (token: string, reportId: string) => {
    const response = await fetch(`${API}/api/v1/reports/${reportId}/download`, { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) {
      const body = await response.json().catch(() => ({ message: response.statusText }));
      throw new Error(formatApiError(body.message ?? body.detail, body.trace_id));
    }
    return response.blob();
  },
  dashboard: (token: string, start?: string, end?: string) => {
    const query = new URLSearchParams();
    if (start) query.set("start", start);
    if (end) query.set("end", end);
    const suffix = query.size ? `?${query.toString()}` : "";
    return request<DashboardSummary>(`/api/v1/dashboard/summary${suffix}`, token);
  },
};

