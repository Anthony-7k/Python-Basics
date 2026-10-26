import { AuditOutlined, BookOutlined, CheckCircleOutlined, ClockCircleOutlined, FileTextOutlined, LogoutOutlined, SafetyCertificateOutlined, UserOutlined } from "@ant-design/icons";
import { Button, Progress, Tag } from "antd";
import type { DashboardSummary, Job, Report, ReviewCase } from "./api";

export const caseLabels: Record<string, string> = { DRAFT: "草稿", QUEUED: "排队中", PROCESSING: "处理中", REVIEW_READY: "待审查", APPROVED: "已批准", REJECTED: "已驳回", FAILED: "处理失败", ARCHIVED: "已归档" };
export const caseColors: Record<string, string> = { DRAFT: "default", QUEUED: "blue", PROCESSING: "processing", REVIEW_READY: "orange", APPROVED: "green", REJECTED: "red", FAILED: "red", ARCHIVED: "default" };

export function WorkbenchSidebar({ tenant, user, admin, onPolicies, onAudit, onLogout }: {
  tenant?: string; user?: string; admin: boolean; onPolicies: () => void; onAudit: () => void; onLogout: () => void;
}) {
  return <aside className="sidebar" aria-label="主导航">
    <a className="brand" href="#workbench"><SafetyCertificateOutlined /><span>DocFlow <b>AI</b><small>文档智能审查</small></span></a>
    <nav className="side-nav">
      <a href="#workbench" className="nav-link active" aria-current="page"><FileTextOutlined />案件工作台</a>
      <button className="nav-link" onClick={onPolicies}><BookOutlined />制度知识库</button>
      {admin && <button className="nav-link" onClick={onAudit}><AuditOutlined />审计记录</button>}
    </nav>
    <div className="sidebar-bottom">
      <div className="identity"><SafetyCertificateOutlined /><span title={tenant}>{tenant ?? "正在加载租户"}</span></div>
      <div className="identity"><UserOutlined /><span title={user}>{user ?? "正在加载用户"}</span></div>
      <button className="nav-link logout" onClick={onLogout}><LogoutOutlined />退出登录</button>
    </div>
  </aside>;
}

export function OverviewMetrics({ summary }: { summary: DashboardSummary }) {
  const metrics = [
    { name: "案件总数", value: summary.total_cases, icon: <FileTextOutlined />, tone: "blue" },
    { name: "文档总数", value: summary.total_documents, icon: <BookOutlined />, tone: "blue" },
    { name: "任务成功率", value: `${summary.job_success_rate.toFixed(1)}%`, icon: <CheckCircleOutlined />, tone: "teal" },
    { name: "平均处理耗时", value: `${summary.average_processing_seconds.toFixed(2)} 秒`, icon: <ClockCircleOutlined />, tone: "blue" },
  ];
  return <>
    <div className="kpi-grid">{metrics.map(metric => <div className="kpi" key={metric.name}>
      <span className={`kpi-icon ${metric.tone}`}>{metric.icon}</span><div><span className="metric-label">{metric.name}</span><strong>{metric.value}</strong></div>
    </div>)}</div>
    <div className="overview-secondary">
      <div className="mini-metric"><span>人工修正率</span><strong>{summary.manual_review_rate.toFixed(1)}%</strong></div>
      <div className="mini-metric"><span>规则命中率</span><strong>{summary.rule_hit_rate.toFixed(1)}%</strong></div>
      <div className="metric-group"><span>风险分布</span><div>{Object.entries(summary.risk_by_severity).length ? Object.entries(summary.risk_by_severity).map(([severity, count]) => <Tag key={severity} color={severity === "HIGH" ? "red" : severity === "MEDIUM" ? "orange" : "blue"}>{({ HIGH: "高风险", MEDIUM: "中风险", LOW: "低风险" } as Record<string, string>)[severity] ?? severity} {count}</Tag>) : <Tag>无风险</Tag>}</div></div>
      <div className="metric-group case-counts"><span>案件状态</span><div>{Object.entries(summary.status_counts).map(([status, count]) => <Tag key={status} color={caseColors[status]}>{caseLabels[status] ?? status} {count}</Tag>)}</div></div>
      <div className="mini-metric"><span>已生成报告</span><strong>{summary.ready_reports}</strong></div>
    </div>
  </>;
}

export function CaseList({ cases, selectedId, jobs, reports, onSelect, onDownload, onHistory }: {
  cases: ReviewCase[]; selectedId?: string; jobs: Record<string, Job>; reports: Record<string, Report>;
  onSelect: (id: string) => void; onDownload: (report: Report) => void; onHistory: (item: ReviewCase) => void;
}) {
  return <div className="case-table-scroll"><table className="case-table"><thead><tr><th>案件名称</th><th>材料</th><th>处理状态</th><th>操作</th></tr></thead>
    <tbody>{cases.map(item => <tr key={item.id} className={selectedId === item.id ? "selected" : ""}>
      <td><button className="case-select" onClick={() => onSelect(item.id)} aria-pressed={selectedId === item.id}>
        <strong>{item.title}</strong><span>创建于 {new Date(item.created_at).toLocaleDateString("zh-CN")} · v{item.version}</span>
      </button></td>
      <td><span className="document-count">{item.documents.length} 份材料</span></td>
      <td><Tag color={caseColors[item.status]}>{caseLabels[item.status] ?? item.status}</Tag>{jobs[item.id] && ["PROCESSING", "QUEUED"].includes(jobs[item.id].status) && <Progress size="small" percent={jobs[item.id].progress} />}</td>
      <td><div className="row-actions"><Button size="small" type={selectedId === item.id ? "primary" : "default"} onClick={() => onSelect(item.id)}>查看详情</Button>
        {reports[item.id]?.status === "READY" && <Button size="small" type="link" onClick={() => onDownload(reports[item.id])}>下载报告</Button>}
        {item.status === "FAILED" && <Button size="small" type="link" danger onClick={() => onHistory(item)}>失败原因</Button>}
      </div></td>
    </tr>)}</tbody>
  </table></div>;
}

export function CaseSteps({ status }: { status: string }) {
  const current = status === "DRAFT" ? 0 : ["QUEUED", "PROCESSING", "FAILED"].includes(status) ? 1 : status === "REVIEW_READY" ? 2 : 3;
  return <ol className="case-steps" aria-label="案件处理流程">{["上传材料", "智能抽取", "风险审查", "审批报告"].map((label, index) =>
    <li key={label} className={index < current ? "complete" : index === current ? "current" : ""} aria-current={index === current ? "step" : undefined}>
      <span>{index < current ? "✓" : index + 1}</span>{label}
    </li>)}</ol>;
}
