import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { ApiClient, ApiError, errorDescription, friendlyError, Role, StreamEvent, Task, Workspace } from "./api";
import { executionOf, filterTasks, formatTime, safeSourceUrl, statuses, taskStats, titleOf, toolNames, TaskFilter } from "./view-model";
import "./styles.css";

type IconName = "spark" | "grid" | "activity" | "history" | "file" | "play" | "refresh" | "logout" | "check" | "clock" | "arrow" | "shield" | "plus" | "search" | "close" | "copy" | "download" | "book" | "bolt" | "layers" | "external" | "alert";
const paths: Record<IconName, string> = {
  spark: "M12 3l2.2 6L20 11l-5.8 2-2.2 6-2.2-6L4 11l5.8-2L12 3zm7 14 1 2 2 1-2 1-1 2-1-2-2-1 2-1 1-2",
  grid: "M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z",
  activity: "M3 12h4l2-6 4 12 2-6h6",
  history: "M3 12a9 9 0 1 0 3-6.7L3 8m0-5v5h5m4-1v5l3 2",
  file: "M14 3H5v18h14V8zm0 0v5h5M8 12h8m-8 4h5",
  play: "m9 6 9 6-9 6V6z", refresh: "M20 4v6h-6M4 20v-6h6M5 8a8 8 0 0 1 13-3l2 5M4 14l2 5a8 8 0 0 0 13-3",
  logout: "M10 4H4v16h6m5-12 4 4-4 4m-6-4h10",
  check: "m5 12 4 4L19 6", clock: "M12 7v5l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  arrow: "m9 6 6 6-6 6", shield: "m12 3-7 3v5c0 4.5 2.8 8 7 10 4.2-2 7-5.5 7-10V6l-7-3m-3 9 2 2 4-4",
  plus: "M12 5v14M5 12h14", search: "m20 20-5-5m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0",
  close: "m6 6 12 12M6 18 18 6", copy: "M8 8h12v12H8zM16 8V4H4v12h4",
  download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
  book: "M12 5C9 3 5 3 2 4v15c3-1 7-1 10 1m0-15c3-2 7-2 10-1v15c-3-1-7-1-10 1V5",
  bolt: "m13 2-9 12h7l-1 8 10-13h-7l1-7",
  layers: "m12 3 10 5-10 5L2 8l10-5M2 12l10 5 10-5M2 16l10 5 10-5",
  external: "M14 3h7v7m0-7L10 14m0-10H4v16h16v-6",
  alert: "M12 8v5m0 3v1M12 3 2 21h20L12 3",
};
function Icon({ name, size = 18, spin = false }: { name: IconName; size?: number; spin?: boolean }) {
  return <svg className={spin ? "icon spinning" : "icon"} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}
function Badge({ task }: { task: Pick<Task, "status" | "error"> }) {
  return <span className={`status status-${task.error?.error_type === "approval_rejected" ? "REJECTED" : task.status}`}><i />{task.error?.error_type === "approval_rejected" ? "已拒绝" : statuses[task.status] || task.status}</span>;
}
function Empty({ icon, title, children }: { icon: IconName; title: string; children?: React.ReactNode }) {
  return <div className="empty"><span className="empty-icon"><Icon name={icon} size={26} /></span><h3>{title}</h3>{children && <p>{children}</p>}</div>;
}
const rolesList: Array<[Role, string]> = [["viewer", "查看者"], ["operator", "操作员"], ["approver", "审批人"], ["admin", "管理员"]];
const templates: Array<{ icon: IconName; title: string; description: string; prompt: string; tone: string }> = [
  { icon: "book", title: "企业知识问答", description: "查询制度，获取有据可查的回答", prompt: "查询公司年假制度", tone: "blue" },
  { icon: "bolt", title: "差旅费用计算", description: "先查标准，再完成多步计算", prompt: "查询上海差旅标准并计算 5 天最高报销金额", tone: "violet" },
  { icon: "shield", title: "人工审批流程", description: "体验任务创建前的审批与放行", prompt: "创建任务：周五前提交预算复盘", tone: "amber" },
];
type Notice = { text: string; kind: "error" | "success"; requestId?: string } | null;

