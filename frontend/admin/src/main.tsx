import React from "react";
import { createRoot } from "react-dom/client";
import { ConfigProvider, Progress } from "antd";
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { init as initChart, use as useChart } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import {
  Activity, BarChart3, BookOpen, CheckCircle2, ClipboardCheck, Database, Download,
  FileArchive, FileSearch, Gauge, LogOut, PackageOpen, RefreshCw, Settings, Shield,
  UploadCloud, Users, XCircle,
} from "lucide-react";
import "./styles.css";

type User = { id: string; username: string; display_name: string; roles: string[]; is_active: boolean };
type Job = { id: string; file_name: string; source: string; media_type: string; status: string; progress: number; media_id?: string; created_at: string };
type Review = { id: string; report_id?: string; analysis_job_id?: string; reason: string; status: string; reviewer_id?: string; decision?: string; version: number; created_at: string };
type Model = { id: string; pipeline: string; version: string; taxon_group: string; threshold: number; metrics: Record<string, number>; is_active: boolean };
type Species = { species_id: string; cn_name: string; latin_name?: string; category: string; protection_level: string; family?: string };
type Page = "dashboard" | "batch" | "reviews" | "media" | "species" | "models" | "reports" | "system";

useChart([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

const apiBase = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";
const nav: Array<{ page: Page; label: string; icon: React.ReactNode }> = [
  { page: "dashboard", label: "监测数据总览", icon: <Gauge size={18} /> },
  { page: "batch", label: "批量智能分析", icon: <UploadCloud size={18} /> },
  { page: "reviews", label: "专家复核中心", icon: <ClipboardCheck size={18} /> },
  { page: "media", label: "监测数据管理", icon: <Database size={18} /> },
  { page: "species", label: "物种资源管理", icon: <BookOpen size={18} /> },
  { page: "models", label: "样本与模型管理", icon: <PackageOpen size={18} /> },
  { page: "reports", label: "统计分析与报告", icon: <BarChart3 size={18} /> },
  { page: "system", label: "用户与系统管理", icon: <Settings size={18} /> },
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
      <header><div><small>广西动植物智能监测平台</small><h1>{nav.find((item) => item.page === page)?.label}</h1></div><span className="role"><Shield size={15} />{user.roles.join(" / ")}</span></header>
      {page === "dashboard" && <Dashboard api={api} />}
      {page === "batch" && <Batch api={api} />}
      {page === "reviews" && <Reviews api={api} />}
      {page === "media" && <Media api={api} />}
      {page === "species" && <SpeciesResources api={api} />}
      {page === "models" && <Models api={api} />}
      {page === "reports" && <Reports api={api} />}
      {page === "system" && <SystemPage api={api} />}
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
  const state = useLoad(() => api<Record<string, number | boolean>>("/api/v1/admin/analytics/overview"), {});
  const cards = [["素材数量", state.data.media_count ?? 0], ["动物检出数量", state.data.detection_count ?? 0], ["重点物种上报", state.data.priority_species_count ?? 0], ["待复核记录", state.data.pending_review_count ?? 0]];
  return <PageState state={state}><section className="metrics">{cards.map(([label, value]) => <article key={String(label)}><Activity size={20} /><span>{label}</span><strong>{String(value)}</strong></article>)}</section><section className="grid two"><Panel title="监测数据分布"><TrendChart values={cards.map((item) => Number(item[1]))} labels={cards.map((item) => String(item[0]))}/></Panel><Panel title="处理闭环"><div className="pipeline"><b>素材导入</b><i>→</i><b>异步识别</b><i>→</i><b>规则入队</b><i>→</i><b>专家复核</b></div><Status ok text="动物识别管线已接入"/><Status ok={Boolean(state.data.plant_recognition_enabled)} text={state.data.plant_recognition_enabled ? "植物识别已启用" : "植物识别接口已预留"}/></Panel></section></PageState>;
}

function Batch({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) {
  const [files, setFiles] = React.useState<FileList | null>(null); const [site, setSite] = React.useState(""); const [camera, setCamera] = React.useState(""); const [message, setMessage] = React.useState(""); const [busy, setBusy] = React.useState(false);
  async function submit() { if (!files?.length) return; setBusy(true); setMessage(""); const body = new FormData(); Array.from(files).forEach((file) => body.append("files", file)); if (site) body.append("site_id", site); if (camera) body.append("camera_code", camera); try { const jobs = await api<Job[]>("/api/v1/uploads/batch", { method: "POST", body }); setMessage(`已创建 ${jobs.length} 个异步分析任务`); } catch (reason) { setMessage((reason as Error).message); } finally { setBusy(false); } }
  return <Panel title="红外相机素材批量导入"><div className="upload-zone"><FileArchive size={42}/><h2>选择图片、视频或 ZIP 压缩包</h2><p>服务端将执行安全解压、抽帧、空场景过滤、候选识别和复核入队。</p><input type="file" multiple accept="image/*,video/*,.zip" onChange={(event) => setFiles(event.target.files)} /></div><div className="form-row"><label>监测点<input value={site} onChange={(e) => setSite(e.target.value)} placeholder="可选"/></label><label>相机编号<input value={camera} onChange={(e) => setCamera(e.target.value)} placeholder="可选"/></label><button onClick={submit} disabled={busy || !files?.length}>{busy ? "正在提交…" : "创建批量任务"}</button></div>{message && <div className="notice">{message}</div>}</Panel>;
}

function Reviews({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) {
  const state = useLoad(() => api<Review[]>("/api/v1/admin/reviews"), []);
  async function act(task: Review, action: "claim" | "decision", decision?: string) { await api(`/api/v1/admin/reviews/${task.id}/${action}`, { method: "POST", headers: action === "decision" ? { "Content-Type": "application/json" } : undefined, body: action === "decision" ? JSON.stringify({ version: task.version, decision, comment: "管理端复核", promote_to_sample: decision !== "rejected" }) : undefined }); state.reload(); }
  return <PageState state={state}><Panel title="自动入队复核记录"><DataTable headers={["入队原因", "状态", "关联记录", "版本", "操作"]}>{state.data.map((task) => <tr key={task.id}><td>{task.reason}</td><td><Badge value={task.status}/></td><td>{task.report_id ?? task.analysis_job_id ?? "-"}</td><td>v{task.version}</td><td className="actions">{task.status === "pending" && <button onClick={() => act(task, "claim")}>领取</button>}{task.status === "claimed" && <><button onClick={() => act(task, "decision", "confirmed")}>确认</button><button onClick={() => act(task, "decision", "corrected")}>修正</button><button className="danger" onClick={() => act(task, "decision", "rejected")}>驳回</button></>}</td></tr>)}</DataTable></Panel></PageState>;
}

function Media({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) {
  const state = useLoad(() => api<Job[]>("/api/v1/admin/media"), []);
  async function download() { const blob = await api<Blob>("/api/v1/admin/media/export.csv", { headers: { Accept: "text/csv" } }); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "monitoring-data.csv"; link.click(); URL.revokeObjectURL(url); }
  return <PageState state={state}><Panel title="统一监测素材"><div className="toolbar"><span>共 {state.data.length} 条</span><button onClick={download}><Download size={15}/>导出 CSV</button></div><DataTable headers={["文件", "来源", "类型", "状态", "进度", "创建时间"]}>{state.data.map((job) => <tr key={job.id}><td>{job.file_name}</td><td>{job.source}</td><td>{job.media_type}</td><td><Badge value={job.status}/></td><td><Progress percent={job.progress} size="small" status={job.status === "failed" ? "exception" : undefined}/></td><td>{formatTime(job.created_at)}</td></tr>)}</DataTable></Panel></PageState>;
}

function SpeciesResources({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) {
  const state = useLoad(() => api<{ species: Species[] }>("/api/v1/species"), { species: [] });
  return <PageState state={state}><Panel title="动植物知识库与图鉴"><div className="toolbar"><span>共 {state.data.species.length} 个物种</span><small>统一维护分类、科属、生境、保护等级和资料来源。</small></div><DataTable headers={["中文名", "学名", "类别", "科", "保护等级"]}>{state.data.species.slice(0, 200).map((item) => <tr key={item.species_id}><td>{item.cn_name}</td><td><i>{item.latin_name || "-"}</i></td><td>{item.category}</td><td>{item.family || "-"}</td><td>{item.protection_level}</td></tr>)}</DataTable></Panel></PageState>;
}

function Models({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) {
  const models = useLoad(() => api<Model[]>("/api/v1/admin/models"), []); const samples = useLoad(() => api<Array<Record<string, string>>>("/api/v1/admin/samples"), []);
  async function activate(id: string) { await api(`/api/v1/admin/models/${id}/activate`, { method: "POST" }); models.reload(); }
  return <><section className="metrics"><article><PackageOpen/><span>模型版本</span><strong>{models.data.length}</strong></article><article><FileSearch/><span>候选样本</span><strong>{samples.data.length}</strong></article></section><Panel title="模型版本与发布"><DataTable headers={["管线", "版本", "类群", "阈值", "状态", "操作"]}>{models.data.map((model) => <tr key={model.id}><td>{model.pipeline}</td><td>{model.version}</td><td>{model.taxon_group}</td><td>{model.threshold}</td><td><Badge value={model.is_active ? "active" : "inactive"}/></td><td>{!model.is_active && <button onClick={() => activate(model.id)}>发布</button>}</td></tr>)}</DataTable></Panel></>;
}

function Reports({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) { async function download() { const blob = await api<Blob>("/api/v1/admin/media/export.csv", { headers: { Accept: "text/csv" } }); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "report-source.csv"; link.click(); URL.revokeObjectURL(url); } return <section className="grid three">{["巡护报告", "物种发现记录", "年度监测报告"].map((title) => <Panel title={title} key={title}><BarChart3 size={34}/><p>基于已确认的监测与复核数据生成，避免未确认候选进入正式统计。</p><button onClick={download}>导出统计数据</button></Panel>)}</section>; }

function SystemPage({ api }: { api: <T>(path: string, init?: RequestInit) => Promise<T> }) {
  const users = useLoad(() => api<User[]>("/api/v1/admin/users"), []); const [backup, setBackup] = React.useState("");
  return <section className="grid two"><Panel title="账号与角色"><DataTable headers={["账号", "姓名", "角色", "状态"]}>{users.data.map((item) => <tr key={item.id}><td>{item.username}</td><td>{item.display_name}</td><td>{item.roles.join("、")}</td><td><Badge value={item.is_active ? "active" : "disabled"}/></td></tr>)}</DataTable></Panel><Panel title="系统维护"><Status ok text="接口权限由后端 RBAC 强制执行"/><Status ok text="关键操作写入审计日志"/><button onClick={() => api<{ id: string }>("/api/v1/admin/backups", { method: "POST" }).then((data) => setBackup(data.id))}>创建备份清单</button>{backup && <div className="notice">已创建：{backup}</div>}</Panel></section>;
}

function Panel({ title, children }: React.PropsWithChildren<{ title: string }>) { return <section className="panel"><div className="panel-title"><h2>{title}</h2></div>{children}</section>; }
function TrendChart({ labels, values }: { labels: string[]; values: number[] }) { const ref = React.useRef<HTMLDivElement>(null); React.useEffect(() => { if (!ref.current) return; const chart = initChart(ref.current); chart.setOption({ grid: { left: 48, right: 18, top: 20, bottom: 42 }, tooltip: {}, xAxis: { type: "category", data: labels, axisLabel: { interval: 0 } }, yAxis: { type: "value", minInterval: 1 }, series: [{ type: "bar", data: values, itemStyle: { color: "#16805d", borderRadius: [6, 6, 0, 0] } }] }); const resize = () => chart.resize(); window.addEventListener("resize", resize); return () => { window.removeEventListener("resize", resize); chart.dispose(); }; }, [labels.join("|"), values.join("|")]); return <div className="trend-chart" ref={ref}/>; }
function DataTable({ headers, children }: React.PropsWithChildren<{ headers: string[] }>) { return <div className="table-wrap"><table><thead><tr>{headers.map((item) => <th key={item}>{item}</th>)}</tr></thead><tbody>{children}</tbody></table></div>; }
function Badge({ value }: { value: string }) { return <span className={`badge ${value}`}>{value}</span>; }
function Status({ ok, text }: { ok: boolean; text: string }) { return <div className="status">{ok ? <CheckCircle2 color="#16805d"/> : <XCircle color="#b7791f"/>}<span>{text}</span></div>; }
function PageState({ state, children }: React.PropsWithChildren<{ state: { loading: boolean; error: string; reload: () => void } }>) { if (state.loading) return <div className="center"><RefreshCw className="spin"/>加载中…</div>; if (state.error) return <div className="error">{state.error}<button onClick={state.reload}>重试</button></div>; return <>{children}</>; }
function formatTime(value: string) { return new Date(value).toLocaleString("zh-CN", { hour12: false }); }

createRoot(document.getElementById("root")!).render(<React.StrictMode><ConfigProvider theme={{ token: { colorPrimary: "#16805d", borderRadius: 8 } }}><App/></ConfigProvider></React.StrictMode>);
