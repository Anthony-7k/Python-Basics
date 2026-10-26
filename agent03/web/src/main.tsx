import { AuditOutlined, BookOutlined, CheckCircleOutlined, DownloadOutlined, EditOutlined, EyeOutlined, FileDoneOutlined, InboxOutlined, PlusOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Alert, App as AntApp, Button, Card, Col, ConfigProvider, Descriptions, Divider, Empty, Form, Input, Layout, List, Modal, Pagination, Popconfirm, Progress, Radio, Row, Select, Space, Spin, Tag, Timeline, Typography, Upload, message } from "antd";
import zhCN from "antd/locale/zh_CN";
import type { UploadProps } from "antd";
import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { ComparisonCard } from "./ComparisonCard";
import { CaseList, CaseSteps, OverviewMetrics, WorkbenchSidebar, caseLabels, caseColors } from "./WorkbenchChrome";
import { fieldLabels, riskLabels } from "./presentation";
import { api, type AuditPage, type Comparison, type DashboardSummary, type Extraction, type ExtractionField, type Job, type JobEvent, type Policy, type Report, type ReviewCase, type Risk, type TenantChoice } from "./api";
import "./styles.css";

const { Header, Content } = Layout;
const { Title, Text, Paragraph } = Typography;

function Login({ onLogin }: { onLogin: (token: string) => void }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectionToken, setSelectionToken] = useState("");
  const [tenants, setTenants] = useState<TenantChoice[]>([]);
  const submit = async (values: { email: string; password: string }) => {
    setLoading(true);
    setError("");
    try {
      const result = await api.login(values.email, values.password);
      if (result.access_token) onLogin(result.access_token);
      else if (result.selection_token) {
        setSelectionToken(result.selection_token);
        setTenants(result.tenants);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };
  const chooseTenant = async (tenantId: string) => {
    setLoading(true);
    setError("");
    try {
      const result = await api.selectTenant(selectionToken, tenantId);
      if (!result.access_token) throw new Error("租户令牌签发失败");
      onLogin(result.access_token);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "租户选择失败");
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className="login-shell">
      <Card className="login-card">
        <div className="brand-mark"><SafetyCertificateOutlined /></div>
        <Title level={2}>DocFlow AI</Title>
        <Paragraph type="secondary">合同、采购单和发票的智能审查工作台</Paragraph>
        {error && <Alert type="error" message={error} showIcon />}
        {selectionToken ? (
          <div>
            <Text strong>请选择当前租户</Text>
            <List className="tenant-list" dataSource={tenants} renderItem={(tenant) => (
              <List.Item actions={[<Button key={tenant.id} type="primary" loading={loading} onClick={() => chooseTenant(tenant.id)}>进入</Button>]}>
                <List.Item.Meta title={tenant.name} description={tenant.roles.join(" · ")} />
              </List.Item>
            )} />
            <Button type="link" onClick={() => { setSelectionToken(""); setTenants([]); }}>返回登录</Button>
          </div>
        ) : (
          <Form layout="vertical" onFinish={submit} initialValues={{ email: "demo@docflow.local", password: "Demo123!" }}>
            <Form.Item label="邮箱" name="email" rules={[{ required: true }]}><Input size="large" /></Form.Item>
            <Form.Item label="密码" name="password" rules={[{ required: true }]}><Input.Password size="large" /></Form.Item>
            <Button type="primary" htmlType="submit" size="large" loading={loading} block>进入工作台</Button>
          </Form>
        )}
      </Card>
    </div>
  );
}

function Workspace({ token, logout }: { token: string; logout: () => void }) {
  const [cases, setCases] = useState<ReviewCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const selectedCase = cases.find(item => item.id === selectedCaseId) ?? cases[0];
  const [selectedRisks, setSelectedRisks] = useState<Risk[]>();
  const [selectedRiskError, setSelectedRiskError] = useState(false);
  const [me, setMe] = useState<{ display_name: string; tenant_name: string; roles: string[] }>();
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [activeJob, setActiveJob] = useState<Job>();
  const [extraction, setExtraction] = useState<Extraction>();
  const [extractionOpen, setExtractionOpen] = useState(false);
  const [extractionLoading, setExtractionLoading] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [comparison, setComparison] = useState<Comparison>();
  const [risks, setRisks] = useState<Risk[]>([]);
  const [reviewCaseId, setReviewCaseId] = useState("");
  const [editingField, setEditingField] = useState<ExtractionField>();
  const [resolvingRisk, setResolvingRisk] = useState<Risk>();
  const [policiesOpen, setPoliciesOpen] = useState(false);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [policyFile, setPolicyFile] = useState<File>();
  const [policyLoading, setPolicyLoading] = useState(false);
  const [approvalCase, setApprovalCase] = useState<ReviewCase>();
  const [reports, setReports] = useState<Record<string, Report>>({});
  const [dashboard, setDashboard] = useState<DashboardSummary>();
  const [dashboardStart, setDashboardStart] = useState("");
  const [dashboardEnd, setDashboardEnd] = useState("");
  const [caseQuery, setCaseQuery] = useState("");
  const [caseStatus, setCaseStatus] = useState("");
  const [caseOffset, setCaseOffset] = useState(0);
  const [caseTotal, setCaseTotal] = useState(0);
  const [jobs, setJobs] = useState<Record<string, Job>>({});
  const [historyCase, setHistoryCase] = useState<ReviewCase>();
  const [historyJobs, setHistoryJobs] = useState<Job[]>([]);
  const [historyReports, setHistoryReports] = useState<Report[]>([]);
  const [historyEvents, setHistoryEvents] = useState<JobEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [auditOpen, setAuditOpen] = useState(false);
  const [auditPage, setAuditPage] = useState<AuditPage>();
  const [auditAction, setAuditAction] = useState("");
  const [form] = Form.useForm();
  const [correctionForm] = Form.useForm();
  const [resolutionForm] = Form.useForm();
  const [policyForm] = Form.useForm();
  const [approvalForm] = Form.useForm();

  const refresh = async (offset = caseOffset) => {
    const [profile, page, summary] = await Promise.all([api.me(token), api.workbench(token, caseQuery, caseStatus, offset), api.dashboard(token, dashboardStart, dashboardEnd)]);
    setMe(profile);
    setCases(page.items);
    setCaseTotal(page.total);
    setCaseOffset(page.offset);
    setDashboard(summary);
    setJobs(page.jobs);
    setReports(page.reports);
  };
  useEffect(() => { refresh().catch((e) => message.error(e.message)).finally(() => setLoading(false)); }, []);
  useEffect(() => {
    let cancelled = false;
    setSelectedRisks(undefined);
    setSelectedRiskError(false);
    if (selectedCase?.status === "REVIEW_READY") {
      api.risks(token, selectedCase.id).then(next => { if (!cancelled) setSelectedRisks(next); })
        .catch(() => { if (!cancelled) setSelectedRiskError(true); });
    }
    return () => { cancelled = true; };
  }, [selectedCase?.id, selectedCase?.version, selectedCase?.status, token]);
  useEffect(() => {
    if (!activeJob || ["SUCCEEDED", "FAILED"].includes(activeJob.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.job(token, activeJob.id);
        setActiveJob(next);
        setJobs((current) => ({...current, [next.case_id]: next}));
        if (["SUCCEEDED", "FAILED"].includes(next.status)) await refresh();
      } catch (error) { message.error((error as Error).message); }
    }, 700);
    return () => window.clearInterval(timer);
  }, [activeJob?.id, activeJob?.status, caseOffset, caseQuery, caseStatus, dashboardStart, dashboardEnd]);
  useEffect(() => {
    const pending = Object.values(jobs).filter((job) => !["SUCCEEDED", "FAILED"].includes(job.status));
    if (!pending.length || activeJob && !["SUCCEEDED", "FAILED"].includes(activeJob.status)) return;
    const timer = window.setInterval(() => { refresh().catch((error) => message.error(error.message)); }, 1500);
    return () => window.clearInterval(timer);
  }, [jobs, activeJob?.status]);
  useEffect(() => {
    const pending = Object.values(reports).filter((report) => !["READY", "FAILED"].includes(report.status));
    if (!pending.length) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await Promise.all(pending.map((report) => api.report(token, report.id)));
        setReports((current) => ({ ...current, ...Object.fromEntries(next.map((report) => [report.case_id, report])) }));
      } catch (error) { message.error((error as Error).message); }
    }, 700);
    return () => window.clearInterval(timer);
  }, [reports, token]);

  const uploadProps = (item: ReviewCase): UploadProps => ({
    disabled: item.status !== "DRAFT" || !canSubmit,
    multiple: true,
    showUploadList: false,
    accept: ".pdf,.png,.jpg,.jpeg,.docx",
    beforeUpload: (file) => {
      if (file.size > 25 * 1024 * 1024) { message.error("文件大小不能超过 25 MB"); return Upload.LIST_IGNORE; }
      return true;
    },
    customRequest: async ({ file, onSuccess, onError }) => {
      try { await api.upload(token, item.id, file as File); onSuccess?.({}); message.success("文件上传成功"); await refresh(); }
      catch (error) { onError?.(error as Error); message.error((error as Error).message); }
    },
  });

  const statusColor = caseColors;
  const showExtraction = async (documentId: string) => {
    setExtractionOpen(true);
    setExtractionLoading(true);
    try { setExtraction(await api.extraction(token, documentId)); }
    catch (error) { message.error((error as Error).message); setExtractionOpen(false); }
    finally { setExtractionLoading(false); }
  };
  const showReview = async (caseId: string) => {
    setReviewCaseId(caseId);
    setReviewOpen(true);
    setReviewLoading(true);
    try {
      const [nextComparison, nextRisks] = await Promise.all([api.comparison(token, caseId), api.risks(token, caseId)]);
      setComparison(nextComparison);
      setRisks(nextRisks);
    } catch (error) { message.error((error as Error).message); setReviewOpen(false); }
    finally { setReviewLoading(false); }
  };
  const refreshExtraction = async () => {
    if (extraction) setExtraction(await api.extraction(token, extraction.document_id));
    await refresh();
  };
  const refreshReview = async () => {
    if (!reviewCaseId) return;
    const [nextComparison, nextRisks] = await Promise.all([api.comparison(token, reviewCaseId), api.risks(token, reviewCaseId)]);
    setComparison(nextComparison);
    setRisks(nextRisks);
    if (selectedCase?.id === reviewCaseId) setSelectedRisks(nextRisks);
    await refresh();
  };
  const showPolicies = async () => {
    setPoliciesOpen(true);
    setPolicyLoading(true);
    try { setPolicies(await api.policies(token)); }
    catch (error) { message.error((error as Error).message); }
    finally { setPolicyLoading(false); }
  };
  const canApprove = me?.roles.some((role) => ["approver", "tenant_admin"].includes(role));
  const canSubmit = me?.roles.some((role) => ["submitter", "tenant_admin"].includes(role));
  const canReview = me?.roles.some((role) => ["reviewer", "tenant_admin"].includes(role));
  const showHistory = async (item: ReviewCase) => {
    setHistoryCase(item); setHistoryLoading(true); setHistoryEvents([]);
    try {
      const [nextJobs, nextReports] = await Promise.all([api.caseJobs(token, item.id), api.caseReports(token, item.id)]);
      setHistoryJobs(nextJobs); setHistoryReports(nextReports);
      if (nextJobs.length) setHistoryEvents(await api.jobHistory(token, nextJobs[0].id));
    } catch (error) { message.error((error as Error).message); }
    finally { setHistoryLoading(false); }
  };
  const loadAudit = async (offset = 0) => {
    try { setAuditPage(await api.audit(token, auditAction, offset)); }
    catch (error) { message.error((error as Error).message); }
  };
  const downloadReport = async (report: Report) => {
    try {
      const blob = await api.downloadReport(token, report.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      const extension = report.content_type === "application/pdf" ? "pdf" : "html";
      anchor.download = `docflow-report-${report.id}.${extension}`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) { message.error((error as Error).message); }
  };
  return (
    <Layout className="app-shell">
      <WorkbenchSidebar tenant={me?.tenant_name} user={me?.display_name} admin={Boolean(me?.roles.includes("tenant_admin"))}
        onPolicies={showPolicies} onAudit={() => { setAuditOpen(true); void loadAudit(); }} onLogout={logout} />
      <div className="workspace-main" id="workbench">
      <Header className="topbar">
        <div className="breadcrumb">工作空间 <span>/</span> <strong>案件工作台</strong></div>
        <div className="topbar-profile"><span className="trust-label"><SafetyCertificateOutlined /> 证据驱动 · 人工复核</span><span className="avatar" title={me?.display_name}>{me?.display_name?.slice(0, 1) ?? "D"}</span></div>
      </Header>
      <Content className="content">
        <div className="hero">
          <div><Title level={1}>案件工作台</Title><Paragraph>让每一次审查，都有据可循</Paragraph></div>
          {canSubmit && <Button type="primary" size="large" icon={<PlusOutlined />} onClick={() => setCreating(true)}>新建案件</Button>}
        </div>
        {dashboard && (
          <Card className="dashboard-card" title="运营概览" extra={<Space wrap className="date-filters"><Input aria-label="统计开始日期" type="date" value={dashboardStart} onChange={(event) => setDashboardStart(event.target.value)} /><span>至</span><Input aria-label="统计结束日期" type="date" value={dashboardEnd} onChange={(event) => setDashboardEnd(event.target.value)} /><Button onClick={async () => { try { setDashboard(await api.dashboard(token, dashboardStart, dashboardEnd)); } catch (error) { message.error((error as Error).message); } }}>筛选</Button><Button type="text" onClick={async () => { try { setDashboardStart(""); setDashboardEnd(""); setDashboard(await api.dashboard(token)); } catch (error) { message.error((error as Error).message); } }}>重置</Button></Space>}>
            <OverviewMetrics summary={dashboard} />
          </Card>
        )}
        {activeJob && (
          <Alert className="job-strip" type={activeJob.status === "FAILED" ? "error" : "info"} showIcon
            message={`任务 ${activeJob.stage}`} description={<Progress percent={activeJob.progress} status={activeJob.status === "FAILED" ? "exception" : "active"} />} />
        )}
        <div className="case-workspace">
        <section className="case-list-panel" aria-label="案件列表">
        <div className="section-heading"><h2>案件列表</h2><Text type="secondary">共 {caseTotal} 个案件</Text></div>
        <Space wrap className="case-filters">
          <Input placeholder="搜索案件名称" aria-label="搜索案件名称" value={caseQuery} onChange={(event) => setCaseQuery(event.target.value)} onPressEnter={() => { void refresh(0).catch((error) => message.error(error.message)); }} />
          <Select aria-label="案件状态" value={caseStatus} onChange={setCaseStatus} style={{minWidth: 160}} options={[{value: "", label: "全部状态"}, ...Object.keys(caseLabels).map((status) => ({value: status, label: caseLabels[status]}))]} />
          <Button onClick={() => { void refresh(0).catch((error) => message.error(error.message)); }}>查询 / 刷新</Button>
        </Space>
        {loading ? <div className="center"><Spin size="large" /></div> : cases.length === 0 ? <Empty description="暂无符合条件的案件" /> : <CaseList cases={cases} selectedId={selectedCase?.id} jobs={jobs} reports={reports} onSelect={setSelectedCaseId} onDownload={downloadReport} onHistory={showHistory} />}
        <Pagination className="case-pagination" current={Math.floor(caseOffset / 12) + 1} total={caseTotal} pageSize={12} showSizeChanger={false} onChange={(page) => { void refresh((page - 1) * 12).catch((error) => message.error(error.message)); }} />
        </section>
        <section className="case-detail-panel" aria-label="案件详情">
        {!loading && selectedCase ? [selectedCase].map((item) => (
                <Card key={item.id} className="case-card" title={<Space wrap><span>{item.title}</span><Tag color={statusColor[item.status]}>{caseLabels[item.status] ?? item.status}</Tag></Space>} extra={<Text type="secondary">v{item.version}</Text>}>
                  <CaseSteps status={item.status} />
                  <Paragraph type="secondary">{item.description || "暂无描述"}</Paragraph>
                  <h3 className="detail-section-title">业务材料 <span>({item.documents.length})</span></h3>
                  <List size="small" dataSource={item.documents} locale={{ emptyText: "请上传合同、采购单或发票" }}
                    renderItem={(doc) => <List.Item actions={[
                      ...(doc.parse_status === "COMPLETED" ? [<Button key="extract" type="link" icon={<EyeOutlined />} onClick={() => showExtraction(doc.id)}>查看抽取</Button>] : []),
                      ...(canSubmit && item.status === "DRAFT" ? [<Popconfirm key="delete" title="删除此文档？" description="此操作将移除已上传的文件。" onConfirm={async () => { try { await api.deleteDocument(token, doc.id); await refresh(); } catch (error) { message.error((error as Error).message); } }}><Button type="link" danger>删除</Button></Popconfirm>] : [])
                    ]}>
                      <List.Item.Meta title={doc.original_name} description={doc.classification ? `${({ contract: "合同", purchase_order: "采购单", invoice: "发票", unknown: "未识别类型" } as Record<string, string>)[doc.classification] ?? doc.classification} · ${doc.page_count ?? 0} 页 · 待人工核对` : "等待解析"} />
                      <Tag>{doc.kind.toUpperCase()} · {(doc.size_bytes / 1024).toFixed(1)} KB</Tag>
                    </List.Item>} />
                  {jobs[item.id] && <div className="case-job"><Text type="secondary">处理阶段：{jobs[item.id].stage}</Text><Progress percent={jobs[item.id].progress} status={jobs[item.id].status === "FAILED" ? "exception" : jobs[item.id].status === "SUCCEEDED" ? "success" : "active"} />{jobs[item.id].error_message && <Alert type="error" showIcon message="处理失败" description={<><div>{jobs[item.id].error_message}</div><Text copyable>追踪编号：{jobs[item.id].trace_id}</Text></>} />}</div>}
                  {reports[item.id]?.status === "FAILED" && <Alert type="error" showIcon message="报告生成失败" description={reports[item.id].error_message} />}
                  {item.status === "REVIEW_READY" && <div className="selected-risk-summary">
                    <Alert type={selectedRiskError ? "warning" : selectedRisks?.some(risk => risk.status === "OPEN") ? "warning" : selectedRisks ? "success" : "info"} showIcon
                      message={selectedRiskError ? "风险摘要加载失败，请进入三单审查重试" : !selectedRisks ? "正在加载风险摘要" : selectedRisks.some(risk => risk.status === "OPEN") ? `待处置风险 ${selectedRisks.filter(risk => risk.status === "OPEN").length} 项` : selectedRisks.length ? "本轮风险均已处置，仍需人工复核" : "本轮规则未发现风险，仍需人工核对"}
                      description={selectedRisks?.filter(risk => risk.status === "OPEN").map(risk => <div key={risk.id}>{riskLabels[risk.risk_type] ?? risk.risk_type}</div>)} />
                  </div>}
                  <Space wrap className="actions">
                    <Upload.Dragger {...uploadProps(item)} className="compact-upload"><p><InboxOutlined /> 上传材料</p><small>PDF、DOCX、JPG、PNG · 单文件不超过 25 MB</small></Upload.Dragger>
                    {canSubmit && <Button disabled={!["DRAFT", "FAILED"].includes(item.status) || item.documents.length === 0} onClick={async () => { try { const job = await api.submit(token, item.id); setActiveJob(job); await refresh(); } catch (e) { message.error((e as Error).message); } }}>{item.status === "FAILED" ? "重新处理" : "提交处理"}</Button>}
                    <Button onClick={() => { void showHistory(item); }}>处理与报告历史</Button>
                    <Button type="primary" icon={<AuditOutlined />} disabled={item.status !== "REVIEW_READY"} onClick={() => showReview(item.id)}>三单审查</Button>
                    {canApprove && item.status === "REVIEW_READY" && <Button icon={<CheckCircleOutlined />} onClick={() => { setApprovalCase(item); approvalForm.setFieldsValue({ decision: "APPROVED", reason: "" }); }}>审批</Button>}
                    {canApprove && item.status === "APPROVED" && !reports[item.id] && <Button icon={<FileDoneOutlined />} onClick={async () => { try { const report = await api.requestReport(token, item.id, item.version); setReports((current) => ({ ...current, [item.id]: report })); } catch (error) { message.error((error as Error).message); } }}>生成报告</Button>}
                    {reports[item.id]?.status === "READY" && <Button type="primary" icon={<DownloadOutlined />} onClick={() => downloadReport(reports[item.id])}>下载报告</Button>}
                    {canApprove && reports[item.id]?.status === "FAILED" && <Button onClick={async () => { try { const next = await api.retryReport(token, reports[item.id].id); setReports((current) => ({...current, [item.id]: next})); } catch (error) { message.error((error as Error).message); } }}>重试报告</Button>}
                    {reports[item.id] && !["READY", "FAILED"].includes(reports[item.id].status) && <Tag color="processing">报告生成中</Tag>}
                  </Space>
                  <div className="evidence-footer"><SafetyCertificateOutlined /> 字段可追溯至原文 · 操作全程留痕</div>
                </Card>
            )) : <div className="detail-empty"><Empty description={loading ? "正在加载案件" : "选择案件查看材料与审查操作"} /></div>}
        </section>
        </div>
      </Content>
      </div>
      <Modal title={`${historyCase?.title ?? "案件"} · 历史记录`} open={Boolean(historyCase)} onCancel={() => setHistoryCase(undefined)} footer={null} width={800}>
        {historyLoading ? <Spin /> : <>
          <Divider>处理任务</Divider>
          <List dataSource={historyJobs} locale={{emptyText: "尚未提交处理"}} renderItem={(job) => <List.Item actions={[<Button key="events" onClick={async () => { try { setHistoryEvents(await api.jobHistory(token, job.id)); } catch (error) { message.error((error as Error).message); } }}>查看时间线</Button>]}><List.Item.Meta title={<Space><Tag>{job.status}</Tag><Text copyable>{job.id}</Text></Space>} description={<><div>{job.stage} · {job.progress}% {job.error_message}</div><Text copyable>追踪编号：{job.trace_id}</Text></>} /></List.Item>} />
          <Timeline items={historyEvents.map((event) => ({color: event.event_type === "job.failed" ? "red" : "green", children: <><Text>{event.event_type} · {event.payload.stage} · {new Date(event.occurred_at).toLocaleString()}</Text>{event.payload.message && <Paragraph type="danger">{event.payload.message}</Paragraph>}</>}))} />
          <Divider>固化报告</Divider>
          <List dataSource={historyReports} locale={{emptyText: "审批通过后可生成报告"}} renderItem={(report) => <List.Item actions={report.status === "READY" ? [<Button key="download" onClick={() => { void downloadReport(report); }}>下载</Button>] : []}><List.Item.Meta title={<Space><Tag>{report.status}</Tag><Text>案件版本 {report.case_version} · {report.content_type}</Text></Space>} description={<><div>{report.error_message ?? new Date(report.created_at).toLocaleString()}</div>{report.content_hash && <Text copyable>SHA-256：{report.content_hash}</Text>}</>} /></List.Item>} />
        </>}
      </Modal>
      <Modal title="审计记录" open={auditOpen} onCancel={() => setAuditOpen(false)} footer={null} width={900}>
        <Space wrap className="case-filters"><Input placeholder="操作类型，例如 case.create" value={auditAction} onChange={(event) => setAuditAction(event.target.value)} /><Button onClick={() => { void loadAudit(); }}>筛选</Button></Space>
        <List dataSource={auditPage?.items ?? []} renderItem={(entry) => <List.Item><List.Item.Meta title={<Space><Tag>{entry.action}</Tag><Tag color={entry.outcome === "success" ? "green" : "red"}>{entry.outcome}</Tag><Text>{new Date(entry.created_at).toLocaleString()}</Text></Space>} description={<><div>资源：{entry.resource_type} · {entry.resource_id ?? "—"}</div><Text copyable>追踪编号：{entry.trace_id}</Text><details><summary>查看变更</summary><pre className="audit-json">{JSON.stringify({before: entry.before, after: entry.after, actor: entry.actor_id}, null, 2)}</pre></details></>} /></List.Item>} />
        <Pagination current={Math.floor((auditPage?.offset ?? 0) / 20) + 1} total={auditPage?.total ?? 0} pageSize={20} showSizeChanger={false} onChange={(page) => { void loadAudit((page - 1) * 20); }} />
      </Modal>
      <Modal title="新建审查案件" open={creating} onCancel={() => setCreating(false)} onOk={() => form.submit()} destroyOnHidden>
        <Form form={form} layout="vertical" onFinish={async (values) => { try { await api.createCase(token, values.title, values.description ?? ""); setCreating(false); form.resetFields(); await refresh(); } catch (e) { message.error((e as Error).message); } }}>
          <Form.Item name="title" label="案件名称" rules={[{ required: true, message: "请输入案件名称" }]}><Input /></Form.Item>
          <Form.Item name="description" label="说明"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>
      <Modal title="结构化抽取与原文证据" open={extractionOpen} onCancel={() => { setExtractionOpen(false); setExtraction(undefined); }} footer={null} width={780}>
        {extractionLoading ? <div className="center"><Spin /></div> : extraction && (
          <div>
            <Descriptions size="small" column={2} bordered items={[
              { key: "type", label: "文档类型", children: extraction.classification ?? "unknown" },
              { key: "confidence", label: "分类校验", children: "待人工核对（不展示未校准概率）" },
              { key: "extractor", label: "抽取器", children: extraction.extractor_version },
              { key: "schema", label: "Schema", children: extraction.schema_version },
              { key: "pages", label: "解析方式", children: extraction.processing_metadata?.page_methods?.map((method, index) => <Tag key={index} color={method === "fake" ? "orange" : "blue"}>第 {index + 1} 页：{method === "rapidocr" ? "真实 OCR" : method === "fake" ? "模拟 OCR" : "原生解析"}</Tag>) ?? "旧版本未记录" },
              { key: "model", label: "模型", children: extraction.processing_metadata?.model ?? "确定性规则" },
              { key: "latency", label: "处理耗时", children: extraction.processing_metadata?.total_latency_ms != null ? `${extraction.processing_metadata.total_latency_ms} ms` : "未记录" },
              { key: "usage", label: "Token 用量", children: extraction.processing_metadata?.input_tokens != null ? `${extraction.processing_metadata.input_tokens} 输入 / ${extraction.processing_metadata.output_tokens ?? "未知"} 输出` : "未使用或未报告" },
            ]} />
            {(extraction.processing_metadata?.provider === "cloud" || extraction.processing_metadata?.provider === "ollama") && <Alert style={{ marginTop: 12 }} type="info" showIcon message="模型字段已通过原文引用校验，仍需人工核对。展示分数不是经过校准的正确概率；费用尚未核算。" />}
            <List className="field-list" dataSource={extraction.fields} locale={{ emptyText: "未识别到结构化字段" }} renderItem={(field) => (
                <List.Item actions={canReview ? [<Button key="correct" type="link" icon={<EditOutlined />} onClick={() => { setEditingField(field); correctionForm.setFieldsValue({ normalized_value: field.normalized_value, reason: "" }); }}>修正</Button>] : []}>
                <List.Item.Meta title={<Space><Text strong>{fieldLabels[field.field_name] ?? field.field_name}</Text><Tag color={field.source === "HUMAN" ? "blue" : "default"}>{field.source === "MODEL" ? "模型抽取·待人工核对" : field.source} v{field.version}</Tag></Space>}
                  description={<div><div>规范值：<Text copyable>{field.normalized_value}</Text></div><div className="evidence">第 {field.evidence.page_number} 页 · {field.evidence.snippet}</div></div>} />
              </List.Item>
            )} />
          </div>
        )}
      </Modal>
      <Modal title="三单对照与风险" open={reviewOpen} onCancel={() => { setReviewOpen(false); setComparison(undefined); setRisks([]); }} footer={null} width={1100}>
        {reviewLoading ? <div className="center"><Spin /></div> : comparison && (
          <div>
            <Row gutter={16}>{comparison.columns.map((column) => (
              <Col xs={24} md={8} key={column.document_type}>
                <ComparisonCard column={column} />
              </Col>
            ))}</Row>
            <Divider>风险结论</Divider>
            {risks.length === 0 ? <Alert type="success" showIcon message="本轮规则未发现风险" /> : (
              <List dataSource={risks} renderItem={(risk) => (
                <List.Item actions={risk.status === "OPEN" ? [<Button key="resolve" type="link" icon={<CheckCircleOutlined />} onClick={() => { setResolvingRisk(risk); resolutionForm.setFieldsValue({ disposition: "RESOLVED", reason: "" }); }}>处置</Button>] : []}><List.Item.Meta title={<Space><Tag color={risk.severity === "HIGH" ? "red" : "orange"}>{risk.severity === "HIGH" ? "高风险" : risk.severity === "MEDIUM" ? "中风险" : "低风险"}</Tag><Text strong>{riskLabels[risk.risk_type] ?? risk.risk_type}</Text><Text type="secondary">{risk.risk_type}</Text></Space>} description={<div>{risk.explanation}{risk.policy_citations.map((citation) => <div className="policy-citation" key={citation.chunk_id}><BookOutlined /> {citation.policy_title} v{citation.policy_version} · 第 {citation.page_number} 页 · {citation.excerpt}</div>)}{risk.resolution_reason && <div className="evidence">处置说明：{risk.resolution_reason}</div>}</div>} /><Tag color={risk.status === "OPEN" ? "red" : "green"}>{({ OPEN: "待处置", RESOLVED: "已解决", ACCEPTED: "已接受" } as Record<string, string>)[risk.status] ?? risk.status}</Tag></List.Item>
              )} />
            )}
          </div>
        )}
      </Modal>
      <Modal title="修正字段" open={Boolean(editingField)} onCancel={() => setEditingField(undefined)} onOk={() => correctionForm.submit()} destroyOnHidden>
        <Form form={correctionForm} layout="vertical" onFinish={async (values) => {
          if (!editingField) return;
          try {
            await api.correctField(token, editingField.id, editingField.version, values.normalized_value, values.reason);
            message.success("字段已修正，相关规则已重新计算");
            setEditingField(undefined);
            await refreshExtraction();
          } catch (error) { message.error((error as Error).message); }
        }}>
          <Form.Item label="规范值" name="normalized_value" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item label="修正理由" name="reason" rules={[{ required: true, min: 3, message: "请填写至少 3 个字符的理由" }]}><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>
      <Modal title="处置风险" open={Boolean(resolvingRisk)} onCancel={() => setResolvingRisk(undefined)} onOk={() => resolutionForm.submit()} destroyOnHidden>
        <Form form={resolutionForm} layout="vertical" onFinish={async (values) => {
          if (!resolvingRisk) return;
          try {
            await api.resolveRisk(token, resolvingRisk.id, resolvingRisk.version, values.disposition, values.reason);
            message.success("风险已处置");
            setResolvingRisk(undefined);
            await refreshReview();
          } catch (error) { message.error((error as Error).message); }
        }}>
          <Form.Item label="处置结果" name="disposition" rules={[{ required: true }]}><Radio.Group options={[{ label: "问题已解决", value: "RESOLVED" }, { label: "接受该风险", value: "ACCEPTED" }]} /></Form.Item>
          <Form.Item label="处置理由" name="reason" rules={[{ required: true, min: 3, message: "请填写至少 3 个字符的理由" }]}><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>
      <Modal title="制度知识库" open={policiesOpen} onCancel={() => setPoliciesOpen(false)} footer={null} width={850}>
        {me?.roles.includes("tenant_admin") && (
          <Card size="small" title="上传制度版本" className="policy-upload">
            <Form form={policyForm} layout="vertical" onFinish={async (values) => {
              if (!policyFile) { message.error("请选择 PDF 或 DOCX 文件"); return; }
              try {
                await api.uploadPolicy(token, policyFile, values.title, values.version, values.effective_on, values.expires_on);
                message.success("制度已解析并加入检索库");
                setPolicyFile(undefined);
                policyForm.resetFields();
                setPolicies(await api.policies(token));
              } catch (error) { message.error((error as Error).message); }
            }}>
              <Row gutter={12}>
                <Col span={8}><Form.Item label="制度名称" name="title" rules={[{ required: true }]}><Input /></Form.Item></Col>
                <Col span={5}><Form.Item label="版本" name="version" rules={[{ required: true }]}><Input /></Form.Item></Col>
                <Col span={5}><Form.Item label="生效日期" name="effective_on" rules={[{ required: true }]}><Input type="date" /></Form.Item></Col>
                <Col span={6}><Form.Item label="失效日期" name="expires_on"><Input type="date" /></Form.Item></Col>
              </Row>
              <Space><Upload accept=".pdf,.docx" maxCount={1} beforeUpload={(file) => { setPolicyFile(file); return false; }} onRemove={() => { setPolicyFile(undefined); }}><Button icon={<InboxOutlined />}>选择制度文件</Button></Upload><Button type="primary" htmlType="submit">上传并建立索引</Button></Space>
            </Form>
          </Card>
        )}
        {policyLoading ? <div className="center"><Spin /></div> : <List dataSource={policies} locale={{ emptyText: "暂无制度版本" }} renderItem={(policy) => (
          <List.Item><List.Item.Meta title={<Space><Text strong>{policy.title}</Text><Tag color="blue">v{policy.version}</Tag><Tag color="green">{policy.status}</Tag></Space>} description={`${policy.original_name} · 生效 ${policy.effective_on}${policy.expires_on ? ` · 失效 ${policy.expires_on}` : ""} · ${policy.chunk_count} 个检索片段`} /></List.Item>
        )} />}
      </Modal>
      <Modal title="案件审批" open={Boolean(approvalCase)} onCancel={() => setApprovalCase(undefined)} onOk={() => approvalForm.submit()} destroyOnHidden>
        <Form form={approvalForm} layout="vertical" onFinish={async (values) => {
          if (!approvalCase) return;
          try {
            await api.approve(token, approvalCase.id, approvalCase.version, values.decision, values.reason);
            message.success(values.decision === "APPROVED" ? "案件已批准" : "案件已驳回");
            setApprovalCase(undefined);
            await refresh();
          } catch (error) { message.error((error as Error).message); }
        }}>
          <Alert type="info" showIcon message="批准前必须完成所有高风险处置；审批将锁定当前案件版本。" />
          <Form.Item label="审批决定" name="decision" rules={[{ required: true }]}><Radio.Group options={[{ label: "批准", value: "APPROVED" }, { label: "驳回", value: "REJECTED" }]} /></Form.Item>
          <Form.Item label="审批理由" name="reason" rules={[{ required: true, min: 3, message: "请填写至少 3 个字符的理由" }]}><Input.TextArea rows={4} /></Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
}

function Root() {
  const [token, setToken] = useState(() => localStorage.getItem("docflow_token") ?? "");
  const login = (value: string) => { localStorage.setItem("docflow_token", value); setToken(value); };
  const logout = () => { localStorage.removeItem("docflow_token"); setToken(""); };
  useEffect(() => {
    let handled = false;
    const expired = () => {
      if (!token || handled) return;
      handled = true;
      logout(); message.warning("登录已过期，请重新登录");
    };
    window.addEventListener("docflow-session-expired", expired);
    return () => window.removeEventListener("docflow-session-expired", expired);
  }, [token]);
  return <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: "#1762e8", colorText: "#172b45", colorTextSecondary: "#708098", colorBorder: "#dce5ef", borderRadius: 8, fontFamily: 'Inter, "Microsoft YaHei", system-ui, sans-serif', controlHeight: 36 }, components: { Card: { headerFontSize: 16 }, Button: { primaryShadow: "0 3px 8px #1762e81f" } } }}><AntApp>{token ? <Workspace token={token} logout={logout} /> : <Login onLogin={login} />}</AntApp></ConfigProvider>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><Root /></React.StrictMode>);