function Login({ onLogin, expired }: { onLogin: (token: string) => void; expired: boolean }) {
  const [roles, setRoles] = useState<Role[]>(["operator", "approver"]);
  const [mode, setMode] = useState<"demo" | "token">("demo");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      const token = mode === "token" ? String(form.get("token")).trim()
        : await ApiClient.devToken(String(form.get("subject")).trim(), String(form.get("tenant")).trim(), roles);
      if (!token) throw new Error("请输入有效的访问令牌。");
      onLogin(token);
    } catch (cause) { setError(friendlyError(cause)); } finally { setBusy(false); }
  }
  return <main className="login-layout">
    <section className="login-visual">
      <div className="brand brand-light"><span className="brand-symbol"><Icon name="spark" size={23} /></span><strong>FlowPilot<span>企业智能工作流</span></strong></div>
      <div className="login-story"><span className="overline">WORK, WITH A LITTLE MORE FLOW.</span><h1>从一个想法，<br />到一次完成。</h1><p>让企业知识、工具和团队协同工作。<br />每一步执行，都清晰可见。</p>
        <div className="login-flow"><span><Icon name="spark" />智能规划</span><i /><span><Icon name="layers" />工具协作</span><i /><span><Icon name="shield" />人工审批</span></div>
      </div><div className="login-bottom"><span><i />为可追踪的工作而设计</span><span>FlowPilot / 02</span></div>
    </section>
    <section className="login-form-wrap"><form className="login-form" onSubmit={login}>
      <div className="mobile-brand"><Icon name="spark" size={28} />FlowPilot</div><span className="overline">YOUR WORKSPACE AWAITS</span><h2>登录工作空间</h2><p className="muted">把繁琐交给 Agent，把决策留给你。</p>
      {expired && <p className="inline-notice" role="status">登录已过期，请重新登录后继续。</p>}
      <div className="segmented login-switch" aria-label="登录方式"><button type="button" aria-pressed={mode === "demo"} onClick={() => setMode("demo")}>演示身份</button><button type="button" aria-pressed={mode === "token"} onClick={() => setMode("token")}>访问令牌</button></div>
      {mode === "demo" ? <><label>用户标识<input name="subject" defaultValue="demo-user" maxLength={200} required autoComplete="username" /></label><label>工作空间<input name="tenant" defaultValue="portfolio-demo" maxLength={100} required /></label><fieldset><legend>选择演示角色</legend><div className="role-grid">{rolesList.map(([role, label]) => <label key={role} className="role-option"><input type="checkbox" checked={roles.includes(role)} onChange={e => setRoles(e.target.checked ? [...roles, role] : roles.filter(item => item !== role))} /><span>{label}</span></label>)}</div></fieldset></>
        : <label>访问令牌<textarea name="token" rows={5} placeholder="粘贴由你的身份服务签发的 JWT" required spellCheck={false} autoComplete="off" /></label>}
      {error && <p className="inline-notice error" role="alert">{error}</p>}
      <button className="primary login-submit" disabled={busy || (mode === "demo" && roles.length === 0)}>{busy ? <Icon name="refresh" spin /> : <Icon name="arrow" />}{busy ? "正在连接工作空间…" : "进入工作台"}</button>
      <p className="login-caption"><Icon name="shield" size={14} />{mode === "demo" ? "演示身份仅在开发或集成环境启用" : "令牌仅在当前浏览器会话中使用"}</p>
    </form></section>
  </main>;
}

