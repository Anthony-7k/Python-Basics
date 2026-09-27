import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { ApiClient, Role, StreamEvent, Task } from "./api";
import "./styles.css";

const roleOptions: Role[] = ["viewer", "operator", "approver", "admin"];

const statusText: Record<string, string> = {
  COMPLETED: "已完成",
  FAILED: "执行失败",
  WAITING_APPROVAL: "等待审批",
  RUNNING: "执行中",
  PENDING: "等待中",
};

const eventText: Record<string, [string, string]> = {
  task_created: ["任务已创建", "工作流已生成并进入执行队列"],
  planning: ["正在规划", "Agent 正在选择合适的执行步骤"],
  tool_started: ["工具开始执行", "正在调用已授权的企业工具"],
  tool_finished: ["工具执行完成", "调用结果已安全返回工作流"],
  approval_required: ["等待人工审批", "高风险操作已暂停"],
  completed: ["任务已完成", "最终结果已经生成"],
  failed: ["任务执行失败", "请查看错误信息后重试"],
};

type IconName = "spark" | "activity" | "history" | "result" | "play" | "refresh" | "logout" | "check" | "clock" | "task" | "arrow" | "shield";

const iconPaths: Record<IconName, string> = {
  spark: "M12 3l1.6 4.3L18 9l-4.4 1.7L12 15l-1.6-4.3L6 9l4.4-1.7L12 3zM5 15l.8 2.2L8 18l-2.2.8L5 21l-.8-2.2L2 18l2.2-.8L5 15z",
  activity: "M3 12h4l2-6 4 12 2-6h6",
  history: "M3 12a9 9 0 1 0 3-6.7L3 8m0-5v5h5m4-1v5l3 2",
  result: "M7 3h10l3 3v15H4V3h3m1 7h8m-8 4h8m-8 4h5",
  play: "M9 7l8 5-8 5V7z",
  refresh: "M20 6v5h-5M4 18v-5h5M5.5 9a7 7 0 0 1 12-2.5L20 11M4 13l2.5 4.5A7 7 0 0 0 18.5 15",
  logout: "M10 5H4v14h6m4-11 4 4-4 4m-6-4h10",
  check: "M5 12l4 4L19 6",
  clock: "M12 7v5l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z",
  task: "M5 3h14v18H5V3zm4 5h6m-6 4h6m-6 4h4",
  arrow: "M9 18l6-6-6-6",
  shield: "M12 3L5 6v5c0 4.6 2.8 8 7 10 4.2-2 7-5.4 7-10V6l-7-3zm-3 9 2 2 4-4",
};

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={iconPaths[name]} /></svg>;
}

function taskTitle(task: Task) {
  const title = task.tool_calls.find((call) => typeof call.arguments.title === "string")?.arguments.title;
  if (title) return String(title);
  return task.answer || (task.tool_calls[0] ? `调用 ${task.tool_calls[0].name} 工具` : "新建工作流任务");
}

