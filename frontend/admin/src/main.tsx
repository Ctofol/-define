import React from "react";
import { createRoot } from "react-dom/client";
import { ConfigProvider, Pagination, Progress } from "antd";
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { init as initChart, use as useChart } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import {
  Activity, BarChart3, BookOpen, CheckCircle2, ClipboardCheck, Database, Download,
  FileArchive, FileSearch, FileUp, Gauge, LogOut, PackageOpen, RefreshCw, Shield,
  Users, XCircle,
} from "lucide-react";
import "./styles.css";
import "./layout-fixes.css";

type User = { id: string; username: string; display_name: string; roles: string[]; is_active: boolean };
type Job = { id: string; file_name: string; source: string; media_type: string; status: string; progress: number; media_id?: string; result_json?: Record<string, unknown>; created_at: string };
type Review = { id: string; report_id?: string; analysis_job_id?: string; reason: string; status: string; reviewer_id?: string; decision?: string; corrected_species_name?: string; comment?: string; version: number; created_at: string };
type FieldReport = { id: string; analysis_job_id?: string; species_name: string; status: string; location_text: string; notes: string; observed_at: string; final_species_name?: string };
type Detection = { species_label?: string; confidence?: number; classification_confidence?: number; preview_crop_path?: string; top_candidates?: Array<{ label: string; confidence: number; latin_name?: string; protection_level?: string }> };
type Model = { id: string; pipeline: string; version: string; taxon_group: string; threshold: number; metrics: Record<string, number>; is_active: boolean };
type Species = { species_id: string; cn_name: string; latin_name?: string; category: string; protection_level: string; family?: string };
type ReportsOverview = {
  patrol: { media_count: number; succeeded_count: number; pending_review_count: number };
  species: { species_count: number; detection_count: number; reviewed_report_count: number };
  annual: { month_count: number; media_count: number; resolved_review_count: number };
};
type Page = "dashboard" | "batch" | "reviews" | "media" | "species" | "models" | "reports";