function WorkspaceApp({ token, onLogout }: { token: string; onLogout: (expired?: boolean) => void }) {
  const controller = useMemo(() => new AbortController(), [token]);
  const client = useMemo(() => new ApiClient(token, controller.signal), [token, controller]);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [bootError, setBootError] = useState("");
  const [reload, setReload] = useState(0);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selected, setSelected] = useState<Task | null>(null);
  const selectedRef = useRef<string | null>(null);
  const [events, setEvents] = useState<Record<string, StreamEvent[]>>({});
  const [page, setPage] = useState<"overview" | "tasks" | "approval">("overview");
  const [filter, setFilter] = useState<TaskFilter>("all");
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [refreshing, setRefreshing] = useState(false);
  const [detailTab, setDetailTab] = useState("result");
  const [health, setHealth] = useState<"checking" | "online" | "offline">("checking");
  const [notice, setNotice] = useState<Notice>(null);
  const [help, setHelp] = useState(false);
  const promptRef = useRef<HTMLTextAreaElement>(null);
  const historyRef = useRef<HTMLElement>(null);
  const detailRef = useRef<HTMLElement>(null);
  const [lastSync, setLastSync] = useState<number | null>(null);
  const can = (permission: string) => workspace?.permissions.includes(permission) ?? false;
  const stats = useMemo(() => taskStats(tasks), [tasks]);
  const effectiveFilter = page === "approval" ? "approval" : filter;
  const visibleTasks = useMemo(() => filterTasks(tasks, effectiveFilter, query), [tasks, effectiveFilter, query]);
  const draftKey = workspace ? `flowpilot-draft:${workspace.tenant_id}:${workspace.subject}` : null;

  const reportError = useCallback((cause: unknown) => {
    if (controller.signal.aborted) return;
    if (cause instanceof ApiError && cause.status === 401) { onLogout(true); return; }
    setNotice({ text: friendlyError(cause), kind: "error", requestId: cause instanceof ApiError ? cause.requestId : undefined });
  }, [controller, onLogout]);

  const selectTask = useCallback((task: Task | null) => {
    selectedRef.current = task?.task_id ?? null;
    setSelected(task); setDetailTab("result");
  }, []);

  const refresh = useCallback(async () => {
    if (controller.signal.aborted) return;
    setRefreshing(true);
    try {
      const rows = await client.listTasks();
      if (controller.signal.aborted) return;
      setTasks(rows); setLastSync(Date.now());
      setSelected(current => current ? rows.find(item => item.task_id === current.task_id) ?? current : rows[0] ?? null);
      if (!selectedRef.current && rows[0]) selectedRef.current = rows[0].task_id;
    } catch (cause) { reportError(cause); } finally { if (!controller.signal.aborted) setRefreshing(false); }
  }, [client, controller, reportError]);

  useEffect(() => {
    let active = true;
    setBootError("");
    void (async () => {
      try {
        const info = await client.workspace();
        if (!active) return;
        setWorkspace(info);
        setMessage(sessionStorage.getItem(`flowpilot-draft:${info.tenant_id}:${info.subject}`) ?? "");
        if (info.permissions.includes("task:read")) await refresh();
      } catch (cause) {
        if (!active || controller.signal.aborted) return;
        if (cause instanceof ApiError && cause.status === 401) { onLogout(true); return; }
        setBootError(friendlyError(cause));
      }
    })();
    return () => { active = false; };
  }, [client, controller, reload, refresh, onLogout]);

  useEffect(() => () => { controller.abort(); }, [controller]);
  useEffect(() => {
    if (!draftKey) return;
    sessionStorage.setItem(draftKey, message);
  }, [draftKey, message]);
  useEffect(() => {
    if (notice?.kind !== "success") return;
    const timer = window.setTimeout(() => setNotice(null), 3500);
    return () => window.clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    const check = async () => {
      try {
        const response = await fetch("/ready", { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(5000)]) });
        if (!controller.signal.aborted) setHealth(response.ok ? "online" : "offline");
      } catch { if (!controller.signal.aborted) setHealth("offline"); }
    };
    void check();
    const timer = window.setInterval(() => void check(), 30000);
    return () => window.clearInterval(timer);
  }, [controller]);
  useEffect(() => {
    if (busy || !tasks.some(task => ["RUNNING", "CREATED", "WAITING_TOOL", "WAITING_APPROVAL"].includes(task.status))) return;
    const timer = window.setInterval(() => { if (!document.hidden) void refresh(); }, 10000);
    return () => window.clearInterval(timer);
  }, [busy, tasks, refresh]);

  function updateTask(task: Task) {
    setTasks(current => [task, ...current.filter(item => item.task_id !== task.task_id)].slice(0, 100));
    if (selectedRef.current === task.task_id) setSelected(task);
  }

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!message.trim() || message.length > 4000 || !can("task:create") || lock.current) return;
    lock.current = true; setBusy(true); setNotice(null);
    const prompt = message.trim();
    let taskId = "";
    try {
      await client.streamTask(prompt, item => {
        if (item.type === "task_created") {
          taskId = String(item.data.task_id);
          const created: Task = { task_id: taskId, request_id: String(item.data.request_id || ""), session_id: "", status: "RUNNING", message: prompt, answer: "", tool_calls: [], tool_results: [], sources: [], current_step: 0, max_steps: 10, created_at: new Date().toISOString() };
          selectTask(created); updateTask(created);
          window.requestAnimationFrame(() => historyRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
          setEvents(current => ({ ...current, [taskId]: [item] }));
        } else if (taskId) {
          setEvents(current => ({ ...current, [taskId]: [...(current[taskId] || []), item].slice(-150) }));
          const state = item.type === "approval_required" ? "WAITING_APPROVAL" : item.type === "completed" ? "COMPLETED" : item.type === "failed" ? "FAILED" : "RUNNING";
          setSelected(current => current?.task_id === taskId ? { ...current, status: state, answer: String(item.data.answer ?? current.answer) } : current);
        }
      });
    } catch (cause) { reportError(cause); }
    finally {
      if (!controller.signal.aborted) {
        if (taskId) {
          try { updateTask(await client.getTask(taskId)); } catch (cause) { reportError(cause); }
        }
        await refresh(); setBusy(false);
      }
      lock.current = false;
    }
  }

  async function act(action: "approve" | "reject" | "resume", payload?: Record<string, unknown>, reason?: string) {
    if (!selected || lock.current) return;
    lock.current = true; setBusy(true); setNotice(null);
    const id = selected.task_id;
    try {
      const next = action === "approve" ? await client.approve(id, payload) : action === "reject" ? await client.reject(id, reason || "由审批人拒绝") : await client.resume(id);
      updateTask({ ...selected, ...next });
      const full = await client.getTask(id);
      updateTask(full);
      setEvents(current => ({ ...current, [id]: [...(current[id] || []), {
        type: action === "resume" ? "task_resumed" : "approval_decided",
        data: { task_id: id, action, status: full.status }, receivedAt: Date.now(),
      }] }));
      await refresh();
      setNotice({ text: action === "reject" ? "已拒绝执行，审批意见已记录。" : full.status === "COMPLETED" ? "任务已执行完成。" : "任务状态已更新。", kind: "success" });
    } catch (cause) { reportError(cause); await refresh(); }
    finally { if (!controller.signal.aborted) setBusy(false); lock.current = false; }
  }

  function navigate(next: typeof page) {
    setPage(next); setFilter("all"); setQuery("");
    if (next === "approval") selectTask(tasks.find(task => task.status === "WAITING_APPROVAL") ?? null);
  }
  function newTask(prompt?: string) {
    setPage("overview");
    if (prompt !== undefined) setMessage(prompt);
    window.setTimeout(() => { promptRef.current?.focus(); promptRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); }, 30);
  }
  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); setNotice({ text: "已复制到剪贴板。", kind: "success" }); }
    catch { setNotice({ text: "浏览器未允许复制，请直接选择文字复制。", kind: "error" }); }
  }
  function exportTask(task: Task) {
    const text = [`# ${titleOf(task)}`, `状态：${statuses[task.status] || task.status}`, `任务编号：${task.task_id}`, "", task.answer, "", "引用来源", ...task.sources.map((s, i) => `${i + 1}. ${s.title || s.source_id || "企业知识"} ${s.locator || ""}`)].join("\n");
    const url = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `FlowPilot-${task.task_id.slice(0, 8)}.md`; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    setNotice({ text: "任务记录已导出。", kind: "success" });
  }

  if (!workspace) return <div className="connection-screen"><span className="brand-symbol"><Icon name="spark" size={28} /></span><h1>{bootError ? "暂时无法进入工作空间" : "正在连接你的工作空间"}</h1><p>{bootError || "正在确认身份与加载任务记录…"}</p>{bootError && <div className="button-row"><button className="primary" onClick={() => setReload(x => x + 1)}>重新连接</button><button className="secondary" onClick={() => onLogout()}>返回登录</button></div>}</div>;

  const pageTitle = page === "overview" ? "工作台" : page === "approval" ? "审批中心" : "任务记录";
  return <div className="app-layout">
    <a className="skip-link" href="#main-content">跳至主要内容</a>
    <aside className="sidebar">
      <div className="brand"><span className="brand-symbol"><Icon name="spark" size={22} /></span><strong>FlowPilot<span>企业智能工作流</span></strong></div>
      <div className="workspace-switch"><span className="workspace-avatar">{workspace.tenant_id.slice(0, 1).toUpperCase()}</span><div><strong title={workspace.tenant_id}>{workspace.tenant_id}</strong><small>当前工作空间</small></div><Icon name="layers" size={15} /></div>
      <p className="nav-caption">工作空间</p><nav aria-label="主导航">
        <button className={page === "overview" ? "nav-item active" : "nav-item"} aria-current={page === "overview" ? "page" : undefined} onClick={() => navigate("overview")}><Icon name="grid" />工作台<span className="nav-active-mark" /></button>
        <button className={page === "tasks" ? "nav-item active" : "nav-item"} aria-current={page === "tasks" ? "page" : undefined} onClick={() => navigate("tasks")}><Icon name="history" />任务记录<span className="nav-count">{tasks.length}</span></button>
        <button className={page === "approval" ? "nav-item active" : "nav-item"} aria-current={page === "approval" ? "page" : undefined} onClick={() => navigate("approval")}><Icon name="shield" />审批中心{stats.waiting > 0 && <span className="nav-count amber">{stats.waiting}</span>}</button>
      </nav>
      <div className="sidebar-bottom"><div className="runtime-note"><span><i />{workspace.planner_mode === "openai" ? "模型规划模式" : "规则演示模式"}</span><p>{workspace.knowledge_backend === "agent01" ? "已配置企业知识库连接" : "使用内置示例知识库"}</p><button onClick={() => setHelp(true)}>查看使用指南 <Icon name="arrow" size={13} /></button></div>
        <div className="profile"><span className="avatar">{workspace.subject.slice(0, 1).toUpperCase()}</span><div><strong title={workspace.subject}>{workspace.subject}</strong><small>{workspace.roles.map(role => rolesList.find(item => item[0] === role)?.[1] || role).join(" · ") || "无角色"}</small></div><button className="icon-button" title="退出登录" aria-label="退出登录" disabled={busy} onClick={() => onLogout()}><Icon name="logout" size={17} /></button></div>
      </div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb"><span>工作空间</span><Icon name="arrow" size={13} /><strong>{pageTitle}</strong></div><div className="topbar-right"><span className={`service-status ${health}`} role="status"><i />{health === "online" ? "服务已就绪" : health === "offline" ? "服务连接异常" : "检查服务中"}</span><span className="environment">{workspace.environment === "production" ? "生产环境" : workspace.environment === "test" ? "测试环境" : "演示环境"}</span><button className="icon-button help-button" title="使用指南" aria-label="使用指南" onClick={() => setHelp(true)}>?</button></div></header>
      <main className="dashboard" id="main-content">
        <section className="page-heading"><div><div className="heading-kicker"><span />{page === "overview" ? "让工作顺畅发生" : page === "approval" ? "每一次放行，都有依据" : "每一次执行，都有迹可循"}</div><h1>{page === "overview" ? "今天，想完成什么？" : pageTitle}</h1><p>{page === "overview" ? "发起一个目标，交给 Agent 规划；关键决策，由你掌握。" : page === "approval" ? "检查待执行操作及参数，确认后再继续工作流。" : "搜索和回看任务结果，也可以从这里继续未完成的工作。"}</p></div><button className="secondary new-task" disabled={!can("task:create")} onClick={() => newTask("")}><Icon name="plus" size={17} />新建任务</button></section>
        <section className="stats-grid" aria-label="当前加载的最近一百条任务概览">
          <button className="stat-card" onClick={() => { navigate("tasks"); setFilter("all"); }}><div><span>任务总数</span><Icon name="layers" /></div><strong>{tasks.length}<small>条</small></strong><p>最近加载的任务记录</p></button>
          <button className="stat-card" onClick={() => navigate("approval")}><div><span>待我审批</span><Icon name="clock" /></div><strong>{stats.waiting}<small>项</small></strong><p>{stats.waiting ? <><span className="dot amber" />{can("task:approve") ? "等待你的确认" : "等待审批人处理"}</> : <><span className="dot" />暂无待处理审批</>}</p></button>
          <button className="stat-card" onClick={() => { navigate("tasks"); setFilter("completed"); }}><div><span>已完成任务</span><Icon name="check" /></div><strong>{stats.completed}<small>条</small></strong><p>已生成最终执行结果</p></button>
          <button className="stat-card" title="已完成 /（已完成 + 失败 + 超时），不含人工拒绝" onClick={() => { navigate("tasks"); setFilter("failed"); }}><div><span>执行成功率</span><Icon name="activity" /></div><strong>{stats.successRate === null ? "—" : stats.successRate}<small>{stats.successRate === null ? "" : "%"}</small></strong><p>{stats.successRate === null ? "执行任务后开始统计" : "按已结束任务计算 · 不含拒绝"}</p></button>
        </section>

        {page === "overview" && <section className="start-grid">
          <article className="panel composer"><div className="panel-title"><span className="section-icon"><Icon name="spark" /></span><h2>交给 Agent 一个目标</h2><span className="pill quiet">自然语言发起</span></div>
            <form onSubmit={submit}><label className="sr-only" htmlFor="task-message">任务描述</label><div className="prompt-wrap"><textarea ref={promptRef} id="task-message" maxLength={4000} value={message} disabled={busy || !can("task:create")} placeholder={"例如：查询上海差旅标准，并计算 5 天的最高报销金额。\n也可以先从右侧场景中选择一个。"} onChange={e => setMessage(e.target.value)} onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !e.nativeEvent.isComposing) { e.preventDefault(); void submit(); } }} /><div className="prompt-meta"><span><Icon name="shield" size={13} />涉及写入操作时会先请你审批</span><span>{message.length}/4000</span></div></div><div className="composer-footer"><span>{!can("task:create") ? "当前账号仅可查看或审批任务" : busy ? "工作流正在执行，可在下方查看进展" : "草稿已保留 · Ctrl / ⌘ + Enter 执行"}</span><button className="primary" disabled={busy || !message.trim() || !can("task:create")}><Icon name={busy ? "refresh" : "arrow"} spin={busy} size={16} />{busy ? "正在执行…" : "开始执行"}</button></div></form>
          </article>
          <article className="templates"><div className="template-heading"><h2>从一个场景开始</h2><span>选择后可继续编辑</span></div>{templates.map(template => <button key={template.title} className="template-card" disabled={busy || !can("task:create")} onClick={() => newTask(template.prompt)}><span className={`template-icon ${template.tone}`}><Icon name={template.icon} size={20} /></span><span><strong>{template.title}</strong><small>{template.description}</small></span><Icon name="arrow" size={15} /></button>)}</article>
        </section>}

        <section className="activity-section" ref={historyRef}><div className="section-heading"><div><h2>{page === "approval" ? "待审批任务" : "任务与执行详情"}<span className="number-label">{visibleTasks.length}</span></h2><p>{page === "approval" ? "批准后，工作流会从暂停的位置继续。" : "最近 100 条任务，按创建时间倒序展示。"}</p></div><button className="text-button" disabled={refreshing || busy} onClick={() => void refresh()}><Icon name="refresh" size={15} spin={refreshing} />{refreshing ? "同步中" : "刷新记录"}</button></div>
          <div className="execution-layout"><article className="panel task-panel"><div className="list-controls"><div className="search-field"><Icon name="search" size={16} /><input aria-label="搜索任务" placeholder="搜索任务内容或编号" value={query} onChange={e => setQuery(e.target.value)} />{query && <button className="icon-button" aria-label="清空搜索" onClick={() => setQuery("")}><Icon name="close" size={14} /></button>}</div>{page !== "approval" && <div className="filter-tabs" aria-label="任务筛选">{([["all", "全部"], ["approval", "待审批"], ["completed", "已完成"], ["failed", "失败 / 超时"]] as Array<[TaskFilter, string]>).map(([key, label]) => <button key={key} aria-pressed={filter === key} onClick={() => setFilter(key)}>{label}{key === "approval" && stats.waiting > 0 && <span>{stats.waiting}</span>}</button>)}</div>}</div>
            <div className="task-list" aria-busy={refreshing}>{visibleTasks.length ? visibleTasks.map(task => <button key={task.task_id} className={`task-row ${selected?.task_id === task.task_id ? "selected" : ""}`} aria-pressed={selected?.task_id === task.task_id} onClick={() => { selectTask(task); if (window.innerWidth <= 650) window.requestAnimationFrame(() => detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })); }}><div className="task-row-top"><Badge task={task} /><time>{formatTime(task.created_at)}</time></div><strong>{titleOf(task)}</strong><div className="task-row-bottom"><span>{task.task_id.slice(0, 8)}</span><span>{task.tool_results.filter(result => result.success).length} 次工具成功调用<Icon name="arrow" size={13} /></span></div></button>)
              : <Empty icon={query ? "search" : page === "approval" ? "shield" : "history"} title={query ? "没有找到相关任务" : page === "approval" ? "待办已清空" : "这里还没有任务"}>{query ? "试试其他关键词，或清空搜索。" : page === "approval" ? "有新审批时，会出现在这里。" : "创建第一个任务，开始你的智能工作流。"}<br />{(query || filter !== "all") && <button className="inline-link" onClick={() => { setQuery(""); setFilter("all"); }}>清除筛选</button>}</Empty>}</div>
            <div className="list-footer"><span>已加载 {tasks.length} 条</span><span>{lastSync ? `${formatTime(new Date(lastSync).toISOString(), false)} 已同步` : "尚未同步"}</span></div>
          </article>
          <article className="panel detail-panel" ref={detailRef} aria-label="任务详情">
            {!selected ? <Empty icon="file" title={busy ? "正在创建任务" : "等待一个值得完成的目标"}>选择左侧任务，查看结果、工具执行与引用来源。</Empty>
              : <><div className="detail-header"><div><div className="detail-label"><span>任务详情</span><Badge task={selected} /></div><h2>{titleOf(selected)}</h2><div className="task-metadata"><span>{formatTime(selected.created_at)}</span><span>·</span><button title="复制完整任务编号" onClick={() => void copy(selected.task_id)}>#{selected.task_id.slice(0, 8)}<Icon name="copy" size={12} /></button></div></div><button className="icon-button" disabled={!selected.answer} title="导出任务记录" aria-label="导出任务记录" onClick={() => exportTask(selected)}><Icon name="download" size={17} /></button></div>
                <div className="detail-tabs" role="tablist" aria-label="任务详情视图">{[["result", "执行结果"], ["tools", `工具调用 ${selected.tool_calls.length || ""}`], ["trace", "执行轨迹"]].map(([key, label]) => <button key={key} id={`tab-${key}`} role="tab" aria-selected={detailTab === key} aria-controls={`panel-${key}`} tabIndex={detailTab === key ? 0 : -1} onKeyDown={e => { if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return; e.preventDefault(); const keys = ["result", "tools", "trace"]; const i = keys.indexOf(key); const next = e.key === "Home" ? 0 : e.key === "End" ? 2 : (i + (e.key === "ArrowRight" ? 1 : 2)) % 3; setDetailTab(keys[next]); document.getElementById(`tab-${keys[next]}`)?.focus(); }} onClick={() => setDetailTab(key)}>{label}{key === "trace" && events[selected.task_id]?.length > 0 && <span className="tiny-dot" />}</button>)}</div>
                <div className="detail-body" id={`panel-${detailTab}`} role="tabpanel" aria-labelledby={`tab-${detailTab}`}>
                  {detailTab === "result" && <>
                    {selected.status === "WAITING_APPROVAL" ? <Approval key={`${selected.task_id}:${selected.current_step}`} task={selected} canApprove={can("task:approve")} busy={busy} onDecision={act} />
                      : <section className={`answer answer-${selected.status}`}><div className="answer-heading"><span><Icon name={selected.status === "COMPLETED" ? "check" : selected.error ? "alert" : "activity"} size={17} />{selected.status === "COMPLETED" ? "任务执行完成" : selected.error?.error_type === "approval_rejected" ? "操作已拒绝" : selected.error ? "执行遇到问题" : "Agent 正在执行"}</span>{selected.answer && <button className="icon-button" title="复制结果" aria-label="复制结果" onClick={() => void copy(selected.answer)}><Icon name="copy" size={15} /></button>}</div><p className="answer-text">{selected.error ? errorDescription(selected.error.error_type, selected.error.message) : selected.answer || "正在规划执行步骤，进展会实时更新。"}</p>{selected.error && <details className="technical-details"><summary>查看错误详情</summary><pre>{selected.error.error_type}\n{selected.error.message}</pre></details>}{["FAILED", "TIMEOUT"].includes(selected.status) && selected.error?.retryable && <button className="secondary recovery-button" disabled={busy || !can("task:resume")} onClick={() => void act("resume")}><Icon name="refresh" size={15} spin={busy} />从失败处恢复</button>}</section>}
                    <section className="workflow-summary"><div className="subheading"><h3>工作流步骤</h3><span>{selected.tool_calls.length ? `${selected.current_step} / ${selected.tool_calls.length} 步` : "暂无工具步骤"}</span></div><div className="step-strip">{selected.tool_calls.length ? selected.tool_calls.map((call, index) => { const execution = executionOf(selected, call); return <button key={call.call_id} className={`step-chip ${execution.status}`} title={execution.label} onClick={() => setDetailTab("tools")}><span>{execution.status === "success" ? <Icon name="check" size={12} /> : index + 1}</span>{toolNames[call.name] || call.name}</button>; }) : <p className="muted">{busy ? "Agent 正在选择工具…" : "此任务没有执行工具调用。"}</p>}</div></section>
                    {selected.sources.length > 0 && <section className="sources-section"><div className="subheading"><h3>引用来源</h3><span>{selected.sources.length} 项来源</span></div>{selected.sources.map((source, index) => { const url = safeSourceUrl(source.url); const title = String(source.title || source.source_id || "企业知识来源"); return <details className="source" key={index}><summary><span className="source-index">{String(index + 1).padStart(2, "0")}</span><span><strong>{title}</strong><small>{String(source.locator || "企业知识库")}{source.source_type === "sample" ? " · 示例数据" : ""}</small></span><Icon name="arrow" size={14} /></summary><p>{String(source.content || "该来源未返回可展示的原文片段。")}</p>{url && <a href={url} target="_blank" rel="noopener noreferrer">打开来源<Icon name="external" size={13} /></a>}</details>; })}</section>}
                  </>}
                  {detailTab === "tools" && <><div className="subheading"><h3>工具执行明细</h3><span>按调用结果展示状态</span></div>{!selected.tool_calls.length ? <Empty icon="layers" title="此任务没有工具调用">工具执行后，参数与返回结果会显示在这里。</Empty> : selected.tool_calls.map((call, index) => { const execution = executionOf(selected, call); return <section className="tool-card" key={call.call_id}><div className="tool-title"><span className={`tool-number ${execution.status}`}>{execution.status === "success" ? <Icon name="check" size={16} /> : index + 1}</span><div><strong>{toolNames[call.name] || call.name}</strong><small>{call.name}{execution.result ? ` · ${Math.round(execution.result.latency_ms)} ms` : ""}</small></div><span className={`execution-state ${execution.status}`}>{execution.label}</span></div><details className="technical-details"><summary>查看参数与返回数据</summary><p>调用参数</p><pre>{JSON.stringify(call.arguments, null, 2)}</pre>{execution.result && <><p>返回结果{execution.result.retry_count ? ` · 重试 ${execution.result.retry_count} 次` : ""}</p><pre>{JSON.stringify(execution.result.success ? execution.result.data : execution.result.error, null, 2)}</pre></>}</details></section>; })}</>}
                  {detailTab === "trace" && <Trace events={events[selected.task_id] || []} task={selected} />}
                </div>
              </>}
          </article></div>
        </section>
        <footer className="page-footer"><span><Icon name="shield" size={13} />关键操作审批 · 执行结果留痕</span><button onClick={() => setHelp(true)}>使用指南 <Icon name="arrow" size={12} /></button></footer>
      </main>
    </div>
    {notice && <div className={`toast ${notice.kind}`} role={notice.kind === "error" ? "alert" : "status"}><Icon name={notice.kind === "success" ? "check" : "alert"} size={20} /><div><p>{notice.text}</p>{notice.requestId && <small>请求编号 {notice.requestId}</small>}</div><button className="icon-button" aria-label="关闭提示" onClick={() => setNotice(null)}><Icon name="close" size={16} /></button></div>}
    {help && <Help onClose={() => setHelp(false)} />}
  </div>;
}