function formatTime(value?: string) {
  if (!value) return "刚刚";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "刚刚" : new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("agent-token") ?? "");
  const [roles, setRoles] = useState<Role[]>(["operator", "approver"]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selected, setSelected] = useState<Task | null>(null);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [message, setMessage] = useState("查询上海差旅标准并计算 3 天最高报销金额");
  const [approvalPayload, setApprovalPayload] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const client = useMemo(() => token ? new ApiClient(token) : null, [token]);

  const stats = useMemo(() => {
    const completed = tasks.filter((task) => task.status === "COMPLETED").length;
    const pending = tasks.filter((task) => task.status === "WAITING_APPROVAL").length;
    const failed = tasks.filter((task) => task.status === "FAILED").length;
    const settled = completed + failed;
    return { completed, pending, successRate: settled ? Math.round(completed / settled * 100) : 100 };
  }, [tasks]);

  const refresh = useCallback(async () => {
    if (!client) return;
    try {
      const rows = await client.listTasks();
      setTasks(rows);
      if (selected) setSelected(rows.find((item) => item.task_id === selected.task_id) ?? selected);
    } catch (cause) { setError(String(cause)); }
  }, [client, selected]);

  useEffect(() => { void refresh(); }, [client]);
  useEffect(() => {
    const pending = selected?.tool_calls[selected.current_step];
    setApprovalPayload(selected?.status === "WAITING_APPROVAL" && pending ? JSON.stringify(pending.arguments, null, 2) : "");
  }, [selected?.task_id, selected?.status, selected?.current_step]);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setError("");
    try {
      const next = await ApiClient.devToken(String(data.get("subject")), String(data.get("tenant")), roles);
      sessionStorage.setItem("agent-token", next);
      setToken(next);
    } catch (cause) { setError(String(cause)); }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!client || !message.trim() || busy) return;
    setBusy(true); setError(""); setEvents([]); setSelected(null);
    try {
      let taskId = "";
      await client.streamTask(message.trim(), (item) => {
        setEvents((current) => [...current, item]);
        if (item.type === "task_created") taskId = String(item.data.task_id);
      });
      if (taskId) setSelected(await client.getTask(taskId));
      await refresh();
    } catch (cause) { setError(String(cause)); }
    finally { setBusy(false); }
  }

  async function decide(action: "approve" | "reject") {
    if (!client || !selected) return;
    setBusy(true); setError("");
    try {
      let modified: Record<string, unknown> | undefined;
      if (action === "approve" && approvalPayload.trim()) {
        const parsed: unknown = JSON.parse(approvalPayload);
        if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("审批参数必须是 JSON 对象");
        modified = parsed as Record<string, unknown>;
      }
      const next = action === "approve" ? await client.approve(selected.task_id, modified) : await client.reject(selected.task_id, "由控制台审批人拒绝");
      setSelected(next);
      await refresh();
    } catch (cause) { setError(String(cause)); }
    finally { setBusy(false); }
  }

  function logout() {
    sessionStorage.removeItem("agent-token");
    setToken(""); setSelected(null); setTasks([]);
  }

  if (!token) return <main className="login-shell">
    <section className="login-showcase">
      <div className="login-brand"><span><Icon name="spark" size={21} /></span><strong>FlowPilot</strong></div>
      <div className="login-copy"><p className="eyebrow light">ENTERPRISE AI WORKSPACE</p><h1>让复杂工作流，<br />变得清晰可控。</h1><p>统一编排企业知识、工具调用与人工审批，让每一次 Agent 执行都有迹可循。</p></div>
      <div className="login-proof"><div><Icon name="shield" /><span><strong>企业级安全</strong><small>租户隔离与角色权限</small></span></div><div><Icon name="activity" /><span><strong>全链路可观测</strong><small>实时追踪每个执行步骤</small></span></div></div>
    </section>
    <form className="login-card" onSubmit={login}>
      <div className="mobile-logo"><Icon name="spark" /></div>
      <p className="eyebrow">WELCOME BACK</p><h2>登录智能工作台</h2><p className="login-intro">使用演示身份体验完整的 Agent 工作流。</p>
      <label>用户标识<input name="subject" defaultValue="demo-user" required /></label>
      <label>租户空间<input name="tenant" defaultValue="portfolio-demo" required /></label>
      <fieldset><legend>演示角色</legend><div className="role-grid">{roleOptions.map((role) => <label key={role} className={`check ${roles.includes(role) ? "checked" : ""}`}><input type="checkbox" checked={roles.includes(role)} onChange={(e) => setRoles(e.target.checked ? [...roles, role] : roles.filter((item) => item !== role))} /><span>{role}</span></label>)}</div></fieldset>
      {error && <p role="alert" className="form-error">{error}</p>}
      <button className="primary login-button" type="submit">进入工作台 <Icon name="arrow" /></button>
      <p className="login-note"><Icon name="shield" size={14} />仅用于本地开发演示</p>
    </form>
  </main>;

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><span><Icon name="spark" size={18} /></span><strong>FlowPilot</strong><em>企业版</em></div>
      <div className="header-center"><span>智能工作流工作台</span><small>演示环境</small></div>
      <div className="header-actions"><span className="health"><i />服务运行正常</span><button className="icon-button" title="退出登录" onClick={logout}><Icon name="logout" /></button></div>
    </header>

    <main className="dashboard">
      <section className="welcome-row"><div><p className="eyebrow">AI OPERATIONS CENTER</p><h1>欢迎回来，开始今天的智能协作</h1><p>发起任务、观察执行过程，并安全审批每一项高风险操作。</p></div><div className="workspace-tag"><small>当前工作区</small><strong>portfolio-demo</strong></div></section>

      <section className="stats-grid" aria-label="工作台概览">
        <article><span className="stat-icon blue"><Icon name="task" /></span><div><small>任务总数</small><strong>{tasks.length}</strong></div><em>全部记录</em></article>
        <article><span className="stat-icon amber"><Icon name="clock" /></span><div><small>等待审批</small><strong>{stats.pending}</strong></div><em className={stats.pending ? "attention" : ""}>{stats.pending ? "需要处理" : "暂无待办"}</em></article>
        <article><span className="stat-icon green"><Icon name="check" /></span><div><small>已完成</small><strong>{stats.completed}</strong></div><em>稳定运行</em></article>
        <article><span className="stat-icon violet"><Icon name="activity" /></span><div><small>成功率</small><strong>{stats.successRate}%</strong></div><em>已结束任务</em></article>
      </section>

      <section className="workspace-grid">
        <article className="panel composer">
          <div className="panel-heading"><span className="heading-icon blue"><Icon name="spark" /></span><div><p className="eyebrow">NEW WORKFLOW</p><h2>发起新任务</h2></div><span className={`run-state ${busy ? "busy" : ""}`}><i />{busy ? "执行中" : "随时可用"}</span></div>
          <form onSubmit={submit}><label htmlFor="message">描述你希望 Agent 完成的工作</label><div className="prompt-box"><textarea id="message" value={message} onChange={(e) => setMessage(e.target.value)} rows={5} placeholder="例如：查询差旅标准并计算最高报销金额" /><span>{message.length}/4000</span></div><div className="quick-row"><span>快速开始</span><div className="quick-prompts"><button type="button" onClick={() => setMessage("查询公司年假制度")}>知识问答</button><button type="button" onClick={() => setMessage("查询上海差旅标准并计算 5 天最高报销金额")}>费用计算</button><button type="button" onClick={() => setMessage("创建任务：周五前提交预算复盘")}>审批演示</button></div></div><button className="primary submit-button" disabled={busy || !message.trim()}><Icon name={busy ? "activity" : "play"} />{busy ? "Agent 正在编排…" : "开始执行"}</button></form>
        </article>

        <article className="panel trace">
          <div className="panel-heading"><span className="heading-icon violet"><Icon name="activity" /></span><div><p className="eyebrow">LIVE TRACE</p><h2>实时执行轨迹</h2></div><span className="count-pill">{events.length} 个事件</span></div>
          <ol className="timeline" aria-live="polite">{events.length === 0 && <li className="trace-empty"><span><Icon name="activity" size={24} /></span><strong>等待任务开始</strong><p>执行后将在这里实时展示规划、工具调用和审批节点。</p></li>}{events.map((item, index) => { const copy = eventText[item.type] ?? [item.type, "工作流事件"]; return <li className="timeline-item" key={`${item.type}-${index}`}><span className={`event-dot ${item.type}`}><Icon name={item.type === "completed" ? "check" : item.type === "approval_required" ? "clock" : "activity"} size={12} /></span><div className="event-card"><div><strong>{copy[0]}</strong><time>步骤 {index + 1}</time></div><p>{copy[1]}</p><details><summary>查看事件数据</summary><pre>{JSON.stringify(item.data, null, 2)}</pre></details></div></li>; })}</ol>
        </article>

        <article className="panel history">
          <div className="panel-heading"><span className="heading-icon cyan"><Icon name="history" /></span><div><p className="eyebrow">RECENT RUNS</p><h2>最近任务</h2></div><button className="text-button" onClick={() => void refresh()}><Icon name="refresh" size={15} />刷新</button></div>
          <div className="task-list">{tasks.length === 0 && <div className="list-empty"><Icon name="history" /><span>还没有任务记录</span></div>}{tasks.map((task) => <button key={task.task_id} className={selected?.task_id === task.task_id ? "task active" : "task"} onClick={() => setSelected(task)}><span className={`task-marker ${task.status}`}><Icon name={task.status === "COMPLETED" ? "check" : task.status === "WAITING_APPROVAL" ? "clock" : "task"} size={14} /></span><span className="task-copy"><strong>{taskTitle(task)}</strong><small>{formatTime(task.updated_at ?? task.created_at)} · {task.current_step}/{task.max_steps} 步</small></span><span className={`status ${task.status}`}>{statusText[task.status] ?? task.status}</span><Icon name="arrow" size={15} /></button>)}</div>
        </article>

        <article className="panel detail">
          <div className="panel-heading"><span className="heading-icon orange"><Icon name="result" /></span><div><p className="eyebrow">TASK DETAIL</p><h2>任务详情</h2></div>{selected && <span className={`status ${selected.status}`}>{statusText[selected.status] ?? selected.status}</span>}</div>
          {!selected ? <div className="detail-empty"><span><Icon name="result" size={28} /></span><h3>选择一个任务查看详情</h3><p>从左侧任务列表选择记录，或发起一个新任务。</p></div> : <div className="detail-content">
            <section className="answer"><div><Icon name="spark" size={15} />Agent 结果</div><p>{selected.answer || (selected.status === "WAITING_APPROVAL" ? "任务已暂停，正在等待审批后继续执行。" : "Agent 正在处理这个任务…")}</p>{selected.error && <p className="error-message">{selected.error.error_type}: {selected.error.message}</p>}</section>
            {selected.status === "WAITING_APPROVAL" && <section className="approval"><div className="approval-heading"><span><Icon name="shield" /></span><div><h3>需要人工审批</h3><p>高风险操作已安全暂停，请核对参数后作出决定。</p></div></div><label htmlFor="approval-payload">待执行参数</label><textarea id="approval-payload" rows={6} value={approvalPayload} onChange={(event) => setApprovalPayload(event.target.value)} spellCheck={false} /><div className="approval-actions"><button className="primary approve-button" disabled={busy || !roles.some((role) => role === "approver" || role === "admin")} onClick={() => void decide("approve")}><Icon name="check" />批准并继续</button><button className="danger-button" disabled={busy || !roles.some((role) => role === "approver" || role === "admin")} onClick={() => void decide("reject")}>拒绝执行</button></div></section>}
            <section className="detail-section"><div className="subheading"><h3>工具调用</h3><span>{selected.tool_calls.length} 项</span></div><div className="tool-grid">{selected.tool_calls.length === 0 && <p className="inline-empty">此任务未调用工具</p>}{selected.tool_calls.map((call, index) => <article key={call.call_id}><span className="tool-index">{String(index + 1).padStart(2, "0")}</span><div><strong>{call.name}</strong><p>{call.selection_reason || "由 Agent 规划选择"}</p><code>{JSON.stringify(call.arguments)}</code></div><span className="tool-check"><Icon name="check" size={13} /></span></article>)}</div></section>
            {selected.sources.length > 0 && <section className="detail-section"><div className="subheading"><h3>引用来源</h3><span>{selected.sources.length} 项</span></div><ul className="sources">{selected.sources.map((source, index) => <li key={index}><span>S{index + 1}</span><div><strong>{String(source.title ?? source.source_id ?? "企业知识来源")}</strong><small>{String(source.locator ?? "内部知识库")}</small></div></li>)}</ul></section>}
          </div>}
        </article>
      </section>
    </main>
    {error && <div className="toast" role="alert"><span>!</span><p>{error}</p><button onClick={() => setError("")}>关闭</button></div>}
  </div>;
}

createRoot(document.getElementById("root")!).render(<App />);