useChart([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

const configuredApiBase = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";
const deployedApiFallback = window.location.port === "5002"
  ? `${window.location.protocol}//${window.location.hostname}:5001`
  : "";
const configuredApiIsLoopback = /^https?:\/\/(localhost|127(?:\.\d{1,3}){3})(?::|\/|$)/i.test(configuredApiBase);
const pageIsLoopback = /^(localhost|127(?:\.\d{1,3}){3})$/i.test(window.location.hostname);
const apiBase = configuredApiIsLoopback && !pageIsLoopback ? deployedApiFallback : configuredApiBase || deployedApiFallback;
const nav: Array<{ page: Page; label: string; icon: React.ReactNode }> = [
  { page: "dashboard", label: "监测数据总览", icon: <Gauge size={18} /> },
  { page: "reviews", label: "专家复核中心", icon: <ClipboardCheck size={18} /> },
  { page: "media", label: "监测数据管理", icon: <Database size={18} /> },
  { page: "species", label: "物种资源管理", icon: <BookOpen size={18} /> },
  { page: "reports", label: "统计与系统管理", icon: <BarChart3 size={18} /> },
];

function App() {
  const [token, setToken] = React.useState("");
  const [user, setUser] = React.useState<User | null>(null);
  const [page, setPage] = React.useState<Page>("dashboard");
  const [booting, setBooting] = React.useState(true);

  React.useEffect(() => {
    fetch(`${apiBase}/api/v1/auth/refresh`, { method: "POST", credentials: "include" })
      .then(async (response) => response.ok ? response.json() : null)
      .then((payload) => { if (payload) { setToken(payload.access_token); setUser(payload.user); } })
      .finally(() => setBooting(false));
  }, []);

  async function login(username: string, password: string) {
    const response = await fetch(`${apiBase}/api/v1/auth/login`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
    if (!response.ok) throw new Error((await response.json()).detail ?? "登录失败");
    const payload = await response.json();
    setToken(payload.access_token); setUser(payload.user);
  }

  async function logout() {
    await fetch(`${apiBase}/api/v1/auth/logout`, { method: "POST", credentials: "include" });
    setToken(""); setUser(null);
  }

  if (booting) return <div className="center"><RefreshCw className="spin" /> 正在恢复会话…</div>;
  if (!user) return <Login onLogin={login} />;
  const api = async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const headers = new Headers(init?.headers); headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(`${apiBase}${path}`, { ...init, headers, credentials: "include" });
    if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail ?? `请求失败 (${response.status})`);
    if (response.status === 204) return undefined as T;
    const contentType = response.headers.get("content-type") ?? "";
    return (contentType.includes("json") ? response.json() : response.blob()) as Promise<T>;
  };

  return <div className="admin-shell">
    <aside className="sidebar">
      <div className="brand"><span className="logo">森</span><div><strong>森智眼</strong><small>PC 管理端</small></div></div>
      <nav>{nav.map((item) => <button className={page === item.page ? "active" : ""} onClick={() => setPage(item.page)} key={item.page}>{item.icon}<span>{item.label}</span></button>)}</nav>
      <button className="logout" onClick={logout}><LogOut size={17} />退出 · {user.display_name}</button>
    </aside>
    <main className="workspace">
       <header><div><small>广西动植物智能监测平台</small><h1>{nav.find((item) => item.page === page)?.label}</h1></div><span className="role"><Shield size={15} />{user.roles.map(formatRole).join(" / ")}</span></header>
      {page === "dashboard" && <Dashboard api={api} />}
      {page === "batch" && <Batch api={api} />}
      {page === "reviews" && <Reviews api={api} />}
      {page === "media" && <Media api={api} onReview={() => setPage("reviews")} />}
      {page === "species" && <SpeciesResources api={api} />}
      {page === "models" && <Models api={api} />}
      {page === "reports" && <ManagementCenter api={api} />}
    </main>
  </div>;
}

function Login({ onLogin }: { onLogin: (username: string, password: string) => Promise<void> }) {
  const [username, setUsername] = React.useState("admin"); const [password, setPassword] = React.useState(""); const [error, setError] = React.useState("");
  return <main className="login-page"><form onSubmit={(event) => { event.preventDefault(); setError(""); void onLogin(username, password).catch((reason) => setError(reason.message)); }}>
    <span className="login-mark">森</span><small>广西动植物智能监测平台</small><h1>PC 管理端</h1><p>监测、复核、资源与模型统一管理</p>
    <label>账号<input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" /></label>
    <label>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" /></label>
    {error && <div className="error">{error}</div>}<button type="submit">登录管理端</button>
  </form></main>;
}

function useLoad<T>(loader: () => Promise<T>, initial: T) {
  const [data, setData] = React.useState(initial); const [error, setError] = React.useState(""); const [loading, setLoading] = React.useState(true);
  const reload = React.useCallback(() => { setLoading(true); setError(""); loader().then(setData).catch((reason) => setError(reason.message)).finally(() => setLoading(false)); }, []);
  React.useEffect(reload, [reload]); return { data, error, loading, reload };
}

function Dashboard({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) {
  const state = useLoad(async () => {
    const [overview, jobs] = await Promise.all([
      api<Record<string, number | boolean>>("/api/v1/admin/analytics/overview"),
      api<Job[]>("/api/v1/admin/media"),
    ]);
    return { overview, jobs };
  }, { overview: {} as Record<string, number | boolean>, jobs: [] as Job[] });
  const cards = [["素材数量", state.data.overview.media_count ?? 0], ["动物检出数量", state.data.overview.detection_count ?? 0], ["重点物种上报", state.data.overview.priority_species_count ?? 0], ["待复核记录", state.data.overview.pending_review_count ?? 0]];
  const recentJobs = state.data.jobs.slice(0, 6);
  return <PageState state={state}>
    <section className="metrics">{cards.map(([label, value]) => <article key={String(label)}><Activity size={20} /><span>{label}</span><strong>{String(value)}</strong></article>)}</section>
    <section className="grid two">
      <Panel title="监测数据分布"><TrendChart values={cards.map((item) => Number(item[1]))} labels={cards.map((item) => String(item[0]))}/></Panel>
      <Panel title="处理闭环"><div className="pipeline"><b>素材导入</b><i>→</i><b>异步识别</b><i>→</i><b>规则入队</b><i>→</i><b>专家复核</b></div><Status ok text="动物识别管线已接入"/><Status ok={Boolean(state.data.overview.plant_recognition_enabled)} text={state.data.overview.plant_recognition_enabled ? "植物识别已启用" : "植物识别接口已预留"}/></Panel>
    </section>
    <section className="dashboard-activity-panel"><Panel title="最近识别动态">
      <div className="dashboard-activity-list">
        {recentJobs.map((job) => {
          const result = job.result_json as { detections?: Detection[] } | undefined;
          return <article key={job.id}>
            <span className="dashboard-activity-icon"><FileSearch size={18}/></span>
            <span className="dashboard-activity-file"><strong>{job.file_name}</strong><small>{formatSource(job.source)} · {formatMediaType(job.media_type)} · {formatTime(job.created_at)}</small></span>
            <Badge value={job.status}/>
            <strong className="dashboard-activity-count">{job.status === "succeeded" ? `${result?.detections?.length ?? 0} 个目标` : `${job.progress}%`}</strong>
          </article>;
        })}
        {!recentJobs.length ? <div className="center">暂无识别动态</div> : null}
      </div>
    </Panel></section>
  </PageState>;
}

function Batch({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) {
  const [files, setFiles] = React.useState<FileList | null>(null); const [site, setSite] = React.useState(""); const [camera, setCamera] = React.useState(""); const [message, setMessage] = React.useState(""); const [busy, setBusy] = React.useState(false);
  async function submit() { if (!files?.length) return; setBusy(true); setMessage(""); const body = new FormData(); Array.from(files).forEach((file) => body.append("files", file)); if (site) body.append("site_id", site); if (camera) body.append("camera_code", camera); try { const jobs = await api<Job[]>("/api/v1/uploads/batch", { method: "POST", body }); setMessage(`已创建 ${jobs.length} 个异步分析任务`); } catch (reason) { setMessage((reason as Error).message); } finally { setBusy(false); } }
  return <Panel title="红外相机素材批量导入"><div className="upload-zone"><FileArchive size={42}/><h2>选择图片、视频或 ZIP 压缩包</h2><p>服务端将执行安全解压、抽帧、空场景过滤、候选识别和复核入队。</p><input type="file" multiple accept="image/*,video/*,.zip" onChange={(event) => setFiles(event.target.files)} /></div><div className="form-row"><label>监测点<input value={site} onChange={(e) => setSite(e.target.value)} placeholder="可选"/></label><label>相机编号<input value={camera} onChange={(e) => setCamera(e.target.value)} placeholder="可选"/></label><button onClick={submit} disabled={busy || !files?.length}>{busy ? "正在提交…" : "创建批量任务"}</button></div>{message && <div className="notice">{message}</div>}</Panel>;
}

function Reviews({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) {
  const state = useLoad(async () => {
    const [reviews, jobs, reports] = await Promise.all([
      api<Review[]>("/api/v1/admin/reviews"),
      api<Job[]>("/api/v1/admin/media"),
      api<FieldReport[]>("/api/v1/admin/field-reports").catch(() => []),
    ]);
    return { reviews, jobs: new Map(jobs.map((job) => [job.id, job])), reports: new Map(reports.map((report) => [report.id, report])) };
  }, { reviews: [] as Review[], jobs: new Map<string, Job>(), reports: new Map<string, FieldReport>() });
  const [openId, setOpenId] = React.useState<string | null>(null);
  const [species, setSpecies] = React.useState("");
  const [comment, setComment] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  async function claim(task: Review) {
    setBusy(true); setMessage("");
    try { await api(`/api/v1/admin/reviews/${task.id}/claim`, { method: "POST" }); setMessage("任务已进入核验状态，请查看图片并提交结论。"); state.reload(); }
    catch (reason) { setMessage((reason as Error).message); } finally { setBusy(false); }
  }
  async function decide(task: Review, decision: "confirmed" | "corrected" | "rejected") {
    if (decision === "corrected" && !species.trim()) { setMessage("请选择或填写修正后的物种名称。"); return; }
    setBusy(true); setMessage("");
    try {
      await api(`/api/v1/admin/reviews/${task.id}/decision`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ version: task.version, decision, corrected_species_name: decision === "corrected" ? species.trim() : undefined, comment: comment.trim(), promote_to_sample: decision !== "rejected" }) });
      setMessage(decision === "confirmed" ? "核验完成：已确认模型结果。" : decision === "corrected" ? "核验完成：已保存人工修正。" : "核验完成：该识别结果已驳回。");
      setOpenId(null); setSpecies(""); setComment(""); state.reload();
    } catch (reason) { setMessage((reason as Error).message); } finally { setBusy(false); }
  }
  return <PageState state={state}><Panel title="专家人工核验">{message && <div className="notice">{message}</div>}<div className="review-list">{state.data.reviews.map((task) => {
    const job = task.analysis_job_id ? state.data.jobs.get(task.analysis_job_id) : undefined;
    const report = task.report_id ? state.data.reports.get(task.report_id) : undefined;
    const result = job?.result_json as { preview_url?: string; detections?: Detection[] } | undefined;
    const detection = result?.detections?.[0];
    const imageUrl = detection?.preview_crop_path || result?.preview_url;
    const expanded = openId === task.id;
    return <article className={`review-card ${expanded ? "expanded" : ""}`} key={task.id}>
      <button className="review-summary" onClick={() => { setOpenId(expanded ? null : task.id); setSpecies(report?.species_name ?? detection?.species_label ?? ""); setComment(report?.notes ?? ""); }}>
        <span className="review-thumb">{imageUrl ? <img src={`${apiBase}${imageUrl}`} alt="待核验监测图片"/> : <FileSearch size={28}/>}</span>
        <span><strong>{report?.species_name || detection?.species_label || "待确认物种"}</strong><small>{report ? `移动端上报 · ${report.location_text || "未填写地点"}` : formatReviewReason(task.reason)}</small></span>
        <span className={`review-status ${task.status}`}>{task.status === "pending" ? "待核验" : task.status === "claimed" ? "核验中" : "已完成"}</span>
        <span className="review-toggle">{expanded ? "收起" : "查看详情"}</span>
      </button>
      {expanded && <div className="review-detail">
        <div className="review-image">{imageUrl ? <img src={`${apiBase}${imageUrl}`} alt="待核验监测大图"/> : <div className="empty-image"><FileSearch/><span>该记录未关联可查看的识别图片</span></div>}</div>
        <div className="review-evidence"><h3>{report ? "移动端上报信息" : "模型识别依据"}</h3><p>文件：{job?.file_name ?? "移动端人工上报"}</p>{report && <><p>上报物种：<b>{report.species_name}</b></p><p>观测地点：{report.location_text || "未填写"}</p><p>上报备注：{report.notes || "无"}</p></>}{!report && <p>模型判断：<b>{detection?.species_label ?? "暂无"}</b>{detection?.confidence != null && `（${Math.round(detection.confidence * 100)}%）`}</p>}
          <div className="candidate-list">{detection?.top_candidates?.slice(0, 3).map((candidate) => <button key={`${candidate.label}-${candidate.confidence}`} onClick={() => setSpecies(candidate.label)}><b>{candidate.label}</b><span>{Math.round(candidate.confidence * 100)}%</span><small>{candidate.latin_name || candidate.protection_level || "候选物种"}</small></button>)}</div>
          {task.status === "resolved" ? <div className="resolved-note">处理结论：{task.decision === "confirmed" ? "确认" : task.decision === "corrected" ? `修正为 ${task.corrected_species_name || "其他物种"}` : "驳回"}</div> : task.status === "pending" ? <button onClick={() => claim(task)} disabled={busy}>开始核验</button> : <div className="review-form"><label>人工核验物种<input value={species} onChange={(event) => setSpecies(event.target.value)} placeholder="选择候选或输入正确物种"/></label><label>核验意见<textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="填写判断依据或备注（可选）"/></label><div className="actions"><button onClick={() => decide(task, "confirmed")} disabled={busy}>确认模型结果</button><button onClick={() => decide(task, "corrected")} disabled={busy}>保存人工修正</button><button className="danger" onClick={() => decide(task, "rejected")} disabled={busy}>无法确认 / 驳回</button></div></div>}
        </div>
      </div>}
    </article>;
  })}</div></Panel></PageState>;
}

function Media({ api, onReview }: { api: <T>(path: string, init?: RequestInit) => Promise<T>; onReview: () => void }) {
  const state = useLoad(() => api<Job[]>("/api/v1/admin/media"), []);
  const [openId, setOpenId] = React.useState<string | null>(null);
  async function download() { const blob = await api<Blob>("/api/v1/admin/media/export.csv", { headers: { Accept: "text/csv" } }); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "monitoring-data.csv"; link.click(); URL.revokeObjectURL(url); }
  return <PageState state={state}><Panel title="监测素材与识别记录"><div className="toolbar"><span>共 {state.data.length} 条监测记录</span><button onClick={download}><Download size={15}/>导出数据</button></div><div className="media-list">{state.data.map((job) => {
    const result = job.result_json as { preview_url?: string; detections?: Detection[]; species_summary?: Record<string, number> } | undefined;
    const imageUrl = result?.preview_url || result?.detections?.[0]?.preview_crop_path;
    const expanded = openId === job.id;
    return <article className="media-record" key={job.id}>
      <button className="media-summary" onClick={() => setOpenId(expanded ? null : job.id)}>
        <span className="media-thumb">{imageUrl ? <img src={`${apiBase}${imageUrl}`} alt="监测素材缩略图"/> : <FileSearch size={25}/>}</span>
        <span className="media-file"><strong>{job.file_name}</strong><small>{formatSource(job.source)} · {formatMediaType(job.media_type)} · {formatTime(job.created_at)}</small></span>
        <Badge value={job.status}/><span className="media-progress">{job.status === "succeeded" ? `检出 ${result?.detections?.length ?? 0} 个目标` : job.status === "failed" ? "处理未完成" : <Progress percent={job.progress} size="small"/>}</span><span className="review-toggle">{expanded ? "收起" : "查看详情"}</span>
      </button>
      {expanded && <div className="media-detail">
        <div className="media-preview">{imageUrl ? <img src={`${apiBase}${imageUrl}`} alt="监测素材预览"/> : <div className="empty-image"><FileSearch/><span>暂无可预览图片</span></div>}</div>
        <div className="media-results"><h3>识别结果</h3>{job.status !== "succeeded" ? <p>当前任务状态：{formatStatus(job.status)}，识别完成后将在此展示结果。</p> : !result?.detections?.length ? <p>该素材中未检测到可识别目标。</p> : <>{result.detections.map((detection, index) => <section className="detection-result" key={`${detection.species_label}-${index}`}><div><strong>{detection.species_label || "待确认物种"}</strong><span>{detection.confidence != null ? `${Math.round(detection.confidence * 100)}%` : "置信度未知"}</span></div><small>候选物种：{detection.top_candidates?.slice(0, 3).map((item) => `${item.label} ${Math.round(item.confidence * 100)}%`).join("、") || "暂无"}</small></section>)}</>}
          <dl><div><dt>数据来源</dt><dd>{formatSource(job.source)}</dd></div><div><dt>素材类型</dt><dd>{formatMediaType(job.media_type)}</dd></div><div><dt>任务编号</dt><dd>{job.id}</dd></div></dl>
          {result?.detections?.length ? <button onClick={onReview}><ClipboardCheck size={16}/>前往专家复核</button> : null}
        </div>
      </div>}
    </article>;
  })}</div></Panel></PageState>;
}

function SpeciesResources({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) {
  const state = useLoad(() => api<{ species: Species[] }>("/api/v1/species"), { species: [] });
  const [currentPage, setCurrentPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(20);
  const [importFile, setImportFile] = React.useState<File | null>(null);
  const [importMessage, setImportMessage] = React.useState("");
  const [importBusy, setImportBusy] = React.useState(false);
  const start = (currentPage - 1) * pageSize;
  const rows = state.data.species.slice(start, start + pageSize);
  React.useEffect(() => { if (currentPage > Math.max(1, Math.ceil(state.data.species.length / pageSize))) setCurrentPage(1); }, [currentPage, pageSize, state.data.species.length]);
  async function importSpecies() {
    if (!importFile || importBusy) return;
    setImportBusy(true);
    setImportMessage("");
    const body = new FormData();
    body.append("file", importFile);
    try {
      const result = await api<{ created: number; updated: number; total: number }>("/api/v1/admin/species/import", { method: "POST", body });
      setImportMessage(`导入完成：新增 ${result.created} 条，更新 ${result.updated} 条，共处理 ${result.total} 条。`);
      setImportFile(null);
      await state.reload();
    } catch (reason) {
      setImportMessage((reason as Error).message || "导入失败");
    } finally {
      setImportBusy(false);
    }
  }
  async function downloadTemplate() {
    const blob = await api<Blob>("/api/v1/admin/species/import-template", { headers: { Accept: "application/octet-stream" } });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "species-import-template.json";
    link.click();
    URL.revokeObjectURL(url);
  }
  return <PageState state={state}><Panel title="动植物知识库与图鉴">
    <div className="species-import">
      <div><strong>导入物种资源</strong><span>支持 CSV / JSON，使用 species_id 区分新增或更新。</span></div>
      <div className="species-import-actions">
        <label className="file-picker"><FileUp size={16}/><span>{importFile?.name || "选择资源文件"}</span><input type="file" accept=".csv,.json,application/json,text/csv" onChange={(event) => setImportFile(event.target.files?.[0] ?? null)} /></label>
        <button type="button" onClick={importSpecies} disabled={!importFile || importBusy}>{importBusy ? "导入中…" : "开始导入"}</button>
        <button className="template-download" type="button" onClick={downloadTemplate}><Download size={16}/>下载导入模板</button>
      </div>
      {importMessage ? <div className="notice">{importMessage}</div> : null}
    </div>
    <div className="toolbar"><span>共 {state.data.species.length} 个物种</span><small>统一维护分类、科属、生境、保护等级和资料来源。</small></div><DataTable headers={["中文名", "学名", "类别", "科", "保护等级"]}>{rows.map((item) => <tr key={item.species_id}><td>{item.cn_name}</td><td><i>{item.latin_name || "-"}</i></td><td>{formatCategory(item.category)}</td><td>{item.family || "-"}</td><td>{item.protection_level}</td></tr>)}</DataTable><div className="pagination-bar"><span>第 {currentPage} 页，共 {Math.max(1, Math.ceil(state.data.species.length / pageSize))} 页</span><Pagination current={currentPage} pageSize={pageSize} total={state.data.species.length} showSizeChanger pageSizeOptions={[20, 50, 100]} showQuickJumper onChange={(page, size) => { setCurrentPage(size !== pageSize ? 1 : page); setPageSize(size); }} /></div></Panel></PageState>;
}

function Models({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) {
  const models = useLoad(() => api<Model[]>("/api/v1/admin/models"), []); const samples = useLoad(() => api<Array<Record<string, string>>>("/api/v1/admin/samples"), []);
  async function activate(id: string) { await api(`/api/v1/admin/models/${id}/activate`, { method: "POST" }); models.reload(); }
  return <><section className="metrics"><article><PackageOpen/><span>模型版本</span><strong>{models.data.length}</strong></article><article><FileSearch/><span>候选样本</span><strong>{samples.data.length}</strong></article></section><Panel title="模型版本与发布"><DataTable headers={["管线", "版本", "类群", "阈值", "状态", "操作"]}>{models.data.map((model) => <tr key={model.id}><td>{model.pipeline}</td><td>{model.version}</td><td>{model.taxon_group}</td><td>{model.threshold}</td><td><Badge value={model.is_active ? "active" : "inactive"}/></td><td>{!model.is_active && <button onClick={() => activate(model.id)}>发布</button>}</td></tr>)}</DataTable></Panel></>;
}

function Reports({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) {
  const fallback: ReportsOverview = {
    patrol: { media_count: 0, succeeded_count: 0, pending_review_count: 0 },
    species: { species_count: 0, detection_count: 0, reviewed_report_count: 0 },
    annual: { month_count: 0, media_count: 0, resolved_review_count: 0 },
  };
  const state = useLoad(() => api<ReportsOverview>("/api/v1/admin/reports/overview"), fallback);
  async function download(path: string, filename: string) {
    const blob = await api<Blob>(path, { headers: { Accept: "text/csv" } });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }
  const cards = [
    {
      title: "巡护报告",
      stats: [["素材", state.data.patrol.media_count], ["完成", state.data.patrol.succeeded_count], ["待复核", state.data.patrol.pending_review_count]],
      text: "按素材来源、监测点、相机编号和处理状态汇总巡护数据。",
      path: "/api/v1/admin/reports/patrol.csv",
      filename: "patrol-report.csv",
    },
    {
      title: "物种发现记录",
      stats: [["物种", state.data.species.species_count], ["发现", state.data.species.detection_count], ["复核上报", state.data.species.reviewed_report_count]],
      text: "按物种聚合识别结果和已复核移动端上报。",
      path: "/api/v1/admin/reports/species.csv",
      filename: "species-discovery-report.csv",
    },
    {
      title: "年度监测报告",
      stats: [["月份", state.data.annual.month_count], ["素材", state.data.annual.media_count], ["已复核", state.data.annual.resolved_review_count]],
      text: "按月份汇总素材量、检出目标和复核完成情况。",
      path: "/api/v1/admin/reports/annual.csv",
      filename: "annual-monitoring-report.csv",
    },
  ];
  return <PageState state={state}><section className="grid three report-cards">{cards.map((card) => <Panel title={card.title} key={card.title}><BarChart3 size={34}/><div className="report-stat-row">{card.stats.map(([label, value]) => <span key={label}><b>{value}</b><small>{label}</small></span>)}</div><p>{card.text}</p><button onClick={() => download(card.path, card.filename)}><Download size={15}/>导出{card.title}</button></Panel>)}</section></PageState>;
}

function ManagementCenter({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) {
  return <div className="management-center"><section><div className="section-heading"><h2>统计分析与报告</h2><span>基于已确认的监测与复核数据生成</span></div><Reports api={api}/></section><section><div className="section-heading"><h2>用户与系统管理</h2><span>账号权限与系统维护</span></div><SystemPage api={api}/></section></div>;
}

function SystemPage({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) {
  const users = useLoad(() => api<User[]>("/api/v1/admin/users"), []); const [backup, setBackup] = React.useState(""); const [showCreate, setShowCreate] = React.useState(false); const [newUser, setNewUser] = React.useState({ username: "", display_name: "", password: "", role: "patrol_user" }); const [userMessage, setUserMessage] = React.useState("");
  async function createUser(event: React.FormEvent) { event.preventDefault(); setUserMessage(""); try { await api("/api/v1/admin/users", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: newUser.username.trim(), display_name: newUser.display_name.trim(), password: newUser.password, roles: [newUser.role] }) }); setNewUser({ username: "", display_name: "", password: "", role: "patrol_user" }); setShowCreate(false); setUserMessage("账号已创建"); users.reload(); } catch (reason) { setUserMessage((reason as Error).message || "创建账号失败"); } }
  return <section className="grid two"><Panel title="账号与角色"><div className="panel-toolbar"><span>当前共 {users.data.length} 个账号</span><button type="button" onClick={() => setShowCreate((value) => !value)}>{showCreate ? "收起" : "新增账号"}</button></div>{showCreate ? <form className="user-create-form" onSubmit={createUser}><label>账号<input value={newUser.username} onChange={(event) => setNewUser({ ...newUser, username: event.target.value })} required /></label><label>姓名<input value={newUser.display_name} onChange={(event) => setNewUser({ ...newUser, display_name: event.target.value })} required /></label><label>初始密码<input type="password" value={newUser.password} onChange={(event) => setNewUser({ ...newUser, password: event.target.value })} minLength={8} required /></label><label>角色<select value={newUser.role} onChange={(event) => setNewUser({ ...newUser, role: event.target.value })}><option value="patrol_user">巡护用户</option><option value="reviewer">专家复核员</option><option value="data_operator">数据管理员</option><option value="system_admin">系统管理员</option></select></label><button type="submit">保存账号</button></form> : null}{userMessage ? <div className="notice">{userMessage}</div> : null}<DataTable headers={["账号", "姓名", "角色", "状态"]}>{users.data.map((item) => <tr key={item.id}><td>{item.username}</td><td>{item.display_name}</td><td>{item.roles.map(formatRole).join("、")}</td><td><Badge value={item.is_active ? "active" : "disabled"}/></td></tr>)}</DataTable></Panel><Panel title="系统维护"><Status ok text="接口权限由后端 RBAC 强制执行"/><Status ok text="关键操作写入审计日志"/><button onClick={() => api<{ id: string }>("/api/v1/admin/backups", { method: "POST" }).then((data) => setBackup(data.id))}>创建备份清单</button>{backup && <div className="notice">已创建：{backup}</div>}</Panel></section>;
}

function Panel({ title, children }: React.PropsWithChildren<{ title: string }>) { return <section className="panel"><div className="panel-title"><h2>{title}</h2></div>{children}</section>; }
function TrendChart({ labels, values }: { labels: string[]; values: number[] }) { const ref = React.useRef<HTMLDivElement>(null); React.useEffect(() => { if (!ref.current) return; const chart = initChart(ref.current); chart.setOption({ grid: { left: 48, right: 18, top: 20, bottom: 42 }, tooltip: {}, xAxis: { type: "category", data: labels, axisLabel: { interval: 0 } }, yAxis: { type: "value", minInterval: 1 }, series: [{ type: "bar", data: values, itemStyle: { color: "#16805d", borderRadius: [6, 6, 0, 0] } }] }); const resize = () => chart.resize(); window.addEventListener("resize", resize); return () => { window.removeEventListener("resize", resize); chart.dispose(); }; }, [labels.join("|"), values.join("|")]); return <div className="trend-chart" ref={ref}/>; }
function DataTable({ headers, children }: React.PropsWithChildren<{ headers: string[] }>) { return <div className="table-wrap"><table><thead><tr>{headers.map((item) => <th key={item}>{item}</th>)}</tr></thead><tbody>{children}</tbody></table></div>; }
function Badge({ value }: { value: string }) { return <span className={`badge ${value}`}>{formatStatus(value)}</span>; }
function Status({ ok, text }: { ok: boolean; text: string }) { return <div className="status">{ok ? <CheckCircle2 color="#16805d"/> : <XCircle color="#b7791f"/>}<span>{text}</span></div>; }
function PageState({ state, children }: React.PropsWithChildren<{ state: { loading: boolean; error: string; reload: () => void } }>) { if (state.loading) return <div className="center"><RefreshCw className="spin"/>加载中…</div>; if (state.error) return <div className="error">{state.error}<button onClick={state.reload}>重试</button></div>; return <>{children}</>; }
function formatTime(value: string) { return new Date(value).toLocaleString("zh-CN", { hour12: false }); }
function formatStatus(value: string) { return ({ pending: "待处理", claimed: "核验中", resolved: "已完成", active: "启用", inactive: "未启用", queued: "等待识别", succeeded: "识别完成", failed: "识别失败", running: "正在识别", disabled: "停用" } as Record<string, string>)[value] ?? value; }
function formatRole(value: string) { return ({ system_admin: "系统管理员", expert_reviewer: "专家复核员", analyst: "分析员" } as Record<string, string>)[value] ?? value; }
function formatSource(value: string) { return ({ mobile: "移动端上传", admin_batch: "管理端批量导入", legacy_migration: "历史数据迁移", upload: "文件上传" } as Record<string, string>)[value] ?? value; }
function formatMediaType(value: string) { return ({ image: "图片", video: "视频" } as Record<string, string>)[value] ?? value; }
function formatCategory(value: string) { return ({ plant: "植物", bird: "鸟类", mammal: "哺乳动物", animal: "动物", reptile: "爬行动物", amphibian: "两栖动物", insect: "昆虫" } as Record<string, string>)[value] ?? value; }
function formatReviewReason(value: string) {
  const labels: Record<string, string> = { weak_reference_evidence: "参考证据不足", protected_species_candidate: "疑似重点保护物种", low_confidence: "识别置信度较低", close_top_candidates: "候选物种接近", knowledge_only_species: "知识库物种待确认" };
  return value.split(";").map((item) => labels[item.trim()] ?? item.trim()).filter(Boolean).join("；");
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><ConfigProvider theme={{ token: { colorPrimary: "#16805d", borderRadius: 8 } }}><App/></ConfigProvider></React.StrictMode>);