function Approval({ task, canApprove, busy, onDecision }: { task: Task; canApprove: boolean; busy: boolean; onDecision: (action: "approve" | "reject", payload?: Record<string, unknown>, reason?: string) => Promise<void> }) {
  const call = task.tool_calls[task.current_step];
  const [title, setTitle] = useState(String(call?.arguments.title || ""));
  const [due, setDue] = useState(String(call?.arguments.due_date || ""));
  const [raw, setRaw] = useState(JSON.stringify(call?.arguments || {}, null, 2));
  const [reason, setReason] = useState("");
  const [mode, setMode] = useState<"form" | "json">(call?.name === "task" ? "form" : "json");
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  async function decide(event: FormEvent) {
    event.preventDefault(); setError("");
    try {
      const payload: unknown = mode === "form" ? { ...call?.arguments, title: title.trim(), due_date: due || null } : JSON.parse(raw);
      if (!payload || Array.isArray(payload) || typeof payload !== "object") throw new Error("审批参数必须是 JSON 对象。");
      if (call?.name === "task") {
        const data = payload as Record<string, unknown>;
        if (typeof data.title !== "string" || !data.title.trim() || data.title.length > 200) throw new Error("任务标题需填写 1 至 200 个字符。");
      }
      await onDecision("approve", payload as Record<string, unknown>);
    } catch (cause) { setError(cause instanceof SyntaxError ? "参数格式不正确，请检查 JSON，或切回表单编辑。" : friendlyError(cause)); }
  }
  function changeMode() {
    if (mode === "form") { setRaw(JSON.stringify({ ...call?.arguments, title, due_date: due || null }, null, 2)); setMode("json"); }
    else {
      try {
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error();
        setTitle(String(parsed.title ?? "")); setDue(String(parsed.due_date ?? "")); setMode("form"); setError("");
      } catch { setError("请先修正 JSON 格式，再切回表单。"); }
    }
  }
  return <section className="approval">
    <div className="approval-intro"><span><Icon name="shield" size={22} /></span><div><h3>这一步，需要你确认</h3><p>即将执行「{toolNames[call?.name] || call?.name || "高风险操作"}」，批准后将立即继续。</p></div></div>
    {!canApprove && <p className="inline-notice">你可以查看此任务。批准或拒绝操作需要审批人或管理员权限。</p>}
    <form onSubmit={decide}><div className="approval-form-heading"><strong>核对执行内容</strong>{call?.name === "task" && <button type="button" className="inline-link" disabled={busy} onClick={changeMode}>{mode === "form" ? "编辑 JSON" : "表单编辑"}</button>}</div>
      {mode === "form" ? <><label>任务标题<input value={title} maxLength={200} required disabled={busy || !canApprove} onChange={e => setTitle(e.target.value)} /></label><label>截止日期 <span className="optional">选填</span><input aria-label="截止日期" type="date" value={due} disabled={busy || !canApprove} onChange={e => setDue(e.target.value)} /></label><p className="field-hint">未指定具体日期的相对时间不会被自动写入；可在此确认截止日期。</p></>
        : <label>执行参数<textarea aria-label="执行参数 JSON" rows={6} value={raw} disabled={busy || !canApprove} onChange={e => setRaw(e.target.value)} spellCheck={false} /></label>}
      {error && <p className="inline-notice error" role="alert">{error}</p>}
      <div className="approval-actions"><button className="primary" disabled={busy || !canApprove || !call}><Icon name={busy ? "refresh" : "check"} spin={busy} size={16} />{busy ? "处理中…" : "批准并继续"}</button><button type="button" className="reject-button" disabled={busy || !canApprove} onClick={() => setConfirm(!confirm)}>拒绝执行</button></div>
    </form>
    {confirm && <div className="reject-confirm"><label>拒绝原因<textarea aria-label="拒绝原因" maxLength={500} rows={2} placeholder="请说明原因，便于提交人调整任务。" value={reason} disabled={busy} onChange={e => setReason(e.target.value)} /></label><div className="button-row"><button className="danger-button" disabled={busy || !reason.trim()} onClick={() => void onDecision("reject", undefined, reason.trim())}>确认拒绝</button><button className="text-button" disabled={busy} onClick={() => setConfirm(false)}>取消</button></div></div>}
  </section>;
}

function Trace({ events, task }: { events: StreamEvent[]; task: Task }) {
  const descriptions: Record<string, [string, string]> = {
    task_created: ["任务已创建", "目标已保存，开始准备执行。"], planning: ["正在规划", "选择完成当前目标需要的工具。"],
    tool_started: ["开始调用工具", "按计划执行当前步骤。"], tool_finished: ["工具执行完成", "已收到工具返回结果。"],
    approval_required: ["等待人工审批", "操作已暂停，确认后继续执行。"], completed: ["任务完成", "最终结果已保存。"], failed: ["执行未完成", "请在结果页查看原因和恢复方式。"],
    approval_decided: ["审批已处理", "审批操作已返回，最新执行结果已同步。"], task_resumed: ["恢复请求已完成", "已从服务端读取最新任务状态。"],
  };
  return <><div className="subheading"><h3>{events.length ? "本次实时轨迹" : "已保存的执行记录"}</h3><span>{events.length ? `${events.length} 个事件` : "工具调用记录"}</span></div>{events.length ? <ol className="timeline">{events.map((event, index) => { const failed = event.type === "failed" || event.data.success === false; const label = event.data.success === false ? "工具调用失败" : descriptions[event.type]?.[0] || event.type; return <li key={index} className={`timeline-item ${failed ? "failed" : event.type === "approval_required" ? "waiting" : ""}`}><span className="timeline-dot"><Icon name={failed ? "close" : event.type === "approval_required" ? "clock" : "check"} size={12} /></span><div><div className="event-title"><strong>{label}{event.data.tool_name ? ` · ${toolNames[String(event.data.tool_name)] || String(event.data.tool_name)}` : ""}</strong><time>{event.receivedAt ? formatTime(new Date(event.receivedAt).toISOString(), false) : ""}</time></div><p>{descriptions[event.type]?.[1]}</p><details className="technical-details"><summary>事件数据</summary><pre>{JSON.stringify(event.data, null, 2)}</pre></details></div></li>; })}</ol>
      : <><p className="trace-note">历史任务展示已保存的调用状态；实时事件仅在当前页面会话中保留。</p>{task.tool_calls.length ? <ol className="timeline">{task.tool_calls.map(call => { const execution = executionOf(task, call); return <li key={call.call_id} className={`timeline-item ${execution.status}`}><span className="timeline-dot"><Icon name={execution.status === "success" ? "check" : execution.status === "failed" ? "close" : "clock"} size={12} /></span><div><strong>{toolNames[call.name] || call.name}</strong><p>{execution.label}{execution.result ? ` · ${Math.round(execution.result.latency_ms)} ms` : ""}</p></div></li>; })}</ol> : <Empty icon="activity" title="没有保存的工具记录">此任务可能直接生成了回答，或尚未完成规划。</Empty>}</>}</>;
}

function Help({ onClose }: { onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialogRef.current?.showModal(); }, []);
  return <dialog className="help-dialog" ref={dialogRef} onCancel={onClose} onClick={e => { if (e.target === e.currentTarget) { const box = e.currentTarget.getBoundingClientRect(); if (e.clientX < box.left || e.clientX > box.right || e.clientY < box.top || e.clientY > box.bottom) onClose(); } }} aria-labelledby="help-title"><div className="help-header"><span className="section-icon"><Icon name="book" /></span><h2 id="help-title">开始使用 FlowPilot</h2><button className="icon-button" autoFocus aria-label="关闭使用指南" onClick={onClose}><Icon name="close" /></button></div><ol className="help-steps"><li><strong>描述目标</strong><p>写清需要查询的信息、计算条件和最终结果。也可以使用场景模板。</p></li><li><strong>观察执行</strong><p>在任务详情中切换结果、工具调用和执行轨迹，查看每一步的实际状态。</p></li><li><strong>审批关键操作</strong><p>创建任务等写入操作会先暂停。审批人核对标题、日期后批准，或填写原因拒绝。</p></li><li><strong>回看与恢复</strong><p>通过搜索和筛选查找记录；可重试的失败任务提供恢复入口，结果可以复制或导出。</p></li></ol><div className="help-note"><Icon name="shield" size={18} /><p>规则演示模式使用固定规划逻辑。搜索和任务工具仍为本地演示适配器；完整模型规划与企业知识库由后端配置决定。</p></div></dialog>;
}

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("agent-token") || "");
  const [expired, setExpired] = useState(false);
  const logout = useCallback((wasExpired = false) => { sessionStorage.removeItem("agent-token"); setToken(""); setExpired(wasExpired); }, []);
  const login = useCallback((next: string) => { sessionStorage.setItem("agent-token", next); setExpired(false); setToken(next); }, []);
  return token ? <WorkspaceApp key={token} token={token} onLogout={logout} /> : <Login onLogin={login} expired={expired} />;
}
createRoot(document.getElementById("root")!).render(<App />);
