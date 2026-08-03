import React from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowRight,
  BookOpen,
  Bot,
  Camera,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Database,
  FileVideo,
  History,
  ImageUp,
  Leaf,
  Loader2,
  LogOut,
  PawPrint,
  Settings2,
  ShieldCheck,
  Send,
  Sparkles,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import "./styles.css";

type Page = "overview" | "animal" | "resources" | "report" | "animalKnowledge" | "plantKnowledge" | "gallery" | "assistant" | "records" | "system";

type AnalysisJob = { id: string; status: string; progress: number; result_json?: AnalysisResponse | null; error_message?: string | null };
type FieldReport = { id: string; species_name: string; status: string; final_species_name?: string | null; review_comment?: string | null; created_at: string };

type BoundingBox = { x: number; y: number; width: number; height: number };

type SpeciesCandidateResult = {
  label: string;
  confidence: number;
  source: string;
  evidence?: string | null;
  sample_url?: string | null;
  species_id?: string | null;
  latin_name?: string | null;
  taxon_group?: string | null;
  protection_level?: string | null;
  region_status?: string;
  priority?: string;
  review_flags?: string[];
};

type Detection = {
  media_id: string;
  frame_time: number;
  bbox: BoundingBox;
  detected_type: string;
  species_label: string;
  confidence: number;
  detection_confidence?: number;
  classification_confidence?: number;
  top_candidates?: SpeciesCandidateResult[];
  review_status?: "ready" | "needs_review" | "low_confidence" | string;
  review_reasons?: string[];
  preview_crop_path: string;
  retrieval_confidence?: number;
};

type AnalysisResponse = {
  media_id: string;
  media_type: string;
  preview_url: string | null;
  detections: Detection[];
  species_summary: Record<string, number>;
  model_status: Record<string, string>;
  message: string;
};

type KnowledgeEntry = {
  speciesId?: string;
  title: string;
  latin: string;
  category?: string;
  taxonGroup?: string | null;
  order?: string | null;
  family?: string | null;
  genus?: string | null;
  recognitionTier?: string;
  tags: string[];
  habitat: string;
  habits?: string;
  diet?: string;
  features: string[];
  note: string;
  protectionLevel?: string;
  similarSpecies?: string[];
  reviewTips?: string;
  monitoringValue?: string;
  lifeForm?: string;
  phenology?: string;
  distribution?: string;
  sourceUrls?: string[];
  imageUrl?: string | null;
  imageSourceUrl?: string | null;
  imageAuthor?: string;
  imageLicense?: string;
  imageBasisOfRecord?: string;
};

type SpeciesEntry = {
  species_id: string;
  cn_name: string;
  latin_name: string | null;
  category: string;
  taxon_group?: string | null;
  order?: string | null;
  family?: string | null;
  genus?: string | null;
  protection_level: string;
  recognition_tier: string;
  habits?: string;
  diet?: string;
  features: string[];
  habitat: string;
  monitoring_value: string;
  similar_species: string[];
  review_tips: string;
  tags: string[];
  life_form?: string;
  phenology?: string;
  distribution?: string;
  source_urls?: string[];
  image_url?: string | null;
  image_source_url?: string | null;
  image_author?: string;
  image_license?: string;
  image_basis_of_record?: string;
};

type ReferenceSample = {
  file_name: string;
  file_url: string;
  source?: string | null;
  author?: string | null;
  license?: string | null;
  sex?: string | null;
  cn_name?: string | null;
  scientific_name?: string | null;
  category?: string | null;
  taxon_group?: string | null;
  protection_level?: string | null;
  source_pdf?: string | null;
  source_page?: number | null;
  match_status?: string | null;
  subspecies?: string | null;
  note?: string | null;
};

type ReferenceSpecies = {
  folder_name: string;
  image_count: number;
  metadata_rows: number;
  cover_url?: string | null;
  sample_urls: string[];
  samples: ReferenceSample[];
};

type AssistantSource = {
  species_id: string;
  cn_name: string;
  latin_name?: string | null;
  protection_level: string;
  matched_fields: string[];
};

type AssistantChatResponse = {
  answer: string;
  mode: string;
  review_notice: string;
  sources: AssistantSource[];
  suggested_questions: string[];
};

type AssistantTurn = {
  question: string;
  response: AssistantChatResponse;
};

type HealthResponse = {
  status: string;
  models: Record<string, string>;
  assistant?: Record<string, string>;
};

const configuredApiBase = import.meta.env.VITE_API_BASE as string | undefined;
// 开发环境始终走 Vite 同源代理，避免手机把 127.0.0.1 解析成自身。
const API_BASE = import.meta.env.DEV ? "" : (configuredApiBase?.replace(/\/$/, "") ?? "");
const MIN_KNOWLEDGE_MATCH_CONFIDENCE = 0.7;
const CANDIDATE_DISPLAY_THRESHOLD = 0.45;
const WILDLIFE_CATEGORIES = new Set(["animal", "bird", "reptile_amphibian", "monitoring_object"]);
const DIRECT_RECOGNITION_TIERS = new Set(["knowledge_first", "high_demo"]);

async function copyTextToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Some embedded browsers expose clipboard but block it on non-HTTPS pages.
    }
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  textarea.setSelectionRange(0, text.length);

  try {
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    document.body.removeChild(textarea);
  }
}

const SPECIES_ALIASES: Record<string, string[]> = {
  macaque: ["macaque", "rhesus macaque", "macaca", "macaca mulatta", "猕猴"],
  leopard_cat: ["leopard cat", "leopard-cat", "prionailurus bengalensis", "prionailurus", "豹猫"],
  red_fox: ["red fox", "vulpes vulpes", "vulpes", "赤狐"],
  wild_boar: ["wild boar", "boar", "wild pig", "sus scrofa", "sus", "野猪"],
  sika_deer: ["sika deer", "cervus nippon", "sika", "梅花鹿"],
  sambar_deer: ["sambar", "sambar deer", "cervus equinus", "rusa unicolor", "水鹿"],
  chinese_goral: ["goral", "chinese goral", "naemorhedus griseus", "naemorhedus", "中华斑羚", "斑羚"],
  asiatic_black_bear: ["asiatic black bear", "asian black bear", "black bear", "ursus thibetanus", "黑熊", "亚洲黑熊"],
  yellow_throated_marten: ["yellow-throated marten", "yellow throated marten", "martes flavigula", "marten", "黄喉貂"],
  large_indian_civet: ["large indian civet", "large civet", "viverra zibetha", "viverra", "civet", "大灵猫"],
  white_headed_langur: ["white-headed langur", "white headed langur", "trachypithecus leucocephalus", "langur", "白头叶猴"],
  chinese_pangolin: ["chinese pangolin", "pangolin", "manis pentadactyla", "manis", "中华穿山甲", "穿山甲"],
};

const NAV_ITEMS: Array<{ page: Page; label: string; icon: React.ReactNode }> = [
  { page: "animal", label: "智能识别", icon: <PawPrint size={18} /> },
  { page: "resources", label: "物种资源中心", icon: <BookOpen size={18} /> },
  { page: "report", label: "重点物种上报", icon: <ShieldCheck size={18} /> },
  { page: "assistant", label: "生态助手", icon: <Bot size={18} /> },
  { page: "records", label: "我的记录", icon: <History size={18} /> },
];

const ANIMAL_KNOWLEDGE: Record<string, KnowledgeEntry> = {
  梅花鹿: {
    title: "梅花鹿",
    latin: "Cervus nippon",
    tags: ["哺乳动物", "鹿科", "林缘活动"],
    habitat: "林地、草坡、林缘和开阔灌丛区域。",
    features: ["体表白色斑点明显", "四肢细长", "警觉性强"],
    note: "当前结果仍建议结合模型版本、原始画面和人工复核，避免把候选分类当成最终结论。",
  },
  野猪: {
    title: "野猪",
    latin: "Sus scrofa",
    tags: ["哺乳动物", "偶蹄目", "夜间活动"],
    habitat: "森林、灌丛、农田边缘和山地沟谷。",
    features: ["体型粗壮", "吻部突出", "背部轮廓较高"],
    note: "野猪主体轮廓通常较清晰，但真实部署仍需要结合区域物种库和人工复核。",
  },
  黑熊: {
    title: "黑熊",
    latin: "Ursus thibetanus",
    tags: ["哺乳动物", "大型兽类", "保护预警"],
    habitat: "山地森林、阔叶林、针阔混交林和低干扰区域。",
    features: ["体型大", "毛色黑", "胸部常有浅色月牙斑"],
    note: "黑熊类结果建议结合连续帧和胸斑特征复核，当前更适合做保护预警展示。",
  },
  豹猫: {
    title: "豹猫",
    latin: "Prionailurus bengalensis",
    tags: ["哺乳动物", "猫科", "夜行性"],
    habitat: "森林、灌丛、农田边缘和溪谷附近。",
    features: ["体表斑纹明显", "尾部较长", "夜间活动较多"],
    note: "豹猫在单帧里容易与家猫混淆，适合展示候选识别与复核口径。",
  },
  大灵猫: {
    title: "大灵猫",
    latin: "Viverra zibetha",
    tags: ["哺乳动物", "灵猫科", "一级保护"],
    habitat: "森林、灌丛、溪谷和农田边缘。",
    features: ["体型中等", "体表具斑纹或条纹", "尾具环纹"],
    note: "大灵猫是广西特色重点物种，适合作为知识库优先展示对象。",
  },
  中华穿山甲: {
    title: "中华穿山甲",
    latin: "Manis pentadactyla",
    tags: ["哺乳动物", "鳞甲目", "国家一级"],
    habitat: "森林、灌丛、丘陵和土质适合挖洞的区域。",
    features: ["体表覆鳞片", "吻部细长", "四肢具强爪"],
    note: "样本稀缺但保护价值高，适合展示知识库和人工复核流程。",
  },
  赤狐: {
    title: "赤狐",
    latin: "Vulpes vulpes",
    tags: ["哺乳动物", "犬科", "候选分类"],
    habitat: "林缘、草地、荒坡和农田周边。",
    features: ["吻部较尖", "尾部蓬松", "行动灵活"],
    note: "赤狐类结果建议作为候选展示，并结合本地物种清单细分到具体种。",
  },
  狼: {
    title: "狼",
    latin: "Canis lupus",
    tags: ["哺乳动物", "犬科", "需复核"],
    habitat: "山地、森林、草原和人类干扰较少区域。",
    features: ["体型较大", "吻部较长", "耳部直立"],
    note: "狼与犬、狐狸等容易在单帧中混淆，建议显示为候选并保留复核口径。",
  },
  Tapirus: {
    title: "貘属",
    latin: "Tapirus",
    tags: ["哺乳动物", "夜行性", "林地湿润环境"],
    habitat: "热带森林、河岸和湿地边缘。",
    features: ["体型粗壮", "鼻吻部灵活", "常在夜间活动"],
    note: "当前分类器可能输出属级结果，更适合当作候选类别展示。",
  },
  Mazama: {
    title: "短角鹿属",
    latin: "Mazama",
    tags: ["哺乳动物", "鹿科", "林下活动"],
    habitat: "热带和亚热带森林下层，常在隐蔽区域活动。",
    features: ["体型较小", "四肢细长", "常单独出现"],
    note: "属级结果不能等同于具体物种，需要结合区域物种库判断。",
  },
  Canis: {
    title: "犬属",
    latin: "Canis",
    tags: ["哺乳动物", "食肉目", "候选分类"],
    habitat: "森林、草地、农田边缘等多种环境。",
    features: ["吻部较长", "耳形明显", "行动敏捷"],
    note: "犬属包含多种动物，建议把它作为候选属类处理。",
  },
  Unknown: {
    title: "未知动物",
    latin: "Unknown",
    tags: ["低置信度", "类外动物", "待人工复核"],
    habitat: "需要结合地点、时间、连续帧和原图综合判断。",
    features: ["模型置信度不足", "可能不在当前分类范围内"],
    note: "这是系统的安全出口，避免把不确定结果说成确定物种。",
  },
};

const ROADMAP_STEPS = [
  { phase: "阶段一", title: "识别闭环", points: ["动物检测", "候选分类", "结果回放", "本地保存"] },
  { phase: "阶段二", title: "知识库补强", points: ["植物知识库", "物种特征卡", "栖息地字段", "保护等级"] },
  { phase: "阶段三", title: "人工复核", points: ["待确认状态", "样本沉淀", "修正记录", "结果追踪"] },
  { phase: "阶段四", title: "模型升级", points: ["区域物种库", "自训练模型", "同一目标去重", "批量回放分析"] },
];

function App() {
  const [isAuthenticated, setIsAuthenticated] = React.useState(false);
  const [account, setAccount] = React.useState("");
  const [authToken, setAuthToken] = React.useState("");
  const [authReady, setAuthReady] = React.useState(false);
  const [activeJobId, setActiveJobId] = React.useState<string | null>(null);
  const [page, setPage] = React.useState<Page>(() =>
    window.matchMedia("(max-width: 860px)").matches ? "overview" : "animal",
  );
  const [file, setFile] = React.useState<File | null>(null);
  const [localPreview, setLocalPreview] = React.useState<string | null>(null);
  const [confidence, setConfidence] = React.useState(0.35);
  const [frameInterval, setFrameInterval] = React.useState(1);
  const [includeLowConfidence, setIncludeLowConfidence] = React.useState(false);
  const [result, setResult] = React.useState<AnalysisResponse | null>(null);
  const [history, setHistory] = React.useState<AnalysisResponse[]>([]);
  const [speciesKnowledge, setSpeciesKnowledge] = React.useState<SpeciesEntry[]>([]);
  const [speciesCatalog, setSpeciesCatalog] = React.useState<SpeciesEntry[]>([]);
  const [referenceSpecies, setReferenceSpecies] = React.useState<ReferenceSpecies[]>([]);
  const [pdfWeakReferenceSpecies, setPdfWeakReferenceSpecies] = React.useState<ReferenceSpecies[]>([]);
  const [openSetReferenceSpecies, setOpenSetReferenceSpecies] = React.useState<ReferenceSpecies[]>([]);
  const [health, setHealth] = React.useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const lastAutoAnalyzeKey = React.useRef("");

  React.useEffect(() => {
    fetch(`${API_BASE}/api/v1/auth/refresh`, { method: "POST", credentials: "include" })
      .then(async (response) => response.ok ? response.json() : null)
      .then((payload) => {
        if (!payload) return;
        setAuthToken(payload.access_token);
        setAccount(payload.user.display_name);
        setIsAuthenticated(true);
      })
      .finally(() => setAuthReady(true));
  }, []);

  React.useEffect(() => {
    if (!isAuthenticated) return;
    fetch(`${API_BASE}/api/health`)
      .then((response) => (response.ok ? response.json() : null))
      .then(setHealth)
      .catch(() => setHealth(null));
    fetch(`${API_BASE}/api/v1/analysis-jobs`, { headers: { Authorization: `Bearer ${authToken}` } })
      .then((response) => (response.ok ? response.json() : []))
      .then((jobs: AnalysisJob[]) => setHistory(jobs.flatMap((job) => job.result_json ? [job.result_json] : [])))
      .catch(() => setHistory([]));
    fetch(`${API_BASE}/api/species`)
      .then((response) => (response.ok ? response.json() : []))
      .then(setSpeciesKnowledge)
      .catch(() => setSpeciesKnowledge([]));
    fetch(`${API_BASE}/api/species-catalog`)
      .then((response) => (response.ok ? response.json() : { species: [] }))
      .then((payload: { species?: SpeciesEntry[] }) => setSpeciesCatalog(payload.species ?? []))
      .catch(() => setSpeciesCatalog([]));
    fetch(`${API_BASE}/api/reference-samples`)
      .then((response) => (response.ok ? response.json() : { species: [] }))
      .then((payload: { species?: ReferenceSpecies[] }) => setReferenceSpecies(payload.species ?? []))
      .catch(() => setReferenceSpecies([]));
    fetch(`${API_BASE}/api/pdf-weak-reference-samples`)
      .then((response) => (response.ok ? response.json() : { species: [] }))
      .then((payload: { species?: ReferenceSpecies[] }) => setPdfWeakReferenceSpecies(payload.species ?? []))
      .catch(() => setPdfWeakReferenceSpecies([]));
    fetch(`${API_BASE}/api/knowledge-open-set-samples`)
      .then((response) => (response.ok ? response.json() : { species: [] }))
      .then((payload: { species?: ReferenceSpecies[] }) => setOpenSetReferenceSpecies(payload.species ?? []))
      .catch(() => setOpenSetReferenceSpecies([]));
  }, [isAuthenticated, authToken]);

  function selectFile(nextFile: File | null) {
    setFile(nextFile);
    setResult(null);
    setError(null);
    if (localPreview) URL.revokeObjectURL(localPreview);
    setLocalPreview(nextFile ? URL.createObjectURL(nextFile) : null);
  }

  async function analyze(overrideFile?: File) {
    const currentFile = overrideFile ?? file;
    if (!currentFile) return;
    setIsLoading(true);
    setError(null);

    const form = new FormData();
    form.append("file", currentFile);
    form.append("confidence_threshold", String(confidence));
    form.append("frame_interval_seconds", String(frameInterval));
    form.append("include_low_confidence", String(includeLowConfidence));

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 120000);

    try {
      const response = await fetch(`${API_BASE}/api/v1/analysis-jobs`, { method: "POST", body: form, signal: controller.signal, headers: { Authorization: `Bearer ${authToken}` } });
      if (!response.ok) throw new Error(await response.text());
      let job = (await response.json()) as AnalysisJob;
      setActiveJobId(job.id);
      while (["queued", "running"].includes(job.status)) {
        await new Promise((resolve) => window.setTimeout(resolve, 900));
        const poll = await fetch(`${API_BASE}/api/v1/analysis-jobs/${job.id}`, { headers: { Authorization: `Bearer ${authToken}` } });
        if (!poll.ok) throw new Error("读取识别进度失败");
        job = await poll.json();
      }
      if (job.status !== "succeeded" || !job.result_json) throw new Error(job.error_message || "分析失败");
      const payload = job.result_json;
      setResult(payload);
      setHistory((items) => [payload, ...items.filter((item) => item.media_id !== payload.media_id)].slice(0, 25));
      setPage("animal");
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") {
        setError("分析超时，请稍后再试");
      } else {
        setError(reason instanceof Error ? reason.message : "分析失败");
      }
    } finally {
      window.clearTimeout(timeout);
      setIsLoading(false);
    }
  }

  React.useEffect(() => {
    if (!file) {
      lastAutoAnalyzeKey.current = "";
      return;
    }
    const key = `${file.name}:${file.size}:${file.lastModified}`;
    if (lastAutoAnalyzeKey.current === key) return;
    lastAutoAnalyzeKey.current = key;
    void analyze(file);
  }, [file]);

  const previewSource = result?.preview_url ? `${API_BASE}${result.preview_url}` : localPreview;
  const catalogSpecies = speciesCatalog.length ? speciesCatalog : speciesKnowledge;
  const activeKnowledge = getKnowledge(result, catalogSpecies);
  const activeReference = getReferenceSpecies(result, [...referenceSpecies, ...pdfWeakReferenceSpecies, ...openSetReferenceSpecies], catalogSpecies);
  const modelStatus = result?.model_status ?? health?.models;

  async function login(username: string, password: string) {
    const response = await fetch(`${API_BASE}/api/v1/auth/login`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
    if (!response.ok) throw new Error((await response.json()).detail || "登录失败");
    const payload = await response.json();
    setAuthToken(payload.access_token);
    setAccount(payload.user.display_name);
    setIsAuthenticated(true);
    setPage(window.matchMedia("(max-width: 860px)").matches ? "overview" : "animal");
  }

  async function logout() {
    await fetch(`${API_BASE}/api/v1/auth/logout`, { method: "POST", credentials: "include" });
    setAccount("");
    setAuthToken("");
    setIsAuthenticated(false);
    setPage("animal");
  }

  if (!authReady) return <main className="login-shell"><Loader2 className="spin" size={30} /></main>;
  if (!isAuthenticated) {
    return <LoginPage onLogin={login} />;
  }

  return (
    <main className="app-shell">
      <aside className="nav">
        <div className="brand">
          <Camera size={24} />
          <div>
            <h1>森智眼</h1>
            <span>识别、知识与记录</span>
          </div>
        </div>
        <nav>
          {NAV_ITEMS.map((item) => (
            <button key={item.page} className={page === item.page ? "active" : ""} onClick={() => setPage(item.page)}>
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <button className="nav-logout" type="button" onClick={logout}>
          <LogOut size={18} />
          <span>{account ? `退出登录 · ${account}` : "退出登录"}</span>
        </button>
      </aside>

      <MobileHeader account={account} onHome={() => setPage("overview")} onLogout={logout} />

      <section className={`page page-${page}`}>
        {page === "overview" ? (
          <OverviewPage
            history={history}
            result={result}
            setPage={setPage}
            speciesCount={catalogSpecies.length}
            referenceCount={referenceSpecies.length + pdfWeakReferenceSpecies.length + openSetReferenceSpecies.length}
            modelStatus={modelStatus}
          />
        ) : null}
        {page === "animal" ? (
          <AnimalPage
            file={file}
            previewSource={previewSource}
            result={result}
            isLoading={isLoading}
            error={error}
            confidence={confidence}
            frameInterval={frameInterval}
            includeLowConfidence={includeLowConfidence}
            activeKnowledge={activeKnowledge}
            speciesKnowledge={catalogSpecies}
            activeReference={activeReference}
            pdfWeakReferenceSpecies={pdfWeakReferenceSpecies}
            openSetReferenceSpecies={openSetReferenceSpecies}
            health={health}
            onFile={selectFile}
            onAnalyze={analyze}
            onClear={() => selectFile(null)}
            setConfidence={setConfidence}
            setFrameInterval={setFrameInterval}
            setIncludeLowConfidence={setIncludeLowConfidence}
          />
        ) : null}
        {page === "resources" ? <ResourceCenterPage animalSpecies={catalogSpecies} pdfWeakReferenceSpecies={pdfWeakReferenceSpecies} openSetReferenceSpecies={openSetReferenceSpecies} /> : null}
        {page === "report" ? <FieldReportPage token={authToken} activeJobId={activeJobId} result={result} /> : null}
        {page === "animalKnowledge" ? <KnowledgeLibraryPage view="animals" animalSpecies={catalogSpecies} pdfWeakReferenceSpecies={pdfWeakReferenceSpecies} openSetReferenceSpecies={openSetReferenceSpecies} /> : null}
        {page === "plantKnowledge" ? <KnowledgeLibraryPage view="plants" animalSpecies={catalogSpecies} pdfWeakReferenceSpecies={pdfWeakReferenceSpecies} openSetReferenceSpecies={openSetReferenceSpecies} /> : null}
        {page === "gallery" ? <KnowledgeLibraryPage view="gallery" animalSpecies={catalogSpecies} pdfWeakReferenceSpecies={pdfWeakReferenceSpecies} openSetReferenceSpecies={openSetReferenceSpecies} /> : null}
        {page === "assistant" ? <EcologyAssistantPage speciesKnowledge={catalogSpecies} result={result} /> : null}
        {page === "records" ? (
          <RecordsPage
            history={history}
            speciesKnowledge={catalogSpecies}
            pdfWeakReferenceSpecies={pdfWeakReferenceSpecies}
            openSetReferenceSpecies={openSetReferenceSpecies}
            modelStatus={modelStatus}
            onOpen={(item) => { setResult(item); setPage("animal"); }}
          />
        ) : null}
      </section>
      <MobileNavigation page={page} onChange={setPage} />
    </main>
  );
}

function MobileHeader({ account, onHome, onLogout }: { account: string; onHome: () => void; onLogout: () => void }) {
  return (
    <header className="mobile-header">
      <button className="mobile-brand" type="button" onClick={onHome} aria-label="返回首页">
        <span className="mobile-brand-mark"><Leaf size={18} /></span>
        <span>
          <strong>森智眼</strong>
          <small>移动生态知识平台</small>
        </span>
      </button>
      <button className="mobile-logout" type="button" onClick={onLogout} aria-label={account ? `退出账号 ${account}` : "退出登录"}>
        <LogOut size={18} />
      </button>
    </header>
  );
}

function MobileNavigation({ page, onChange }: { page: Page; onChange: (page: Page) => void }) {
  const items: Array<{ page: Page; label: string; icon: React.ReactNode }> = [
    { page: "animal", label: "识别", icon: <Camera size={20} /> },
    { page: "resources", label: "资源", icon: <BookOpen size={20} /> },
    { page: "report", label: "上报", icon: <ShieldCheck size={20} /> },
    { page: "assistant", label: "助手", icon: <Bot size={20} /> },
    { page: "records", label: "记录", icon: <History size={20} /> },
  ];

  function changePage(nextPage: Page) {
    onChange(nextPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <nav className="mobile-navigation" aria-label="移动端主导航">
      {items.map((item) => (
        <button
          key={item.page}
          type="button"
          className={page === item.page ? "active" : ""}
          aria-current={page === item.page ? "page" : undefined}
          onClick={() => changePage(item.page)}
        >
          {item.icon}
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  );
}

function LoginPage({ onLogin }: { onLogin: (username: string, password: string) => Promise<void> }) {
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [loginError, setLoginError] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoginError(""); setSubmitting(true);
    try { await onLogin(username, password); }
    catch (reason) { setLoginError(reason instanceof Error ? reason.message : "登录失败"); }
    finally { setSubmitting(false); }
  }
  return (
    <main className="login-shell">
      <section className="login-hero">
        <div className="login-art">
          <div className="login-image-board">
            <img className="login-main-photo" src="/login/white-headed-langur.png" alt="白头叶猴" />
          </div>
          <div className="login-title-block">
            <h1>森智眼</h1>
            <p>识别 · 知识库 · 上报 · 记录</p>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <form className="login-panel-inner" onSubmit={submit}>
          <span className="eyebrow">欢迎来到森智眼</span>
          <h2>巡护人员实名登录</h2>
          <p>识别、重点物种上报和专家复核结果均关联到当前账号。</p>
          <label className="login-field"><span>账号</span><input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required /></label>
          <label className="login-field"><span>密码</span><input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" required /></label>
          {loginError ? <div className="error-banner">{loginError}</div> : null}
          <button className="login-submit login-enter" type="submit" disabled={submitting}>
            <ArrowRight size={18} />
            <span>{submitting ? "正在登录…" : "进入系统"}</span>
          </button>
        </form>
      </section>
    </main>
  );
}

function OverviewPage({
  history,
  result,
  setPage,
  speciesCount,
  referenceCount,
  modelStatus,
}: {
  history: AnalysisResponse[];
  result: AnalysisResponse | null;
  setPage: (page: Page) => void;
  speciesCount: number;
  referenceCount: number;
  modelStatus?: Record<string, string>;
}) {
  return (
    <>
      <PageHeader
        eyebrow="平台总览"
        title="森智眼"
        subtitle="面向监测、巡护和科普场景，提供素材识别、物种知识和历史记录管理。"
      />
      <section className="metric-grid">
        <MetricCard label="分析记录" value={String(history.length)} hint="本地保存的识别结果" />
        <MetricCard label="当前目标" value={String(result?.detections.length ?? 0)} hint="最近一次分析中的目标数" />
        <MetricCard label="物种目录" value={String(speciesCount)} hint="统一动植物知识库条目" />
        <MetricCard label="图鉴参考" value={String(referenceCount)} hint="口袋书与开放集参考图" />
        <MetricCard label="检测引擎" value={modelStatusLabel(modelStatus?.detector)} hint="上传素材时用于定位动物目标" />
        <MetricCard label="物种分类" value={modelStatusLabel(modelStatus?.classifier)} hint="识别结果与知识库联动" />
      </section>
      <section className="overview-grid">
        <ModuleCard icon={<PawPrint size={24} />} title="智能识别" text="上传图片或视频，查看目标框、可展示候选和置信度。" action="进入识别" onClick={() => setPage("animal")} />
        <ModuleCard icon={<BookOpen size={24} />} title="物种资源中心" text="统一检索动物、植物、保护等级、分类信息和参考图鉴。" action="查看资源" onClick={() => setPage("resources")} />
        <ModuleCard icon={<ShieldCheck size={24} />} title="重点物种上报" text="提交图片、时间、地点和现场备注，等待专家确认。" action="立即上报" onClick={() => setPage("report")} />
        <ModuleCard icon={<Bot size={24} />} title="生态助手" text="围绕当前候选物种回答识别、习性和复核问题。" action="打开助手" onClick={() => setPage("assistant")} />
        <ModuleCard icon={<History size={24} />} title="分析记录" text="集中查看最近的结果，便于回看任务、复制摘要和追踪复核状态。" action="查看记录" onClick={() => setPage("records")} />
        <ModuleCard icon={<ShieldCheck size={24} />} title="系统说明" text="查看统一的识别链路、复核口径和维护路线。" action="查看说明" onClick={() => setPage("system")} />
      </section>
    </>
  );
}

function AnimalPage(props: {
  file: File | null;
  previewSource: string | null;
  result: AnalysisResponse | null;
  isLoading: boolean;
  error: string | null;
  confidence: number;
  frameInterval: number;
  includeLowConfidence: boolean;
  activeKnowledge: KnowledgeEntry;
  speciesKnowledge: SpeciesEntry[];
  activeReference: ReferenceSpecies | null;
  pdfWeakReferenceSpecies: ReferenceSpecies[];
  openSetReferenceSpecies: ReferenceSpecies[];
  health: HealthResponse | null;
  onFile: (file: File | null) => void;
  onAnalyze: () => void;
  onClear: () => void;
  setConfidence: (value: number) => void;
  setFrameInterval: (value: number) => void;
  setIncludeLowConfidence: (value: boolean) => void;
}) {
  const hasResult = Boolean(props.result);
  const [detailEntry, setDetailEntry] = React.useState<KnowledgeEntry | null>(null);
  const canOpenDetail = hasResult && props.activeKnowledge.title !== "未知动物";

  return (
    <>
      <PageHeader eyebrow="智能识别" title="森智眼智能识别" subtitle="上传野外相机图片或视频，系统给出目标框、候选物种、置信度和知识库复核依据。" />
      <RuntimeStatusStrip health={props.health} />
      <section className="animal-layout">
        <aside className="tool-panel">
          <UploadPanel file={props.file} hasResult={hasResult} isLoading={props.isLoading} onFile={props.onFile} onAnalyze={props.onAnalyze} onClear={props.onClear} />
          <SettingsPanel {...props} />
        </aside>
        <main className="work-panel">
          <section className="analysis-workspace">
            <div className="workspace-main">
              <PreviewPanel file={props.file} previewSource={props.previewSource} />
              {hasResult ? (
                <SpeciesReportCard
                  result={props.result}
                  entry={props.activeKnowledge}
                  reference={props.activeReference}
                  canOpenDetail={canOpenDetail}
                  onOpenDetail={() => setDetailEntry(props.activeKnowledge)}
                />
              ) : null}
            </div>
            <aside className="workspace-side">
              <ResultInsight result={props.result} speciesKnowledge={props.speciesKnowledge} />
              <SessionSummary result={props.result} file={props.file} />
              {hasResult ? <ReferenceSampleCard reference={props.activeReference} /> : null}
            </aside>
          </section>
          <ResultDetailsPanel
            result={props.result}
            error={props.error}
            speciesKnowledge={props.speciesKnowledge}
            onOpenDetail={(entry) => setDetailEntry(entry)}
          />
        </main>
      </section>
      {detailEntry ? (
        <KnowledgeDetailModal
          entry={detailEntry}
          animalSpecies={props.speciesKnowledge}
          pdfWeakReferenceSpecies={props.pdfWeakReferenceSpecies}
          openSetReferenceSpecies={props.openSetReferenceSpecies}
          onClose={() => setDetailEntry(null)}
        />
      ) : null}
    </>
  );
}

function ResourceCenterPage({
  animalSpecies,
  pdfWeakReferenceSpecies,
  openSetReferenceSpecies,
}: {
  animalSpecies: SpeciesEntry[];
  pdfWeakReferenceSpecies: ReferenceSpecies[];
  openSetReferenceSpecies: ReferenceSpecies[];
}) {
  const [section, setSection] = React.useState<"animals" | "plants">("animals");
  return <>
    <PageHeader eyebrow="物种资源中心" title="动植物知识库" subtitle="按名称、学名、分类和保护等级集中查询物种资料。" />
    <div className="mobile-resource-tabs" role="tablist">
      <button className={section === "animals" ? "active" : ""} onClick={() => setSection("animals")}>动物知识库</button>
      <button className={section === "plants" ? "active" : ""} onClick={() => setSection("plants")}>植物知识库</button>
    </div>
    <KnowledgeLibraryPage view={section} animalSpecies={animalSpecies} pdfWeakReferenceSpecies={pdfWeakReferenceSpecies} openSetReferenceSpecies={openSetReferenceSpecies} />
  </>;
}

function FieldReportPage({ token, activeJobId, result }: { token: string; activeJobId: string | null; result: AnalysisResponse | null }) {
  const candidateName = result?.detections[0]?.species_label ?? "待确认物种";
  const [speciesName, setSpeciesName] = React.useState(candidateName);
  const [locationText, setLocationText] = React.useState("");
  const [notes, setNotes] = React.useState("");
  const [position, setPosition] = React.useState<{ latitude: number; longitude: number; accuracy: number } | null>(null);
  const [reports, setReports] = React.useState<FieldReport[]>([]);
  const [message, setMessage] = React.useState("");
  const [reportImage, setReportImage] = React.useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const headers = { Authorization: `Bearer ${token}` };
  const reportImagePreview = React.useMemo(() => reportImage ? URL.createObjectURL(reportImage) : "", [reportImage]);

  React.useEffect(() => () => {
    if (reportImagePreview) URL.revokeObjectURL(reportImagePreview);
  }, [reportImagePreview]);

  const loadReports = React.useCallback(() => {
    fetch(`${API_BASE}/api/v1/field-reports`, { headers })
      .then((response) => response.ok ? response.json() : [])
      .then(setReports).catch(() => setReports([]));
  }, [token]);
  React.useEffect(loadReports, [loadReports]);
  React.useEffect(() => setSpeciesName(candidateName), [candidateName]);

  function locate() {
    if (!navigator.geolocation) { setMessage("当前设备不支持定位，请手动填写地点"); return; }
    setMessage("正在获取位置…");
    navigator.geolocation.getCurrentPosition(
      (value) => { setPosition({ latitude: value.coords.latitude, longitude: value.coords.longitude, accuracy: value.coords.accuracy }); setMessage("已获取当前位置"); },
      () => setMessage("定位失败，请手动填写监测点或地点"),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!reportImage && !activeJobId) {
      setMessage("请先拍照或选择一张现场图片");
      return;
    }
    setIsSubmitting(true);
    setMessage(reportImage ? "正在上传现场图片…" : "正在提交…");
    try {
      let reportJobId = activeJobId;
      if (reportImage) {
        const form = new FormData();
        form.append("file", reportImage);
        form.append("confidence_threshold", "0.35");
        form.append("include_low_confidence", "true");
        const uploadResponse = await fetch(`${API_BASE}/api/v1/analysis-jobs`, { method: "POST", headers, body: form });
        if (!uploadResponse.ok) throw new Error((await uploadResponse.json()).detail ?? "现场图片上传失败");
        const job: AnalysisJob = await uploadResponse.json();
        reportJobId = job.id;
        setMessage("图片上传成功，正在提交上报…");
      }
      const response = await fetch(`${API_BASE}/api/v1/field-reports`, {
        method: "POST", headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ analysis_job_id: reportJobId, species_name: speciesName, location_text: locationText, notes, latitude: position?.latitude, longitude: position?.longitude, location_accuracy: position?.accuracy }),
      });
      if (!response.ok) throw new Error((await response.json()).detail ?? "上报失败");
      setMessage("上报成功，图片和记录已进入专家复核队列");
      setNotes("");
      setReportImage(null);
      loadReports();
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "上报失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  return <>
    <PageHeader eyebrow="重点物种上报" title="提交现场发现" subtitle="图片、时间、位置和备注将供管理端专家确认并留档。" />
    <section className="report-entry-grid">
      <form className="card field-report-form" onSubmit={submit}>
        <div className="card-title"><ShieldCheck size={18}/><span>上报信息</span></div>
        <label className="field-report-upload">
          <span>现场图片</span>
          <div className={`field-report-upload-box ${reportImagePreview ? "has-preview" : ""}`}>
            {reportImagePreview ? <img src={reportImagePreview} alt="现场图片预览" /> : <><Camera size={30}/><strong>拍照或从相册选择</strong><small>{activeJobId ? "已关联当前识别图片，也可以重新选择" : "上报需附带一张现场图片"}</small></>}
          </div>
          <input type="file" accept="image/*" capture="environment" onChange={(event) => setReportImage(event.target.files?.[0] ?? null)} />
        </label>
        {reportImage ? <button type="button" className="secondary-action compact-action field-report-image-clear" onClick={() => setReportImage(null)}><Trash2 size={15}/><span>移除所选图片</span></button> : null}
        <label><span>候选物种</span><input value={speciesName} onChange={(event) => setSpeciesName(event.target.value)} required /></label>
        <label><span>监测点或地点</span><input value={locationText} onChange={(event) => setLocationText(event.target.value)} placeholder="定位失败时请手动填写" /></label>
        <label><span>现场备注</span><textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={4} placeholder="数量、行为、生境及其他观察信息" /></label>
        <div className="field-report-actions"><button type="button" className="secondary-action" onClick={locate} disabled={isSubmitting}>获取位置</button><button type="submit" className="primary-action" disabled={isSubmitting}>{isSubmitting ? <Loader2 className="spin" size={17}/> : null}{isSubmitting ? "提交中…" : "提交上报"}</button></div>
        {position ? <small>位置：{position.latitude.toFixed(5)}, {position.longitude.toFixed(5)}（精度约 {Math.round(position.accuracy)} 米）</small> : null}
        {message ? <div className="notice-banner">{message}</div> : null}
      </form>
      <section className="card">
        <div className="card-title"><History size={18}/><span>我的上报</span></div>
        <div className="field-report-list">{reports.length ? reports.map((report) => <article key={report.id}><div><strong>{report.final_species_name || report.species_name}</strong><span>{new Date(report.created_at).toLocaleString("zh-CN")}</span></div><span className={`status-chip ${report.status === "resolved" ? "ready" : "needs-review"}`}>{report.status === "resolved" ? "已复核" : "待复核"}</span>{report.review_comment ? <p>专家意见：{report.review_comment}</p> : null}</article>) : <EmptyState icon={<ShieldCheck size={40}/>} text="还没有重点物种上报记录" />}</div>
      </section>
    </section>
  </>;
}

function KnowledgeLibraryPage({
  view,
  animalSpecies,
  pdfWeakReferenceSpecies,
  openSetReferenceSpecies,
}: {
  view: "animals" | "plants" | "gallery";
  animalSpecies: SpeciesEntry[];
  pdfWeakReferenceSpecies: ReferenceSpecies[];
  openSetReferenceSpecies: ReferenceSpecies[];
}) {
  const [query, setQuery] = React.useState("");
  const [protectionFilter, setProtectionFilter] = React.useState<"all" | "level1" | "level2">("all");
  const [tierFilter, setTierFilter] = React.useState<"all" | "priority" | "candidate" | "operational">("all");
  const [plantLifeFormFilter, setPlantLifeFormFilter] = React.useState("all");
  const [visibleKnowledgeCount, setVisibleKnowledgeCount] = React.useState(24);
  const [visiblePdfCount, setVisiblePdfCount] = React.useState(48);
  const [selectedGuideEntry, setSelectedGuideEntry] = React.useState<ReferenceSpecies | null>(null);
  const [selectedKnowledgeEntry, setSelectedKnowledgeEntry] = React.useState<KnowledgeEntry | null>(null);
  const animalEntries = sortSpecies(animalSpecies.filter(isWildlifeCatalogSpecies)).map(speciesToKnowledgeEntry);
  const plantEntries = sortSpecies(animalSpecies.filter((entry) => entry.category === "plant")).map(speciesToKnowledgeEntry);
  const plantLifeForms = Array.from(new Set(plantEntries.map((entry) => entry.lifeForm).filter(Boolean) as string[]))
    .sort((left, right) => left.localeCompare(right, "zh-Hans-CN"));
  const catalogEntries = view === "gallery"
    ? animalEntries.filter((entry) => matchesKnowledgeFilters(entry, query, protectionFilter))
    : [];
  const filteredPdfWeakReferences = view === "gallery" ? pdfWeakReferenceSpecies.filter((entry) => matchesReferenceFilters(entry, query)) : [];
  const visibleCatalogEntries = catalogEntries.slice(0, visibleKnowledgeCount);
  const visiblePdfWeakReferences = filteredPdfWeakReferences.slice(0, visiblePdfCount);
  const filteredAnimals = view === "animals"
    ? animalEntries
      .filter((entry) => matchesKnowledgeFilters(entry, query, protectionFilter))
      .filter((entry) => matchesAnimalTier(entry, tierFilter))
    : [];
  const filteredPlants = view === "plants"
    ? plantEntries
      .filter((entry) => matchesKnowledgeFilters(entry, query, protectionFilter))
      .filter((entry) => plantLifeFormFilter === "all" || entry.lifeForm === plantLifeFormFilter)
    : [];
  const visibleAnimals = filteredAnimals.slice(0, visibleKnowledgeCount);
  const visiblePlants = filteredPlants.slice(0, visibleKnowledgeCount);
  const priorityAnimals = filteredAnimals.filter((entry) => entry.protectionLevel?.includes("一级"));
  const secondaryAnimals = filteredAnimals.filter((entry) => !entry.protectionLevel?.includes("一级") && entry.protectionLevel?.includes("二级"));
  const operationalAnimals = filteredAnimals.filter((entry) => !entry.protectionLevel?.includes("一级") && !entry.protectionLevel?.includes("二级"));
  const visiblePriorityAnimals = visibleAnimals.filter((entry) => entry.protectionLevel?.includes("一级"));
  const visibleSecondaryAnimals = visibleAnimals.filter((entry) => !entry.protectionLevel?.includes("一级") && entry.protectionLevel?.includes("二级"));
  const visibleOperationalAnimals = visibleAnimals.filter((entry) => !entry.protectionLevel?.includes("一级") && !entry.protectionLevel?.includes("二级"));
  const directRecognitionAnimals = filteredAnimals.filter((entry) => DIRECT_RECOGNITION_TIERS.has(entry.recognitionTier ?? ""));
  const referenceOnlyAnimals = filteredAnimals.length - directRecognitionAnimals.length;
  const protectedPlants = plantEntries.filter((entry) => entry.protectionLevel?.includes("一级") || entry.protectionLevel?.includes("二级"));
  const plantFamilyCount = new Set(plantEntries.map((entry) => entry.family).filter(Boolean)).size;
  const resultCount = view === "gallery"
    ? catalogEntries.length
    : filteredAnimals.length + filteredPlants.length;
  const displayedKnowledgeCount = view === "animals" ? visibleAnimals.length : visiblePlants.length;
  const activeKnowledgeCount = view === "animals" ? filteredAnimals.length : filteredPlants.length;
  const hasActiveFilters = Boolean(query.trim()) || protectionFilter !== "all" || (view === "animals" && tierFilter !== "all") || (view === "plants" && plantLifeFormFilter !== "all");
  const pageCopy = {
    animals: {
      eyebrow: "动物知识库",
      title: "广西重点保护野生动物知识库",
      subtitle: "统一检索哺乳类、鸟类、爬行与两栖类等物种的中文名、学名、分类、保护等级和识别特征。",
    },
    plants: {
      eyebrow: "植物知识库",
      title: "广西植物知识库",
      subtitle: "整理植物识别所需的叶、花、果、生境和采集要点，支持现场查询和采集记录。",
    },
    gallery: {
      eyebrow: "物种图鉴",
      title: "广西重点保护野生动物图鉴",
      subtitle: "按 400 多个物种目录浏览，并查看口袋书图鉴图片。",
    },
  }[view];

  function resetFilters() {
    setQuery("");
    setProtectionFilter("all");
    setTierFilter("all");
    setPlantLifeFormFilter("all");
    setVisibleKnowledgeCount(24);
    setVisiblePdfCount(48);
  }

  React.useEffect(() => {
    setVisibleKnowledgeCount(24);
    setVisiblePdfCount(48);
  }, [view, query, protectionFilter, tierFilter, plantLifeFormFilter]);

  return (
    <>
      <PageHeader eyebrow={pageCopy.eyebrow} title={pageCopy.title} subtitle={pageCopy.subtitle} />
      <section className="knowledge-toolbar">
        {view === "animals" ? (
          <div className="knowledge-switch" role="tablist" aria-label="识别层级">
            <button type="button" className={tierFilter === "all" ? "active" : ""} onClick={() => setTierFilter("all")}>全部层级</button>
            <button type="button" className={tierFilter === "priority" ? "active" : ""} onClick={() => setTierFilter("priority")}>一级优先</button>
            <button type="button" className={tierFilter === "candidate" ? "active" : ""} onClick={() => setTierFilter("candidate")}>候选识别</button>
          </div>
        ) : null}
        {view === "plants" ? (
          <label className="filter-field">
            <span>生活型</span>
            <select value={plantLifeFormFilter} onChange={(event) => setPlantLifeFormFilter(event.target.value)}>
              <option value="all">全部生活型</option>
              {plantLifeForms.map((lifeForm) => <option key={lifeForm} value={lifeForm}>{lifeForm}</option>)}
            </select>
          </label>
        ) : null}
        <label className="search-field">
          <span>物种检索</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="输入中文名、学名、科属、特征或保护等级" />
        </label>
        <label className="filter-field">
          <span>保护等级</span>
          <select value={protectionFilter} onChange={(event) => setProtectionFilter(event.target.value as "all" | "level1" | "level2")}>
            <option value="all">全部</option>
            <option value="level1">国家一级</option>
            <option value="level2">国家二级</option>
          </select>
        </label>
        <div className="filter-count">
          <strong>{resultCount}</strong>
          <span>{view === "gallery" ? "个物种" : "条知识卡"}</span>
        </div>
        <button className="secondary-action compact-action filter-reset-action" type="button" disabled={!hasActiveFilters} onClick={resetFilters}>
          <X size={16} />
          <span>重置</span>
        </button>
      </section>
      <details className="card knowledge-note compact-disclosure">
        <summary>
          {view === "gallery" ? <BookOpen size={18} /> : <Leaf size={18} />}
          <span>{view === "gallery" ? "图鉴使用说明" : view === "plants" ? "植物知识说明" : "动物知识说明"}</span>
        </summary>
        {view === "gallery" ? (
          <ul className="compact-list">
            <li>浏览口袋书图鉴，用于物种对照和讲解。</li>
            <li>物种目录覆盖哺乳类、鸟类、爬行与两栖类等 400 多个条目。</li>
            <li>点击卡片可查看大图、学名、类群和保护等级。</li>
            <li>图鉴图片默认按质量筛过，截图/遮挡问题的条目会被单独处理。</li>
          </ul>
        ) : view === "plants" ? (
          <ul className="compact-list">
            <li>按中文名、学名、科属和特征检索植物条目。</li>
            <li>用于查询植物形态、生境和采集要点，便于现场补充记录。</li>
            <li>当前以知识展示为主，不混入动物图鉴统计。</li>
          </ul>
        ) : (
          <ul className="compact-list">
            <li>按中文名、学名、分类、保护等级和识别特征快速检索。</li>
            <li>条目覆盖哺乳类、鸟类、爬行与两栖类，不只显示哺乳动物子集。</li>
            <li>重点物种和补充条目分层浏览，适合汇报、讲解和现场查询。</li>
          </ul>
        )}
      </details>
      <section className="knowledge-summary">
        {view === "animals" ? (
          <>
            <div className="summary-pill">
              <strong>{animalEntries.length}</strong>
              <span>物种总目录</span>
            </div>
            <div className="summary-pill">
              <strong>{priorityAnimals.length}</strong>
              <span>一级物种</span>
            </div>
            <div className="summary-pill">
              <strong>{secondaryAnimals.length}</strong>
              <span>二级物种</span>
            </div>
            <div className="summary-pill">
              <strong>{operationalAnimals.length}</strong>
              <span>补充条目</span>
            </div>
            <div className="summary-pill">
              <strong>{directRecognitionAnimals.length}</strong>
              <span>可直接识别</span>
            </div>
            <div className="summary-pill">
              <strong>{referenceOnlyAnimals}</strong>
              <span>图鉴参考</span>
            </div>
            <div className="summary-pill">
              <strong>{displayedKnowledgeCount}/{activeKnowledgeCount}</strong>
              <span>当前显示</span>
            </div>
          </>
        ) : view === "plants" ? (
          <>
            <div className="summary-pill">
              <strong>{plantEntries.length}</strong>
              <span>植物条目</span>
            </div>
            <div className="summary-pill">
              <strong>{protectedPlants.length}</strong>
              <span>重点保护</span>
            </div>
            <div className="summary-pill">
              <strong>{plantLifeForms.length}</strong>
              <span>生活型</span>
            </div>
            <div className="summary-pill">
              <strong>{plantFamilyCount}</strong>
              <span>科</span>
            </div>
            <div className="summary-pill">
              <strong>{displayedKnowledgeCount}/{activeKnowledgeCount}</strong>
              <span>当前显示</span>
            </div>
          </>
        ) : (
          <>
            <div className="summary-pill">
              <strong>{catalogEntries.length}</strong>
              <span>物种目录</span>
            </div>
            <div className="summary-pill">
              <strong>{filteredPdfWeakReferences.length}</strong>
              <span>口袋书图鉴</span>
            </div>
            <div className="summary-pill">
              <strong>{filteredPdfWeakReferences.length}</strong>
              <span>参考图片</span>
            </div>
            <div className="summary-pill">
              <strong>{visibleCatalogEntries.length}/{catalogEntries.length}</strong>
              <span>当前显示</span>
            </div>
          </>
        )}
      </section>
      {view === "gallery" ? (
        <>
          <section className="section-head">
            <div>
              <span className="eyebrow">物种目录</span>
              <h3>400+ 物种图文入口</h3>
            </div>
          </section>
          <section className="plant-grid catalog-species-grid">
            {visibleCatalogEntries.length ? (
              visibleCatalogEntries.map((entry) => (
                <KnowledgeCard key={`${entry.title}-${entry.latin}`} entry={entry} onOpen={() => setSelectedKnowledgeEntry(entry)} />
              ))
            ) : (
              <EmptyState text="暂无匹配的物种目录条目" />
            )}
          </section>
          <LoadMoreControl
            visible={visibleCatalogEntries.length}
            total={catalogEntries.length}
            label="物种目录"
            step={36}
            onLoadMore={() => setVisibleKnowledgeCount((count) => count + 36)}
          />
        </>
      ) : null}
      {view === "gallery" ? <section className="section-head">
        <div>
          <span className="eyebrow">口袋书图鉴</span>
          <h3>物种参考图像</h3>
        </div>
      </section> : null}
      {filteredPdfWeakReferences.length ? (
        <p className="pdf-reference-count">当前显示 {visiblePdfWeakReferences.length} / {filteredPdfWeakReferences.length} 张图鉴图片</p>
      ) : null}
      {view === "gallery" ? <section className="pdf-reference-grid">
        {filteredPdfWeakReferences.length ? (
          visiblePdfWeakReferences.map((entry) => (
            <PdfWeakReferenceCard
              key={`${entry.folder_name}-${entry.samples[0]?.file_name}`}
              entry={entry}
              onOpen={() => setSelectedGuideEntry(entry)}
            />
          ))
        ) : (
          <EmptyState text="暂无匹配的图鉴图片" />
        )}
      </section> : null}
      {view === "gallery" ? (
        <LoadMoreControl
          visible={visiblePdfWeakReferences.length}
          total={filteredPdfWeakReferences.length}
          label="图鉴图片"
          step={48}
          onLoadMore={() => setVisiblePdfCount((count) => count + 48)}
        />
      ) : null}
      {selectedGuideEntry ? (
        <SpeciesGuideModal
          entry={selectedGuideEntry}
          species={findSpeciesForReference(selectedGuideEntry, animalSpecies)}
          onClose={() => setSelectedGuideEntry(null)}
        />
      ) : null}
      {view === "animals" ? <section className="section-head">
        <div>
          <span className="eyebrow">动物重点物种</span>
          <h3>按保护等级和识别优先级分层浏览</h3>
        </div>
      </section> : null}
      {view === "animals" ? <section className="plant-grid">
        {visiblePriorityAnimals.length ? visiblePriorityAnimals.map((entry) => <KnowledgeCard key={`${entry.title}-${entry.latin}`} entry={entry} onOpen={() => setSelectedKnowledgeEntry(entry)} />) : null}
      </section> : null}
      {view === "animals" && visibleSecondaryAnimals.length ? (
        <>
          <section className="section-head">
            <div>
              <span className="eyebrow">国家二级</span>
              <h3>候选识别与复核重点</h3>
            </div>
          </section>
          <section className="plant-grid">
            {visibleSecondaryAnimals.map((entry) => <KnowledgeCard key={`${entry.title}-${entry.latin}`} entry={entry} onOpen={() => setSelectedKnowledgeEntry(entry)} />)}
          </section>
        </>
      ) : null}
      {view === "animals" && visibleOperationalAnimals.length ? (
        <>
          <section className="section-head">
            <div>
              <span className="eyebrow">补充条目</span>
              <h3>监测对照和场景类对象</h3>
            </div>
          </section>
          <section className="plant-grid">
            {visibleOperationalAnimals.map((entry) => <KnowledgeCard key={`${entry.title}-${entry.latin}`} entry={entry} onOpen={() => setSelectedKnowledgeEntry(entry)} />)}
          </section>
        </>
      ) : null}
      {view === "animals" ? (
        <LoadMoreControl
          visible={visibleAnimals.length}
          total={filteredAnimals.length}
          label="动物知识卡"
          step={24}
          onLoadMore={() => setVisibleKnowledgeCount((count) => count + 24)}
        />
      ) : null}
      {view === "animals" && !filteredAnimals.length ? <EmptyState text="暂无匹配的动物知识条目" /> : null}
      {view === "plants" ? <section className="section-head">
        <div>
          <span className="eyebrow">植物知识模块</span>
          <h3>植物条目查询与采集要点</h3>
        </div>
      </section> : null}
      {view === "plants" ? <section className="plant-grid">
        {visiblePlants.length ? visiblePlants.map((entry) => <KnowledgeCard key={entry.latin} entry={entry} onOpen={() => setSelectedKnowledgeEntry(entry)} />) : <EmptyState text="暂无匹配的植物知识条目" />}
      </section> : null}
      {view === "plants" ? (
        <LoadMoreControl
          visible={visiblePlants.length}
          total={filteredPlants.length}
          label="植物知识卡"
          step={24}
          onLoadMore={() => setVisibleKnowledgeCount((count) => count + 24)}
        />
      ) : null}
      {view === "plants" ? <section className="plant-feature-grid">
        <InfoBlock title="采集优先级" items={["叶片近景优先", "花果其次", "树皮和枝条作为补充", "尽量保留整株与环境信息"]} />
        <InfoBlock title="识别重点" items={["叶形与叶缘", "叶脉走向", "花果颜色与形态", "季节和生境"]} />
        <InfoBlock title="采集记录" items={["拍摄叶片正反面", "补充花果特写", "记录生境位置", "保留人工复核结果"]} />
      </section> : null}
      {selectedKnowledgeEntry ? (
        <KnowledgeDetailModal
          entry={selectedKnowledgeEntry}
          animalSpecies={animalSpecies}
          pdfWeakReferenceSpecies={pdfWeakReferenceSpecies}
          openSetReferenceSpecies={openSetReferenceSpecies}
          onClose={() => setSelectedKnowledgeEntry(null)}
        />
      ) : null}
    </>
  );
}

function mapDetectionToKnowledge(detection: Detection, speciesKnowledge: SpeciesEntry[]): { species: SpeciesEntry; label: string } | null {
  const labels = [detection.species_label, ...(detection.top_candidates ?? []).map((candidate) => candidate.label)];
  for (const label of labels) {
    const species = speciesKnowledge.find((entry) => matchesSpecies(label, entry));
    if (species) return { species, label: species.cn_name };
  }
  return null;
}

function EcologyAssistantPage({
  speciesKnowledge,
  result,
}: {
  speciesKnowledge: SpeciesEntry[];
  result: AnalysisResponse | null;
}) {
  const [question, setQuestion] = React.useState("");
  const [contextSpeciesId, setContextSpeciesId] = React.useState("");
  const [turns, setTurns] = React.useState<AssistantTurn[]>([]);
  const [isAsking, setIsAsking] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const firstDetection = result?.detections[0];
  const mappedDetection = firstDetection ? mapDetectionToKnowledge(firstDetection, speciesKnowledge) : null;
  const suggestedSpeciesId = mappedDetection?.species?.species_id ?? "";
  const activeContextId = contextSpeciesId || undefined;
  const latest = turns[0]?.response;
  const latestTurn = turns[0];
  const historyTurns = turns.slice(1);

  async function ask(nextQuestion?: string) {
    const text = (nextQuestion ?? question).trim();
    if (!text || isAsking) return;
    setIsAsking(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/assistant/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text,
          context_species_id: activeContextId,
          messages: turns.slice(0, 6).flatMap((turn) => [
            { role: "user", content: turn.question },
            { role: "assistant", content: turn.response.answer },
          ]),
        }),
      });
      if (!response.ok) throw new Error(await response.text());
      const payload = (await response.json()) as AssistantChatResponse;
      setTurns((items) => [{ question: text, response: payload }, ...items].slice(0, 8));
      setQuestion("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "助手暂时不可用");
    } finally {
      setIsAsking(false);
    }
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    ask();
  }

  function clearConversation() {
    setTurns([]);
    setError(null);
  }

  return (
    <>
      <PageHeader eyebrow="生态助手" title="生态知识问答助手" subtitle="基于本地物种知识库解释识别结果、物种特征、相似物种和复核建议。" />
      <section className="assistant-layout">
        <aside className="assistant-compose card">
          <div className="card-title">
            <Sparkles size={18} />
            <span>提问</span>
          </div>
          <form onSubmit={submit}>
            <label className="filter-field">
              <span>关联物种</span>
              <select value={contextSpeciesId} onChange={(event) => setContextSpeciesId(event.target.value)}>
                <option value="">{suggestedSpeciesId ? "使用当前识别候选" : "自动匹配问题"}</option>
                {sortSpecies(speciesKnowledge).map((species) => (
                  <option key={species.species_id} value={species.species_id}>
                    {species.cn_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="assistant-question">
              <span>问题</span>
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="例如：大灵猫有哪些稳定识别特征？黑熊结果为什么需要复核？"
                rows={7}
              />
            </label>
            <button className="primary" type="submit" disabled={!question.trim() || isAsking}>
              {isAsking ? <Loader2 size={18} className="spin" /> : <Send size={18} />}
              <span>{isAsking ? "生成中" : "发送问题"}</span>
            </button>
            <button className="secondary-action" type="button" disabled={!question.trim()} onClick={() => setQuestion("")}>
              <X size={16} />
              <span>清空输入</span>
            </button>
          </form>
          {error ? <p className="error">{error}</p> : null}
          <div className="quick-question-list">
            {(latest?.suggested_questions ?? [
              "识别结果置信度低时应该怎么处理？",
              "大灵猫和相似物种怎么区分？",
              "知识库里的保护等级怎么看？",
            ]).map((item) => (
              <button key={item} type="button" onClick={() => ask(item)}>
                {item}
              </button>
            ))}
          </div>
        </aside>
        <main className="assistant-main">
          <section className="assistant-status-grid">
            <MetricCard label="知识来源" value={`${speciesKnowledge.length} 条`} hint="本地物种知识库" />
            <MetricCard label="回答模式" value="知识库问答" hint="基于本地物种资料生成" />
            <MetricCard label="识别联动" value={mappedDetection?.label ?? "待识别"} hint="可结合当前候选解释" />
          </section>
          {latestTurn ? (
            <section className="assistant-session">
              <div className="assistant-session-bar">
                <div>
                  <strong>当前会话</strong>
                  <span>{turns.length} 条问答，历史内容已折叠</span>
                </div>
                <button className="secondary-action compact-action" type="button" onClick={clearConversation}>
                  <Trash2 size={16} />
                  <span>清空会话</span>
                </button>
              </div>
              <section className="assistant-turns">
                <AssistantAnswerCard turn={latestTurn} />
                {historyTurns.length ? (
                  <div className="assistant-history-list">
                    {historyTurns.map((turn, index) => (
                      <details className="assistant-history-item" key={`${turn.question}-${index}`}>
                        <summary>
                          <span>历史问题</span>
                          <strong>{turn.question}</strong>
                        </summary>
                        <AssistantAnswerCard turn={turn} compact />
                      </details>
                    ))}
                  </div>
                ) : null}
              </section>
            </section>
          ) : (
            <EmptyState icon={<Bot size={44} />} text="选择一个快捷问题，或输入物种特征、识别结果、复核判断相关问题。" />
          )}
        </main>
      </section>
    </>
  );
}

function AssistantAnswerCard({ turn, compact = false }: { turn: AssistantTurn; compact?: boolean }) {
  return (
    <article className={`assistant-answer-card ${compact ? "compact" : ""}`}>
      <div className="assistant-question-row">
        <span>问题</span>
        <strong>{turn.question}</strong>
      </div>
      <p className="assistant-answer">{turn.response.answer}</p>
      <p className="assistant-review">{turn.response.review_notice}</p>
      {turn.response.sources.length ? (
        <div className="assistant-source-grid">
          {turn.response.sources.map((source) => (
            <div key={source.species_id} className="assistant-source-card">
              <strong>{source.cn_name}</strong>
              <span>{source.latin_name || "暂无学名资料"}</span>
              <p>{source.protection_level}</p>
              <small>{source.matched_fields.join("、")}</small>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function RecordsPage({
  history,
  speciesKnowledge,
  pdfWeakReferenceSpecies,
  openSetReferenceSpecies,
  modelStatus,
  onOpen,
}: {
  history: AnalysisResponse[];
  speciesKnowledge: SpeciesEntry[];
  pdfWeakReferenceSpecies: ReferenceSpecies[];
  openSetReferenceSpecies: ReferenceSpecies[];
  modelStatus?: Record<string, string>;
  onOpen: (item: AnalysisResponse) => void;
}) {
  const [copiedId, setCopiedId] = React.useState<string | null>(null);
  const [visibleHistoryCount, setVisibleHistoryCount] = React.useState(20);
  const [recordQuery, setRecordQuery] = React.useState("");
  const [mediaFilter, setMediaFilter] = React.useState<"all" | "image" | "video">("all");
  const [reviewFilter, setReviewFilter] = React.useState<"all" | "ready" | "review" | "empty">("all");
  const [confidenceFilter, setConfidenceFilter] = React.useState<"all" | "high" | "medium" | "low">("all");
  const [recordSort, setRecordSort] = React.useState<"newest" | "oldest" | "confidence_desc" | "confidence_asc">("newest");
  const imageCount = history.filter((item) => item.media_type === "image").length;
  const videoCount = history.filter((item) => item.media_type === "video").length;
  const latest = history[0];
  const latestSummary = latest ? buildReportSummary(latest, speciesKnowledge) : "";
  const [detailEntry, setDetailEntry] = React.useState<KnowledgeEntry | null>(null);
  const filteredHistory = sortRecordHistory(
    history
      .filter((item) => matchesRecordFilters(item, speciesKnowledge, recordQuery, mediaFilter, reviewFilter))
      .filter((item) => matchesRecordConfidence(item, confidenceFilter)),
    recordSort
  );
  const recentHistory = filteredHistory.slice(0, 20);
  const olderHistory = filteredHistory.slice(20);
  const visibleOlderHistory = olderHistory.slice(0, Math.max(0, visibleHistoryCount - 20));

  async function copySummary(item: AnalysisResponse) {
    const text = buildReportSummary(item, speciesKnowledge);
    const copied = await copyTextToClipboard(text);
    if (copied) {
      setCopiedId(item.media_id);
      window.setTimeout(() => setCopiedId((current) => (current === item.media_id ? null : current)), 1600);
      return;
    }
    window.prompt("浏览器不允许自动复制，请手动复制摘要：", text);
  }

  function resetHistoryView() {
    setVisibleHistoryCount(20);
  }

  React.useEffect(() => {
    resetHistoryView();
  }, [history.length, recordQuery, mediaFilter, reviewFilter, confidenceFilter, recordSort]);

  return (
    <>
      <PageHeader eyebrow="识别记录" title="历史识别任务" subtitle="集中回看识别结果、复核状态和任务摘要，便于持续管理识别记录。" />
      <section className="records-shell">
        <div className="records-main">
          <section className="card records-summary">
            <div className="card-title"><History size={18} /><span>记录概览</span></div>
            <div className="summary-grid">
              <MetricCard label="记录总数" value={String(history.length)} hint="本地保存的识别结果" />
              <MetricCard label="图片任务" value={String(imageCount)} hint="上传图片后保存的任务" />
              <MetricCard label="视频任务" value={String(videoCount)} hint="上传视频后保存的任务" />
            </div>
            <p className="summary-note">{latest ? `最新一条结果：${latest.message}` : "当前还没有历史记录，上传一张图就会出现这里。"}</p>
          </section>
          <section className="records-list-panel">
            <div className="records-filter-bar">
              <label className="search-field">
                <span>搜索记录</span>
                <input value={recordQuery} onChange={(event) => setRecordQuery(event.target.value)} placeholder="物种、学名、任务编号、摘要" />
              </label>
              <label className="filter-field">
                <span>媒体类型</span>
                <select value={mediaFilter} onChange={(event) => setMediaFilter(event.target.value as "all" | "image" | "video")}>
                  <option value="all">全部</option>
                  <option value="image">图片</option>
                  <option value="video">视频</option>
                </select>
              </label>
              <label className="filter-field">
                <span>复核状态</span>
                <select value={reviewFilter} onChange={(event) => setReviewFilter(event.target.value as "all" | "ready" | "review" | "empty")}>
                  <option value="all">全部</option>
                  <option value="ready">可展示</option>
                  <option value="review">需复核</option>
                  <option value="empty">无目标</option>
                </select>
              </label>
              <label className="filter-field">
                <span>置信度</span>
                <select value={confidenceFilter} onChange={(event) => setConfidenceFilter(event.target.value as "all" | "high" | "medium" | "low")}>
                  <option value="all">全部</option>
                  <option value="high">高置信</option>
                  <option value="medium">中置信</option>
                  <option value="low">低置信</option>
                </select>
              </label>
              <label className="filter-field">
                <span>排序</span>
                <select value={recordSort} onChange={(event) => setRecordSort(event.target.value as "newest" | "oldest" | "confidence_desc" | "confidence_asc")}>
                  <option value="newest">最新优先</option>
                  <option value="oldest">最旧优先</option>
                  <option value="confidence_desc">高置信优先</option>
                  <option value="confidence_asc">低置信优先</option>
                </select>
              </label>
              <div className="filter-count records-filter-count">
                <strong>{filteredHistory.length}</strong>
                <span>匹配记录</span>
              </div>
              <button
                className="secondary-action compact-action filter-reset-action"
                type="button"
                onClick={() => {
                  setRecordQuery("");
                  setMediaFilter("all");
                  setReviewFilter("all");
                  setConfidenceFilter("all");
                  setRecordSort("newest");
                }}
              >
                重置
              </button>
            </div>
            <div className="records-list-head">
              <div>
                <span className="eyebrow">历史列表</span>
                <strong>{filteredHistory.length ? `共 ${filteredHistory.length} 条记录` : history.length ? "无匹配记录" : "暂无记录"}</strong>
              </div>
              {latest ? <span>{latest.media_type === "video" ? "最新为视频任务" : "最新为图片任务"}</span> : null}
            </div>
            <div className="records-list">
              {history.length > 0 && filteredHistory.length === 0 ? (
                <EmptyState text="没有匹配的识别记录" />
              ) : null}
              {history.length === 0 ? (
                <EmptyState text="暂无分析记录" />
              ) : (
                recentHistory.map((item) => (
                  <RecordReportRow
                    key={item.media_id}
                    item={item}
                    speciesKnowledge={speciesKnowledge}
                    isCopied={copiedId === item.media_id}
                    onCopy={copySummary}
                    onOpen={onOpen}
                    onOpenDetail={(entry) => setDetailEntry(entry)}
                    pdfWeakReferenceSpecies={pdfWeakReferenceSpecies}
                    openSetReferenceSpecies={openSetReferenceSpecies}
                  />
                ))
              )}
            </div>
            {olderHistory.length ? (
              <details className="records-history-toggle card">
                <summary>
                  <span>更早记录</span>
                  <strong>{olderHistory.length} 条</strong>
                </summary>
                <div className="records-history-more">
                  {visibleOlderHistory.length ? (
                    <div className="records-list">
                      {visibleOlderHistory.map((item) => (
                        <RecordReportRow
                          key={item.media_id}
                          item={item}
                          speciesKnowledge={speciesKnowledge}
                          isCopied={copiedId === item.media_id}
                          onCopy={copySummary}
                          onOpen={onOpen}
                          onOpenDetail={(entry) => setDetailEntry(entry)}
                          pdfWeakReferenceSpecies={pdfWeakReferenceSpecies}
                          openSetReferenceSpecies={openSetReferenceSpecies}
                        />
                      ))}
                    </div>
                  ) : (
                    <p className="summary-note">默认只显示最近 20 条，点击下方按钮查看更早记录。</p>
                  )}
                  {visibleHistoryCount < filteredHistory.length ? (
                    <LoadMoreControl
                      visible={visibleHistoryCount}
                      total={filteredHistory.length}
                      label="历史记录"
                      step={20}
                      onLoadMore={() => setVisibleHistoryCount((count) => count + 20)}
                    />
                  ) : null}
                </div>
              </details>
            ) : null}
          </section>
        </div>
        <aside className="records-side">
          <InfoBlock title="使用方式" items={["点击打开可切回对应结果", "复制摘要可直接放入汇报材料", "历史结果保存在本地 JSON 文件中"]} />
          {latest ? (
            <section className="card report-text-card">
              <div className="card-title"><Copy size={18} /><span>最新报告摘要</span></div>
              <pre>{latestSummary}</pre>
              <button className="secondary-action" onClick={() => copySummary(latest)}>
                {copiedId === latest.media_id ? <Check size={16} /> : <Copy size={16} />}
                {copiedId === latest.media_id ? "已复制" : "复制最新摘要"}
              </button>
            </section>
          ) : null}
          <InfoBlock
            title="结果提示"
            items={
              latest
                ? [`最新媒体类型：${latest.media_type}`, `最新目标数：${latest.detections.length}`, `最新结果：${latest.message}`]
                : ["暂无最近结果", "上传素材后会自动出现在这里", "可作为任务回看入口"]
            }
          />
        </aside>
      </section>
      {detailEntry ? (
        <KnowledgeDetailModal
          entry={detailEntry}
          animalSpecies={speciesKnowledge}
          pdfWeakReferenceSpecies={pdfWeakReferenceSpecies}
          openSetReferenceSpecies={openSetReferenceSpecies}
          onClose={() => setDetailEntry(null)}
        />
      ) : null}
      <section className="system-grid">
        <InfoBlock title="能力说明" items={["目标定位：自动标出画面中的动物区域", "物种判断：给出候选物种与置信度", "图鉴检索：关联口袋书和相似物种参考图", "结果展示：候选结论、复核提示和参考图"]} />
        <InfoBlock title="识别策略" items={["高置信且证据一致的结果可作为候选展示", "非目标物种、低置信度或证据冲突结果保持未知/待复核", "植物暂作为知识库查询内容", "图鉴图片用于物种浏览和结果对照"]} />
        <InfoBlock title="数据维护" items={["持续补充稳定验证图片", "保留人工复核与纠错沉淀", "优先优化重点物种和常见混淆对", "按需扩展植物识别或外部识别服务"]} />
        <InfoBlock title="运行状态" items={[`目标定位：${modelStatusLabel(modelStatus?.detector)}`, `物种判断：${modelStatusLabel(modelStatus?.classifier)}`, "输出口径：候选识别与人工复核"]} />
      </section>
    </>
  );
}

function RecordReportRow({
  item,
  speciesKnowledge,
  isCopied,
  onCopy,
  onOpen,
  onOpenDetail,
  pdfWeakReferenceSpecies,
  openSetReferenceSpecies,
}: {
  item: AnalysisResponse;
  speciesKnowledge: SpeciesEntry[];
  isCopied: boolean;
  onCopy: (item: AnalysisResponse) => void;
  onOpen: (item: AnalysisResponse) => void;
  onOpenDetail: (entry: KnowledgeEntry) => void;
  pdfWeakReferenceSpecies: ReferenceSpecies[];
  openSetReferenceSpecies: ReferenceSpecies[];
}) {
  const firstDetection = item.detections[0];
  const mappedKnowledge = getKnowledge(item, speciesKnowledge);
  const mappedSpecies = findSpeciesForKnowledgeEntry(mappedKnowledge, speciesKnowledge);
  const mappedReference = mappedSpecies ? findReferenceForSpecies(mappedSpecies, [...pdfWeakReferenceSpecies, ...openSetReferenceSpecies]) : null;
  const mappedLabel = firstDetection ? formatRecognitionConclusion(mappedKnowledge, firstDetection) : "未发现目标";
  const rawLabel = firstDetection?.species_label;
  const averageConfidence = averageRecordConfidence(item);
  const status = summarizeReviewStatus(item.detections);
  const speciesSummary = Object.entries(item.species_summary)
    .slice(0, 3)
    .map(([label, count]) => `${label} x${count}`)
    .join(" / ");

  return (
    <article className="record-report-row">
      <div className="record-main">
        <span className="eyebrow">{item.media_type === "video" ? "视频识别报告" : "图片识别报告"}</span>
        <strong>{mappedLabel}</strong>
        <p>{rawLabel && !sameNormalizedLabel(rawLabel, mappedKnowledge.title) ? `初始候选：${rawLabel}` : speciesSummary || item.message}</p>
        {firstDetection ? <p>学术名：{mappedKnowledge.latin}；复核状态：{status}</p> : null}
        {mappedReference ? <p>关联图鉴：{mappedReference.folder_name}，{mappedReference.image_count} 张参考图</p> : null}
      </div>
      <div className="record-side">
        <div className="record-metrics">
          <InfoChip label="目标数" value={`${item.detections.length}`} />
          <InfoChip label="平均置信度" value={item.detections.length ? formatPercent(averageConfidence) : "--"} />
          <InfoChip label="复核状态" value={status} />
        </div>
        <div className="record-actions">
          <button className="secondary-action" onClick={() => onOpen(item)}>打开报告</button>
          {mappedKnowledge.title !== "未知动物" ? (
            <button className="secondary-action" onClick={() => onOpenDetail(mappedKnowledge)}>
              <BookOpen size={16} />
              <span>物种详情</span>
            </button>
          ) : null}
          <button className="secondary-action" onClick={() => onCopy(item)}>
            {isCopied ? <Check size={16} /> : <Copy size={16} />}
            {isCopied ? "已复制" : "复制摘要"}
          </button>
        </div>
      </div>
    </article>
  );
}

function SystemPage({ modelStatus }: { modelStatus?: Record<string, string> }) {
  return (
    <>
      <PageHeader
        eyebrow="系统说明"
        title="统一产品说明"
        subtitle="四个入口共享同一套物种详情、图鉴参考和复核口径。"
      />
      <section className="system-grid">
        <InfoBlock title="统一入口" items={["识别页：结果、候选和参考图", "知识库：分类、习性和详情图", "图谱：关系结构与节点详情", "记录：历史结果和复核回看"]} />
        <InfoBlock title="展示口径" items={["高置信且证据一致的结果可直接展示", "图鉴参考用于解释和复核，不冒充最终结论", "低置信度或类外目标保持未知或待复核", "植物先做知识库，不混入动物识别口径"]} />
        <InfoBlock title="维护材料" items={["模型评估报告与错例图", "持续补充验证图片", "知识库字段与保护等级资料", "稳定验证图片和短视频"]} />
        <InfoBlock title="识别能力" items={[`目标定位：${modelStatusLabel(modelStatus?.detector)}`, `物种判断：${modelStatusLabel(modelStatus?.classifier)}`, "输出口径：候选结论、置信度与复核建议"]} />
      </section>
      <section className="roadmap-section">
        <div className="section-head">
          <div>
            <span className="eyebrow">维护路线</span>
            <h3>当前维护重点与扩展方向</h3>
          </div>
          <p>这部分用于说明系统维护重点和扩展方向。</p>
        </div>
        <section className="roadmap-grid">
          {ROADMAP_STEPS.map((step) => (
            <article key={step.phase} className="roadmap-card">
              <span>{step.phase}</span>
              <h4>{step.title}</h4>
              <ul>{step.points.map((point) => <li key={point}>{point}</li>)}</ul>
            </article>
          ))}
        </section>
      </section>
    </>
  );
}

function PageHeader({ eyebrow, title, subtitle }: { eyebrow: string; title: string; subtitle: string }) {
  return (
    <header className="page-header">
      <span>{eyebrow}</span>
      <h2>{title}</h2>
      <p>{subtitle}</p>
    </header>
  );
}

function RuntimeStatusStrip({ health }: { health: HealthResponse | null }) {
  const models = health?.models ?? {};
  const mode = runtimeModeLabel(models);
  return (
    <section className="runtime-strip">
      <div className={`runtime-mode ${mode.className}`}>
        <ShieldCheck size={18} />
        <div>
          <span>当前运行模式</span>
          <strong>{mode.label}</strong>
        </div>
      </div>
      <div className="runtime-item">
        <span>目标检测</span>
        <strong>{modelStatusLabel(models.detector)}</strong>
      </div>
      <div className="runtime-item">
        <span>物种分类</span>
        <strong>{modelStatusLabel(models.classifier)}</strong>
      </div>
      <div className="runtime-item">
        <span>参考检索</span>
        <strong>{retrievalStatusLabel(models.reference_retrieval)}</strong>
      </div>
      <div className="runtime-item">
        <span>生态助手</span>
        <strong>{assistantStatusLabel(health?.assistant)}</strong>
      </div>
    </section>
  );
}

function UploadPanel({
  file,
  hasResult,
  isLoading,
  onFile,
  onAnalyze,
  onClear,
}: {
  file: File | null;
  hasResult: boolean;
  isLoading: boolean;
  onFile: (file: File | null) => void;
  onAnalyze: () => void;
  onClear: () => void;
}) {
  return (
    <section className="card">
      <div className="card-title">
        <ImageUp size={18} />
        <span>素材上传</span>
      </div>
      <div className="mobile-capture-actions">
        <label className="mobile-capture-action primary-capture">
          <Camera size={20} />
          <span>拍照识别</span>
          <input type="file" accept="image/*" capture="environment" onChange={(event) => onFile(event.target.files?.[0] ?? null)} />
        </label>
        <label className="mobile-capture-action">
          <ImageUp size={20} />
          <span>从相册选择</span>
          <input type="file" accept="image/*,video/*" onChange={(event) => onFile(event.target.files?.[0] ?? null)} />
        </label>
      </div>
      <label className="dropzone">
        <UploadCloud size={34} />
        <strong>{file ? file.name : "选择图片或视频"}</strong>
        <span>支持 camera-trap 图片、短视频片段</span>
        <input type="file" accept="image/*,video/*" onChange={(event) => onFile(event.target.files?.[0] ?? null)} />
      </label>
      <button className="primary" type="button" disabled={!file || isLoading} onClick={onAnalyze}>
        {isLoading ? <Loader2 className="spin" size={18} /> : <Activity size={18} />}
        <span>{isLoading ? "分析中..." : "开始识别"}</span>
      </button>
      <button className="secondary-action upload-clear-action" type="button" disabled={isLoading || (!file && !hasResult)} onClick={onClear}>
        <Trash2 size={16} />
        <span>清空当前任务</span>
      </button>
    </section>
  );
}

function SettingsPanel(props: {
  confidence: number;
  frameInterval: number;
  includeLowConfidence: boolean;
  setConfidence: (value: number) => void;
  setFrameInterval: (value: number) => void;
  setIncludeLowConfidence: (value: boolean) => void;
}) {
  return (
    <section className="card">
      <div className="card-title">
        <Settings2 size={18} />
        <span>参数设置</span>
      </div>
      <label className="control light">
        <span>置信度阈值 {props.confidence.toFixed(2)}</span>
        <input min="0" max="0.95" step="0.05" type="range" value={props.confidence} onChange={(event) => props.setConfidence(Number(event.target.value))} />
      </label>
      <label className="control light">
        <span>视频抽帧间隔 {props.frameInterval.toFixed(1)}s</span>
        <input min="0.5" max="5" step="0.5" type="range" value={props.frameInterval} onChange={(event) => props.setFrameInterval(Number(event.target.value))} />
      </label>
      <label className="toggle light">
        <input type="checkbox" checked={props.includeLowConfidence} onChange={(event) => props.setIncludeLowConfidence(event.target.checked)} />
        <span>显示低置信度结果</span>
      </label>
    </section>
  );
}

function PreviewPanel({ file, previewSource }: { file: File | null; previewSource: string | null }) {
  return (
    <section className="preview-panel">
      {previewSource ? (
        file?.type.startsWith("video/") ? (
          <video src={previewSource} controls />
        ) : (
          <div className="preview-image" role="img" aria-label="识别预览" style={{ backgroundImage: `url("${previewSource}")` }} />
        )
      ) : (
        <EmptyState icon={<FileVideo size={48} />} text="上传素材后这里显示识别预览" />
      )}
    </section>
  );
}

function ResultDetailsPanel({
  result,
  error,
  speciesKnowledge,
  onOpenDetail,
}: {
  result: AnalysisResponse | null;
  error: string | null;
  speciesKnowledge: SpeciesEntry[];
  onOpenDetail: (entry: KnowledgeEntry) => void;
}) {
  const detections = result?.detections ?? [];
  const visibleDetections = detections.slice(0, 3);
  const topConfidence = detections.reduce((max, item) => Math.max(max, item.confidence ?? 0), 0);

  return (
    <section className="card result-details-card">
      <div className="card-title result-details-title">
        <div className="card-title-main">
          <Database size={18} />
          <span>{result ? "检测明细" : "等待上传识别"}</span>
        </div>
        {result ? <span className="result-details-count">{detections.length} 条</span> : null}
      </div>
      {error ? <p className="error">{error}</p> : null}
      {result ? (
        <>
          <div className="result-summary-grid">
            <div className="result-summary-card">
              <span>检测条数</span>
              <strong>{detections.length}</strong>
            </div>
            <div className="result-summary-card">
              <span>最高置信度</span>
              <strong>{detections.length ? formatPercent(topConfidence) : "-"}</strong>
            </div>
            <div className="result-summary-card">
              <span>识别状态</span>
              <strong>{detections.length ? "已生成" : "暂无结果"}</strong>
            </div>
          </div>

          {visibleDetections.length ? (
            <div className="result-mini-list">
              {visibleDetections.map((item, index) => {
                const entry = getKnowledge({ ...result, detections: [item] }, speciesKnowledge);
                const displayLabel = formatRecognitionConclusion(entry, item);
                return (
                  <div className="result-mini-item" key={`${item.media_id}-${index}`}>
                    <img className="crop" src={`${API_BASE}${item.preview_crop_path}`} alt={displayLabel} />
                    <div className="result-mini-body">
                      <strong>{displayLabel}</strong>
                      <span>{item.detected_type} · {item.frame_time.toFixed(2)}s · {Math.round(item.confidence * 100)}%</span>
                      <em>{formatReviewCell(item)}</em>
                      {entry.title !== "未知动物" ? (
                        <button className="secondary-action compact-action result-detail-inline-action" type="button" onClick={() => onOpenDetail(entry)}>
                          <BookOpen size={14} />
                          <span>详情</span>
                        </button>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState icon={<Database size={44} />} text="当前阈值下没有保留下来的结果" />
          )}

          <details className="result-detail-toggle">
            <summary>
              <span>查看全部检测框与候选数据</span>
              <strong>{detections.length ? `${detections.length} 条` : "0 条"}</strong>
            </summary>
            <div className="table-wrap result-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>截图</th>
                    <th>分类结果</th>
                    <th>候选物种</th>
                    <th>检索</th>
                    <th>类型</th>
                    <th>时间</th>
                    <th>检测</th>
                    <th>分类</th>
                    <th>综合</th>
                    <th>复核</th>
                    <th>位置</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {detections.map((item, index) => {
                    const entry = getKnowledge({ ...result, detections: [item] }, speciesKnowledge);
                    const displayLabel = formatRecognitionConclusion(entry, item);

                    return (
                      <tr key={`${item.media_id}-${index}`}>
                        <td>
                          <img className="crop" src={`${API_BASE}${item.preview_crop_path}`} alt={displayLabel} />
                        </td>
                        <td>{displayLabel}</td>
                        <td>{formatCandidates(item.top_candidates, true)}</td>
                        <td>{item.retrieval_confidence ? formatPercent(item.retrieval_confidence) : "-"}</td>
                        <td>{item.detected_type}</td>
                        <td>{item.frame_time.toFixed(2)}s</td>
                        <td>{formatPercent(item.detection_confidence ?? item.confidence)}</td>
                        <td>{formatPercent(item.classification_confidence ?? item.confidence)}</td>
                        <td>{Math.round(item.confidence * 100)}%</td>
                        <td>{formatReviewCell(item)}</td>
                        <td>
                          {item.bbox.x},{item.bbox.y},{item.bbox.width}x{item.bbox.height}
                        </td>
                        <td>
                          {entry.title !== "未知动物" ? (
                            <button className="secondary-action compact-action result-table-action" type="button" onClick={() => onOpenDetail(entry)}>
                              详情
                            </button>
                          ) : (
                            <span className="muted">-</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                  {detections.length === 0 ? (
                    <tr>
                      <td colSpan={12} className="muted">
                        当前阈值下没有保留下来的结果
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </details>
        </>
      ) : (
        <EmptyState icon={<Database size={44} />} text="上传素材后这里会显示识别明细" />
      )}
    </section>
  );
}

function ResultTable({ result, error, speciesKnowledge }: { result: AnalysisResponse | null; error: string | null; speciesKnowledge: SpeciesEntry[] }) {
  return (
    <section className="card">
      <div className="card-title">
        <Database size={18} />
        <span>{result ? "检测明细" : "等待上传识别"}</span>
      </div>
      {error ? <p className="error">{error}</p> : null}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>截图</th>
              <th>分类结果</th>
              <th>Top候选</th>
              <th>检索</th>
              <th>类型</th>
              <th>时间</th>
              <th>检测</th>
              <th>分类</th>
              <th>综合</th>
              <th>复核</th>
              <th>位置</th>
            </tr>
          </thead>
          <tbody>
            {result?.detections.map((item, index) => {
              const entry = getKnowledge({ ...result, detections: [item] }, speciesKnowledge);
              const displayLabel = formatRecognitionConclusion(entry, item);

              return (
                <tr key={`${item.media_id}-${index}`}>
                  <td>
                    <img className="crop" src={`${API_BASE}${item.preview_crop_path}`} alt={displayLabel} />
                  </td>
                  <td>{displayLabel}</td>
                  <td>{formatCandidates(item.top_candidates, true)}</td>
                  <td>{item.retrieval_confidence ? formatPercent(item.retrieval_confidence) : "-"}</td>
                  <td>{item.detected_type}</td>
                  <td>{item.frame_time.toFixed(2)}s</td>
                  <td>{formatPercent(item.detection_confidence ?? item.confidence)}</td>
                  <td>{formatPercent(item.classification_confidence ?? item.confidence)}</td>
                  <td>{Math.round(item.confidence * 100)}%</td>
                  <td>{formatReviewCell(item)}</td>
                  <td>
                    {item.bbox.x},{item.bbox.y},{item.bbox.width}x{item.bbox.height}
                  </td>
                </tr>
              );
            }) ?? null}
            {result && result.detections.length === 0 ? (
              <tr>
                <td colSpan={11} className="muted">
                  当前阈值下没有保留下来结果
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SpeciesReportCard({
  result,
  entry,
  reference,
  canOpenDetail = false,
  onOpenDetail,
}: {
  result: AnalysisResponse | null;
  entry: KnowledgeEntry;
  reference: ReferenceSpecies | null;
  canOpenDetail?: boolean;
  onOpenDetail?: () => void;
}) {
  const detection = result?.detections[0];
  const confidence = detection?.confidence ?? 0;
  const reviewLevel = getReviewLevel(confidence);
  const candidateLabels = displayableCandidates(detection?.top_candidates).slice(0, 3);
  const reviewReasons = detection ? visibleReviewReasons(detection).slice(0, 3) : [];
  const secondaryCandidates = displayableCandidates(detection?.top_candidates).slice(3, 6);
  const reportTitle = detection ? formatRecognitionConclusion(entry, detection) : "等待识别结果";
  const resultLayer = detection ? recognitionResultLayer(entry, detection) : null;

  return (
    <section className="species-report-card">
      <div className="report-heading">
        <div>
          <span className="eyebrow">物种识别报告</span>
          <h3>{reportTitle}</h3>
          <p className="latin">
            {detection
              ? resultLayer?.kind === "direct"
                ? entry.latin
                : `候选参考 · ${entry.latin}`
              : "上传素材并开始识别后生成报告卡"}
          </p>
        </div>
        <div className={`report-score ${resultLayer?.className ?? reviewLevel.className}`}>
          <strong>{detection ? formatPercent(confidence) : "--"}</strong>
          <span>{resultLayer?.label ?? reviewLevel.label}</span>
        </div>
      </div>

      <div className={`report-decision-band ${resultLayer?.className ?? reviewLevel.className}`}>
        <strong>{resultLayer?.label ?? reviewLevel.label}</strong>
        <p>{resultLayer?.note ?? reviewLevel.note}</p>
      </div>

      <div className="report-compact-grid">
        <div className="report-primary">
          <div className="report-chips">
            <InfoChip label="保护等级" value={entry.protectionLevel ?? "未标注"} />
            <InfoChip label="分类地位" value={entry.category ? formatTaxonomy(entry) : "暂无分类资料"} />
            <InfoChip label="识别范围" value={recognitionScopeLabel(entry.recognitionTier)} />
            <InfoChip label="复核状态" value={detection ? reviewStatusLabel(detection.review_status) : "待识别"} />
          </div>
          <section className="report-panel">
            <h4>关键特征</h4>
            <ul>{entry.features.slice(0, 4).map((feature) => <li key={feature}>{feature}</li>)}</ul>
          </section>
        </div>

        <div className="report-secondary">
          <section className="report-panel">
            <h4>候选物种</h4>
            <div className="candidate-strip">
              {candidateLabels.length ? candidateLabels.map((candidate) => (
                <span key={`${candidate.label}-${candidate.confidence}`} title={[formatCandidateSource(candidate.source), candidate.evidence].filter(Boolean).join("：") || undefined}>
                  {candidate.label} {formatPercent(candidate.confidence)}
                </span>
              )) : <span>暂无可靠候选</span>}
            </div>
            {secondaryCandidates.length ? (
              <p className="report-muted">更多候选：{secondaryCandidates.map((candidate) => candidate.label).join("、")}</p>
            ) : null}
            {detection ? <p className="report-muted">综合置信度 {formatPercent(confidence)}，{reviewLevel.label}</p> : null}
          </section>
          <section className="report-panel">
            <h4>复核建议</h4>
            <p>{entry.reviewTips ?? reviewLevel.note}</p>
            {reviewReasons.length ? <p className="report-muted">触发原因：{reviewReasons.map(reviewReasonLabel).join("、")}</p> : null}
            {entry.similarSpecies?.length ? <p className="report-muted">相似物种：{entry.similarSpecies.slice(0, 4).join("、")}</p> : null}
          </section>
          <RecognitionReferenceCard reference={reference} resultLayer={resultLayer} />
        </div>
      </div>

      <details className="report-more">
        <summary>更多信息</summary>
        <div className="report-more-grid">
          <section>
            <h4>习性与食性</h4>
            <p>{entry.habits ?? "暂无习性资料。"}</p>
            <p>{entry.diet ?? "暂无食性资料。"}</p>
          </section>
          <section>
            <h4>参考图</h4>
            {reference?.samples.length ? (
              <div className="report-reference">
                {reference.samples.slice(0, 3).map((sample) => (
                  <img key={sample.file_name} src={`${API_BASE}${sample.file_url}`} alt={sample.file_name} />
                ))}
              </div>
            ) : (
              <p className="report-muted">暂无参考图。</p>
            )}
          </section>
          <section>
            <h4>复核信息</h4>
            <p>结果来源：{detection ? formatReviewCell(detection) : "等待识别"}</p>
            <p>展示状态：{detection ? reviewStatusLabel(detection.review_status) : "待识别"}</p>
            <p>识别分层：{recognitionTierLabel(entry.recognitionTier)}</p>
          </section>
        </div>
      </details>
      {canOpenDetail ? (
        <button className="secondary-action report-detail-action" type="button" onClick={onOpenDetail}>
          <BookOpen size={16} />
          <span>打开物种图文详情</span>
        </button>
      ) : null}
    </section>
  );
}

function RecognitionReferenceCard({
  reference,
  resultLayer,
}: {
  reference: ReferenceSpecies | null;
  resultLayer: { label: string; note: string; className: string; kind: "direct" | "reference" | "unknown" } | null;
}) {
  const sample = reference?.samples[0];
  if (!reference || !sample) return null;

  return (
    <section className="result-reference-card">
      <div className="result-reference-cover">
        {reference.cover_url ? <img src={`${API_BASE}${reference.cover_url}`} alt={reference.folder_name} /> : <div className="result-reference-empty" />}
      </div>
      <div className="result-reference-body">
        <div className="result-reference-head">
          <span className="eyebrow">图鉴参考</span>
          <strong>{reference.folder_name}</strong>
          <p className="latin">{sample.scientific_name ?? sample.subspecies ?? "暂无学名资料"}</p>
        </div>
        <div className="tag-row">
          {sample.cn_name ? <span>{sample.cn_name}</span> : null}
          {sample.protection_level ? <span>{sample.protection_level}</span> : null}
          {sample.taxon_group ? <span>{sample.taxon_group}</span> : null}
          <span>{reference.image_count} 张参考图</span>
        </div>
        <p className="report-muted">
          {resultLayer?.kind === "direct"
            ? "当前结果已进入精识别层，这里保留图鉴作为复核佐证。"
            : resultLayer?.kind === "reference"
              ? "当前结果停留在图鉴参考层，可继续对照大图、学名和习性信息核验。"
              : "当前结果尚未形成稳定候选，图鉴仅作为补充参考。"}
        </p>
      </div>
    </section>
  );
}

function InfoChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="info-chip">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ResultInsight({ result, speciesKnowledge }: { result: AnalysisResponse | null; speciesKnowledge: SpeciesEntry[] }) {
  const detection = result?.detections[0];
  const confidence = detection?.confidence ?? 0;
  const reviewLevel = getReviewLevel(confidence);
  const knowledge = getKnowledge(result, speciesKnowledge);
  const isUnknown = knowledge.title === "未知动物";
  const resultLayer = detection ? recognitionResultLayer(knowledge, detection) : null;
  const mappedLabel = detection ? formatRecognitionConclusion(knowledge, detection) : "未开始分析";
  const rawLabel = detection?.species_label;
  const hasMappedLabel = Boolean(detection?.review_status === "ready" && rawLabel && !sameNormalizedLabel(rawLabel, knowledge.title));

  return (
    <section className="card insight-card">
      <div className="card-title">
        <ShieldCheck size={18} />
        <span>结果解读</span>
      </div>
      <div className="insight-main">
        <strong>{mappedLabel}</strong>
        <span>{detection ? `${Math.round(confidence * 100)}% 综合置信度` : "上传素材后会显示候选结果"}</span>
        {hasMappedLabel ? <span>初始候选：{rawLabel}</span> : null}
      </div>
      <div className="pill-row">
        {resultLayer ? <span className={`pill ${resultLayer.className}`}>{resultLayer.label}</span> : null}
        <span className={`pill ${reviewLevel.className}`}>{reviewLevel.label}</span>
        <span className="pill neutral">目标数 {result?.detections.length ?? 0}</span>
        {!isUnknown && knowledge.protectionLevel ? <span className="pill neutral">{knowledge.protectionLevel}</span> : null}
      </div>
      {detection?.top_candidates?.length ? (
        <div className="pill-row">
          {displayableCandidates(detection.top_candidates).slice(0, 3).map((candidate) => (
            <span className={`pill ${candidatePillClass(candidate)}`} key={`${candidate.label}-${candidate.confidence}`}>
              {candidate.label} {formatPercent(candidate.confidence)} · {regionStatusLabel(candidate.region_status)}
            </span>
          ))}
          {!displayableCandidates(detection.top_candidates).length ? <span className="pill neutral">暂无可靠候选</span> : null}
        </div>
      ) : null}
      <div className="insight-detail">
        <p>{resultLayer?.note ?? reviewLevel.note}</p>
        {detection && visibleReviewReasons(detection).length ? <p>复核触发：{visibleReviewReasons(detection).map(reviewReasonLabel).join("、")}</p> : null}
        {!isUnknown && knowledge.reviewTips ? <p>复核建议：{knowledge.reviewTips}</p> : null}
        {!isUnknown && knowledge.similarSpecies?.length ? <p>相似物种：{knowledge.similarSpecies.slice(0, 3).join("、")}</p> : null}
      </div>
    </section>
  );
}

function SessionSummary({ result, file }: { result: AnalysisResponse | null; file: File | null }) {
  return (
    <section className="card">
      <div className="card-title">
        <Database size={18} />
        <span>会话摘要</span>
      </div>
      <SideRow label="输入" value={file?.name ?? "未选择"} />
      <SideRow label="目标数" value={String(result?.detections.length ?? 0)} />
      <SideRow label="目标定位" value={result ? modelStatusLabel(result.model_status?.detector) : "待分析"} />
      <SideRow label="物种判断" value={result ? modelStatusLabel(result.model_status?.classifier) : "待分析"} />
    </section>
  );
}

function ModuleCard({ icon, title, text, action, onClick }: { icon: React.ReactNode; title: string; text: string; action: string; onClick: () => void }) {
  return (
    <article className="module-card">
      {icon}
      <h3>{title}</h3>
      <p>{text}</p>
      <button onClick={onClick}>{action}</button>
    </article>
  );
}

function MetricCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{hint}</p>
    </article>
  );
}

function InfoBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="card">
      <h3>{title}</h3>
      <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
    </section>
  );
}

function EmptyState({ text, icon }: { text: string; icon?: React.ReactNode }) {
  return (
    <div className="empty">
      {icon ?? <BookOpen size={44} />}
      <span>{text}</span>
    </div>
  );
}

function LoadMoreControl({
  visible,
  total,
  label,
  step,
  onLoadMore,
}: {
  visible: number;
  total: number;
  label: string;
  step: number;
  onLoadMore: () => void;
}) {
  if (visible >= total) return null;
  return (
    <div className="load-more-row">
      <span>{`当前显示 ${visible} / ${total} 项`}</span>
      <button className="secondary-action compact-action" type="button" onClick={onLoadMore}>
        <span>{`再加载 ${Math.min(step, total - visible)} 个${label}`}</span>
      </button>
    </div>
  );
}

function SideRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="side-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function KnowledgeCard({ entry, onOpen }: { entry: KnowledgeEntry; onOpen: () => void }) {
  const visibleTags = entry.tags.slice(0, 3);
  const hiddenTags = entry.tags.slice(3);
  const primaryFeatures = entry.features.slice(0, 2);
  const summary = entry.habitat || entry.monitoringValue || catalogFallbackSummary(entry);

  return (
    <article
      className="knowledge-card interactive-card"
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      {entry.imageUrl ? <div className="knowledge-card-image"><img src={entry.imageUrl} alt={`${entry.title}植物照片`} loading="lazy" /></div> : null}
      <div className="knowledge-card-head">
        <div>
          <h3>{entry.title}</h3>
          <p className="latin">{entry.latin}</p>
        </div>
        {entry.protectionLevel ? <span className="protection-badge">{entry.protectionLevel.replace("国家", "")}</span> : null}
      </div>
      <div className="knowledge-meta">
        {entry.category ? <span>{formatTaxonomy(entry)}</span> : null}
      </div>
      <div className="tag-row">
        {visibleTags.map((tag) => <span key={tag}>{tag}</span>)}
        {hiddenTags.length ? <span>+{hiddenTags.length}</span> : null}
      </div>
      <p className="knowledge-habitat">{summary}</p>
      {primaryFeatures.length ? <ul className="feature-list compact">{primaryFeatures.map((feature) => <li key={feature}>{feature}</li>)}</ul> : null}
      <span className="knowledge-card-more">查看详情</span>
    </article>
  );
}

function catalogFallbackSummary(entry: KnowledgeEntry): string {
  const taxonomy = [entry.taxonGroup, entry.order, entry.family, entry.genus].filter(Boolean).join(" / ");
  const protection = entry.protectionLevel ? `，${entry.protectionLevel}` : "";
  if (taxonomy) {
    return `${entry.title}属于${taxonomy}${protection}。`;
  }
  if (entry.protectionLevel) {
    return `${entry.title}为${entry.protectionLevel}收录物种。`;
  }
  return `${entry.title}已收录基础分类信息，详细形态和生境资料待补充。`;
}

function FocusSpeciesCard({ entry, onOpen }: { entry: KnowledgeEntry; onOpen: () => void }) {
  return (
    <article
      className="focus-species-card interactive-card"
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      <div>
        <span className="eyebrow">{recognitionTierLabel(entry.recognitionTier)}</span>
        <h3>{entry.title}</h3>
        <p className="latin">{entry.latin}</p>
      </div>
      <div className="pill-row">
        {entry.protectionLevel ? <span className="pill neutral">{entry.protectionLevel}</span> : null}
        {entry.family ? <span className="pill neutral">{entry.family}</span> : null}
      </div>
      <p>{entry.features.slice(0, 2).join("；")}</p>
    </article>
  );
}

function PdfWeakReferenceCard({ entry, onOpen }: { entry: ReferenceSpecies; onOpen: () => void }) {
  const sample = entry.samples[0];
  const latin = sample?.scientific_name ?? sample?.subspecies ?? "暂无学名资料";
  const metaTags = [sample?.taxon_group, sample?.protection_level].filter(Boolean) as string[];
  return (
    <article
      className="pdf-reference-card"
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      {entry.cover_url ? <img src={`${API_BASE}${entry.cover_url}`} alt={entry.folder_name} /> : <div className="pdf-reference-empty" />}
      <div>
        <div className="pdf-reference-title">
          <h4>{entry.folder_name}</h4>
          <span>图鉴</span>
        </div>
        <p className="latin">{latin}</p>
        {metaTags.length ? (
          <div className="pdf-reference-tags">
            {metaTags.slice(0, 2).map((tag) => <span key={tag}>{tag}</span>)}
          </div>
        ) : null}
      </div>
    </article>
  );
}

function KnowledgeDetailModal({
  entry,
  animalSpecies,
  pdfWeakReferenceSpecies,
  openSetReferenceSpecies,
  onClose,
}: {
  entry: KnowledgeEntry;
  animalSpecies: SpeciesEntry[];
  pdfWeakReferenceSpecies: ReferenceSpecies[];
  openSetReferenceSpecies: ReferenceSpecies[];
  onClose: () => void;
}) {
  const isPlant = entry.category === "plant";
  const detailRows = [
    ["分类地位", formatTaxonomy(entry)],
    ["保护等级", entry.protectionLevel],
    ...(isPlant ? [["生活型", entry.lifeForm], ["广西分布", entry.distribution]] : []),
  ].filter(([, value]) => Boolean(value));
  const species = findSpeciesForKnowledgeEntry(entry, animalSpecies);
  const reference = species ? findReferenceForSpecies(species, [...pdfWeakReferenceSpecies, ...openSetReferenceSpecies]) : null;
  const referenceSample = reference?.samples[0];

  return (
    <div className="guide-modal-backdrop" role="dialog" aria-modal="true" aria-label={`${entry.title}知识详情`} onClick={onClose}>
      <article className="guide-modal knowledge-modal" onClick={(event) => event.stopPropagation()}>
        <button className="icon-close" type="button" onClick={onClose} aria-label="关闭知识详情">
          <X size={18} />
        </button>
        {isPlant && entry.imageUrl ? <div className="knowledge-plant-hero"><img src={entry.imageUrl} alt={`${entry.title}植物照片`} />{(entry.imageAuthor || entry.imageLicense) ? <span>{[entry.imageAuthor, entry.imageLicense].filter(Boolean).join(" · ")}</span> : null}</div> : null}
        {reference ? (
          <div className="knowledge-reference-panel">
            <div className="knowledge-reference-hero">
              {reference.cover_url ? <img src={`${API_BASE}${reference.cover_url}`} alt={reference.folder_name} /> : <div className="result-reference-empty" />}
            </div>
            <div className="knowledge-reference-meta">
              <span className="eyebrow">关联图鉴</span>
              <strong>{reference.folder_name}</strong>
              <p className="latin">{referenceSample?.scientific_name ?? referenceSample?.subspecies ?? entry.latin}</p>
              <div className="tag-row">
                {referenceSample?.cn_name ? <span>{referenceSample.cn_name}</span> : null}
                {referenceSample?.taxon_group ? <span>{referenceSample.taxon_group}</span> : null}
                <span>{reference.image_count} 张</span>
              </div>
            </div>
          </div>
        ) : null}
        <div className="guide-detail-panel knowledge-detail-panel">
          <span className="eyebrow">知识详情</span>
          <h2>{entry.title}</h2>
          <p className="latin">{entry.latin}</p>
          {detailRows.length ? (
            <div className="knowledge-detail-summary">
              {detailRows.slice(0, 4).map(([label, value]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          ) : null}
          <div className="tag-row">
            {entry.tags.map((tag) => <span key={tag}>{tag}</span>)}
          </div>
          <section className="guide-section">
            <h3>基础信息</h3>
            <p>{entry.habitat}</p>
            {entry.habits ? <p>{isPlant ? "生长特性" : "习性"}：{entry.habits}</p> : null}
            {isPlant && entry.phenology ? <p>花果期：{entry.phenology}</p> : null}
            {!isPlant && entry.diet ? <p>食性：{entry.diet}</p> : null}
          </section>
          <section className="guide-section">
            <h3>识别特征</h3>
            <ul>{entry.features.map((feature) => <li key={feature}>{feature}</li>)}</ul>
          </section>
          {isPlant && (entry.monitoringValue || entry.reviewTips) ? (
            <section className="guide-section">
              <h3>保护与记录</h3>
              {entry.monitoringValue ? <p>{entry.monitoringValue}</p> : null}
              {entry.reviewTips ? <p>现场记录提示：{entry.reviewTips}</p> : null}
            </section>
          ) : null}
          {entry.sourceUrls?.length ? (
            <section className="guide-section knowledge-source-section">
              <h3>资料来源</h3>
              <div className="knowledge-source-links">
                {entry.sourceUrls.map((url, index) => (
                  <a key={url} href={url} target="_blank" rel="noreferrer">
                    {formatSourceLabel(url, index)}
                  </a>
                ))}
              </div>
              <p className="knowledge-source-note">保护等级与物种资料用于科普和现场辅助记录，正式调查结论仍应结合最新名录、标本或专家复核。</p>
            </section>
          ) : null}
          {isPlant && entry.imageSourceUrl ? <a className="plant-image-source" href={entry.imageSourceUrl} target="_blank" rel="noreferrer">查看图片原始记录与授权信息</a> : null}
        </div>
      </article>
    </div>
  );
}

function SpeciesGuideModal({ entry, species, onClose }: { entry: ReferenceSpecies; species?: SpeciesEntry; onClose: () => void }) {
  const sample = entry.samples[0];
  const knowledge = species ? speciesToKnowledgeEntry(species) : getSupplementalReferenceKnowledge(entry);
  const latin = species?.latin_name ?? sample?.scientific_name ?? sample?.subspecies ?? "暂无学名资料";
  const imageUrl = entry.cover_url ? `${API_BASE}${entry.cover_url}` : null;
  const tags = [
    species?.taxon_group ?? sample?.taxon_group,
    species?.family,
  ].filter(Boolean) as string[];

  return (
    <div className="guide-modal-backdrop" role="dialog" aria-modal="true" aria-label={`${entry.folder_name}图鉴详情`} onClick={onClose}>
      <article className="guide-modal" onClick={(event) => event.stopPropagation()}>
        <button className="icon-close" type="button" onClick={onClose} aria-label="关闭图鉴详情">
          <X size={18} />
        </button>
        <div className="guide-image-panel">
          {imageUrl ? <img src={imageUrl} alt={entry.folder_name} /> : <div className="pdf-reference-empty" />}
        </div>
        <div className="guide-detail-panel">
          <span className="eyebrow">物种图鉴</span>
          <h2>{entry.folder_name}</h2>
          <p className="latin">{latin}</p>
          <div className="guide-detail-summary">
            <div>
              <span>图鉴图片</span>
              <strong>{entry.image_count} 张</strong>
            </div>
            <div>
              <span>条目标识</span>
              <strong>{sample?.cn_name ?? entry.folder_name}</strong>
            </div>
            <div>
              <span>配套学名</span>
              <strong>{latin}</strong>
            </div>
          </div>
          {tags.length ? <div className="tag-row">{tags.map((tag) => <span key={tag}>{tag}</span>)}</div> : null}
          <ReferenceMetadataGrid sample={sample} />
          {knowledge ? (
            <>
              <GuideInfoGrid entry={knowledge} />
              <section className="guide-section">
                <h3>生境与习性</h3>
                <p>{knowledge.habitat || "暂无生境资料。"}</p>
                {knowledge.habits ? <p>习性：{knowledge.habits}</p> : null}
                {knowledge.diet ? <p>食性：{knowledge.diet}</p> : null}
              </section>
              {knowledge.features.length ? (
                <section className="guide-section">
                  <h3>识别特征</h3>
                  <ul>{knowledge.features.map((feature) => <li key={feature}>{feature}</li>)}</ul>
                </section>
              ) : null}
            </>
          ) : (
            <section className="guide-section">
              <h3>图鉴说明</h3>
              <p>{sample?.note ?? "当前条目已收录图鉴图片和学名，可用于物种浏览、查询和识别结果对照。"}</p>
            </section>
          )}
        </div>
      </article>
    </div>
  );
}

function GuideInfoGrid({ entry }: { entry: KnowledgeEntry }) {
  const rows = [
    ["分类地位", formatTaxonomy(entry)],
    ["保护等级", entry.protectionLevel],
  ].filter(([, value]) => Boolean(value));

  return (
    <section className="guide-info-grid">
      {rows.map(([label, value]) => (
        <div key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </section>
  );
}

function getSupplementalReferenceKnowledge(entry: ReferenceSpecies): KnowledgeEntry | null {
  const latin = entry.samples[0]?.subspecies ?? "";
  const supplemental: Record<string, KnowledgeEntry> = {
    果子狸: {
      title: "果子狸",
      latin: latin || "Paguma larvata",
      category: "animal",
      taxonGroup: "兽类",
      family: "灵猫科",
      genus: "果子狸属",
      recognitionTier: "knowledge_reference",
      protectionLevel: "相似物种参考",
      tags: ["兽类", "灵猫科", "相似物种"],
      habitat: "常见于森林、灌丛、林缘和村落附近的树栖或半树栖环境。",
      habits: "多在夜间活动，善攀爬，常沿树枝、林缘或道路边缘取食活动。",
      diet: "杂食性，以果实、小型动物、昆虫和鸟卵等为食。",
      features: ["体型中等", "尾较长", "面部常有浅色斑纹", "体色较暗且斑纹不如大灵猫醒目"],
      note: "用于解释灵猫类相似物种，不作为当前 12 类识别模型的正类训练样本。",
      similarSpecies: ["大灵猫", "小灵猫", "熊狸"],
      reviewTips: "若画面只拍到夜间局部身体或尾部，容易与大灵猫候选混淆，应结合头脸、尾纹、体侧斑纹和连续帧判断。",
      monitoringValue: "可作为灵猫类开放集参考，帮助降低黑熊或大灵猫的低置信度误报。",
    },
    熊狸: {
      title: "熊狸",
      latin: latin || "Arctictis binturong",
      category: "animal",
      taxonGroup: "兽类",
      family: "灵猫科",
      genus: "熊狸属",
      recognitionTier: "knowledge_reference",
      protectionLevel: "相似物种参考",
      tags: ["兽类", "灵猫科", "树栖"],
      habitat: "主要活动于热带和亚热带森林，偏树栖，常出现在林冠、树枝和果树附近。",
      habits: "夜行性或晨昏活动较多，行动相对缓慢，善攀爬，尾部可辅助攀援。",
      diet: "杂食偏果食，也取食小型动物、鸟卵和昆虫。",
      features: ["体型较大", "毛色深", "尾长而蓬松", "头脸较宽", "常在树上活动"],
      note: "用于解释黑熊、大灵猫等低置信度候选的相似物种干扰，不作为当前模型正类训练样本。",
      similarSpecies: ["黑熊", "大灵猫", "果子狸"],
      reviewTips: "树上深色大体型目标容易被误联想到黑熊；需要看尾部、攀爬姿态和头脸比例。",
      monitoringValue: "可作为知识库与开放集干扰参考，帮助识别系统保守表达不确定结果。",
    },
  };
  return supplemental[entry.folder_name] ?? null;
}

function ReferenceMetadataGrid({ sample }: { sample?: ReferenceSample }) {
  const rows = [
    ["中文名", sample?.cn_name],
    ["学名", sample?.scientific_name ?? sample?.subspecies],
    ["类群", sample?.taxon_group],
    ["来源", sample?.source],
  ].filter(([, value]) => Boolean(value));

  if (!rows.length) return null;

  return (
    <section className="guide-info-grid reference-metadata-grid">
      {rows.map(([label, value]) => (
        <div key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </section>
  );
}

function ReferenceSampleCard({ reference }: { reference: ReferenceSpecies | null }) {
  return (
    <article className="reference-card">
      <span className="eyebrow">参考样本</span>
      <h3>{reference ? reference.folder_name : "等待匹配"}</h3>
      <p className="note">{reference ? `已整理参考图 ${reference.image_count} 张，本页仅展示少量缩略图辅助复核。` : "识别到物种后显示少量参考图。"}</p>
      {reference?.samples.length ? (
        <div className="reference-grid">
          {reference.samples.slice(0, 3).map((sample) => (
            <figure key={sample.file_name}>
              <img src={`${API_BASE}${sample.file_url}`} alt={sample.file_name} />
              <figcaption>{sample.source ?? "来源未标注"}</figcaption>
            </figure>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function getReviewLevel(confidence: number): { label: string; note: string; className: string } {
  if (confidence >= 0.7) {
    return {
      label: "可展示候选",
      note: "当前候选达到演示展示阈值，建议保留原始画面、参考图和知识库特征作为复核依据。",
      className: "good",
    };
  }
  if (confidence >= 0.45) {
    return {
      label: "建议复核",
      note: "这类结果适合作为候选项展示，不建议直接当作最终物种结论。",
      className: "warn",
    };
  }
  return {
    label: "保守显示",
    note: "当前置信度偏低，前端会倾向保守表达，以免把候选结果说成定论。",
    className: "low",
  };
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatCandidates(candidates?: SpeciesCandidateResult[], includeCatalog = false): string {
  if (!candidates?.length) return "-";
  const visibleCandidates = displayableCandidates(candidates);
  if (!visibleCandidates.length) return "暂无可靠候选";
  return visibleCandidates
    .slice(0, 3)
    .map((candidate) => {
      const catalogText = includeCatalog ? ` · ${regionStatusLabel(candidate.region_status)}` : "";
      return `${candidate.label} ${formatPercent(candidate.confidence)} · ${formatCandidateSource(candidate.source)}${catalogText}`;
    })
    .join(" / ");
}

function displayableCandidates(candidates?: SpeciesCandidateResult[]): SpeciesCandidateResult[] {
  return (candidates ?? []).filter((candidate) => candidate.confidence >= CANDIDATE_DISPLAY_THRESHOLD);
}

function formatCandidateSource(source?: string): string {
  if (!source) return "未知来源";
  if (source === "reference-retrieval") return "参考检索";
  if (source === "pdf-weak-reference") return "图鉴匹配";
  if (source.includes("transformers") || source.includes("classifier")) return "本地模型";
  return source;
}

function runtimeModeLabel(models: Record<string, string>): { label: string; className: string } {
  if (!models.detector && !models.classifier) return { label: "连接中", className: "neutral" };
  if (models.detector?.includes("fallback") || models.classifier?.includes("fallback")) {
    return { label: "展示运行中", className: "warn" };
  }
  return { label: "精识别运行中", className: "good" };
}

function modelStatusLabel(value?: string): string {
  if (!value) return "连接中";
  if (value.includes("fallback-detector")) return "基础定位";
  if (value.includes("fallback-classifier")) return "候选识别";
  if (value.includes("fallback")) return "基础能力";
  if (value.includes("megadetector")) return "目标定位";
  if (value.includes("transformers")) return "精识别模型";
  return value;
}

function retrievalStatusLabel(value?: string): string {
  if (!value) return "连接中";
  if (value === "histogram") return "图鉴检索";
  if (value === "transformers") return "特征检索";
  return value;
}

function assistantStatusLabel(assistant?: Record<string, string>): string {
  if (!assistant?.mode) return "本地问答";
  if (assistant.mode === "deepseek") return "DeepSeek";
  if (assistant.mode === "local_knowledge") return "本地问答";
  return assistant.detail || assistant.mode;
}

function reviewStatusLabel(status?: string): string {
  if (status === "ready") return "可展示";
  if (status === "low_confidence") return "低置信";
  return "需复核";
}

function formatReviewCell(detection: Detection): string {
  const reasons = visibleReviewReasons(detection).slice(0, 2).map(reviewReasonLabel).join("、");
  return reasons ? `${reviewStatusLabel(detection.review_status)}：${reasons}` : reviewStatusLabel(detection.review_status);
}

function visibleReviewReasons(detection: Detection): string[] {
  const reasons = detection.review_reasons ?? [];
  if (detection.review_status !== "low_confidence") return reasons;
  return reasons.filter((reason) => reason !== "protected_species_candidate");
}

function regionStatusLabel(status?: string): string {
  if (status === "local_checklist") return "本地名录";
  if (status === "out_of_catalog") return "名录外";
  return "待核名录";
}

function candidatePillClass(candidate: SpeciesCandidateResult): string {
  if (candidate.region_status === "out_of_catalog") return "low";
  if (candidate.review_flags?.includes("protected_species")) return "warn";
  return "neutral";
}

function reviewReasonLabel(reason: string): string {
  const labels: Record<string, string> = {
    candidate_needs_confirmation: "候选需确认",
    close_top_candidates: "候选接近",
    knowledge_only_species: "知识优先",
    low_confidence: "低置信",
    model_reference_conflict: "模型与参考冲突",
    not_in_local_checklist: "不在本地名录",
    protected_species_candidate: "保护等级需核对",
    weak_reference_evidence: "图鉴证据不足",
  };
  return labels[reason] ?? reason;
}

function summarizeReviewStatus(detections: Detection[]): string {
  if (!detections.length) return "无目标";
  if (detections.some((detection) => detection.review_status === "low_confidence")) return "低置信";
  if (detections.some((detection) => detection.review_status !== "ready")) return "需复核";
  return "高置信候选";
}

function buildReportSummary(result: AnalysisResponse, speciesKnowledge: SpeciesEntry[]): string {
  const detection = result.detections[0];
  const entry = getKnowledge(result, speciesKnowledge);
  const status = summarizeReviewStatus(result.detections);
  const confidence = detection ? formatPercent(detection.confidence) : "--";
  const candidates = detection?.top_candidates?.length ? formatCandidates(detection.top_candidates) : "暂无候选";
  const rawLabel = detection?.species_label ?? "未发现目标";
  const mappedLabel = detection ? formatRecognitionConclusion(entry, detection) : "未发现目标";
  const taxonomy = entry.category ? formatTaxonomy(entry) : "暂无分类资料";
  const features = entry.features.length ? entry.features.slice(0, 4).join("；") : "暂无特征资料";
  const similarSpecies = entry.similarSpecies?.length ? entry.similarSpecies.slice(0, 4).join("、") : "暂无";

  return [
    "森智眼报告摘要",
    `任务编号：${result.media_id}`,
    `素材类型：${result.media_type === "video" ? "视频" : "图片"}`,
    `识别结论：${mappedLabel}`,
    `初始候选：${rawLabel}`,
    `学术名：${detection ? entry.latin : "--"}`,
    `分类地位：${taxonomy}`,
    `保护等级：${entry.protectionLevel ?? "未标注"}`,
    `目标数量：${result.detections.length}`,
    `综合置信度：${confidence}`,
    `复核状态：${status}`,
    `候选物种：${candidates}`,
    `识别特征：${features}`,
    `习性：${entry.habits || "暂无资料"}`,
    `食性：${entry.diet || "暂无资料"}`,
    `生境：${entry.habitat || "暂无资料"}`,
    `相似物种：${similarSpecies}`,
    `复核建议：${entry.reviewTips || getReviewLevel(detection?.confidence ?? 0).note}`,
  ].join("\n");
}

function getKnowledge(result: AnalysisResponse | null, speciesKnowledge: SpeciesEntry[]): KnowledgeEntry {
  const detection = result?.detections[0];
  if (!detection || !isDetectionReliableForSpecies(detection)) return ANIMAL_KNOWLEDGE.Unknown;

  const candidates = getReliableCandidateLabels(detection);
  const matchedSpecies = findMatchedSpecies(candidates, speciesKnowledge);
  if (matchedSpecies) return speciesToKnowledgeEntry(matchedSpecies);
  const matchedKey = Object.keys(ANIMAL_KNOWLEDGE).find((key) => candidates.some((label) => label.includes(key)));
  return ANIMAL_KNOWLEDGE[matchedKey ?? "Unknown"];
}

function getReferenceSpecies(result: AnalysisResponse | null, references: ReferenceSpecies[], speciesKnowledge: SpeciesEntry[]): ReferenceSpecies | null {
  const detection = result?.detections[0];
  if (!detection || !isDetectionReliableForSpecies(detection)) return null;
  const matchedSpecies = findMatchedSpecies(getReliableCandidateLabels(detection), speciesKnowledge);
  if (!matchedSpecies) return null;

  return findReferenceForSpecies(matchedSpecies, references);
}

function isDetectionReliableForSpecies(detection: Detection): boolean {
  if (detection.review_status === "low_confidence") return false;
  return detection.confidence >= CANDIDATE_DISPLAY_THRESHOLD || displayableCandidates(detection.top_candidates).length > 0;
}

function getReliableCandidateLabels(detection: Detection): string[] {
  const labels = detection.confidence >= CANDIDATE_DISPLAY_THRESHOLD ? [detection.species_label] : [];
  const candidateLabels =
    detection.top_candidates
      ?.filter((candidate) => candidate.confidence >= CANDIDATE_DISPLAY_THRESHOLD)
      .map((candidate) => candidate.label) ?? [];
  return [...labels, ...candidateLabels];
}

function formatRecognitionConclusion(entry: KnowledgeEntry, detection: Detection): string {
  if (entry.title === "未知动物") return "未知/待复核";
  if (recognitionResultLayer(entry, detection).kind === "direct") return entry.title;
  return `待复核候选：${entry.title}`;
}

function recognitionResultLayer(entry: KnowledgeEntry, detection: Detection): { label: string; note: string; className: string; kind: "direct" | "reference" | "unknown" } {
  if (entry.title === "未知动物") {
    return {
      label: "未知待复核",
      note: "当前结果不在可直接识别范围内，已保留图鉴参考和候选信息，建议结合原图复核。",
      className: "low",
      kind: "unknown",
    };
  }
  const isDirect = detection.review_status === "ready" && isDirectRecognitionSpeciesFromKnowledge(entry);
  if (isDirect) {
    return {
      label: "精识别",
      note: "当前结果属于模型重点训练范围，可直接作为识别结论使用。",
      className: "good",
      kind: "direct",
    };
  }
  return {
    label: "图鉴参考",
    note: "当前结果来自图鉴/知识库参考匹配，适合作为候选解释，不建议直接当作最终结论。",
    className: "warn",
    kind: "reference",
  };
}

function findReferenceForSpecies(species: SpeciesEntry, references: ReferenceSpecies[]): ReferenceSpecies | null {
  const preferredNames = [species.cn_name, ...getSpeciesAliases(species.species_id)];
  const exactMatch = references.find((reference) =>
    preferredNames.some((name) => normalizeLabel(reference.folder_name) === normalizeLabel(name))
  );
  if (exactMatch) return exactMatch;

  return (
    references.find((reference) =>
      preferredNames.some((name) => matchesReference(name, reference))
    ) ?? null
  );
}

function findMatchedSpecies(candidates: string[], speciesKnowledge: SpeciesEntry[]): SpeciesEntry | undefined {
  const sortedSpecies = sortSpecies(speciesKnowledge.filter(isWildlifeCatalogSpecies));
  return sortedSpecies.find((species) => candidates.some((candidate) => matchesSpecies(candidate, species)));
}

function findSpeciesForReference(reference: ReferenceSpecies, speciesKnowledge: SpeciesEntry[]): SpeciesEntry | undefined {
  const sample = reference.samples[0];
  const labels = [reference.folder_name, sample?.subspecies ?? ""].filter(Boolean);
  return sortSpecies(speciesKnowledge.filter(isWildlifeCatalogSpecies)).find((species) =>
    labels.some((label) => matchesSpecies(label, species))
  );
}

function findSpeciesForKnowledgeEntry(entry: KnowledgeEntry, speciesKnowledge: SpeciesEntry[]): SpeciesEntry | undefined {
  return sortSpecies(speciesKnowledge.filter(isWildlifeCatalogSpecies)).find((species) => {
    if (entry.speciesId && species.species_id === entry.speciesId) return true;
    return [entry.title, entry.latin].some((label) => matchesSpecies(label, species));
  });
}

function sortSpecies(species: SpeciesEntry[]): SpeciesEntry[] {
  return [...species].sort((left, right) => {
    const tierOrder: Record<string, number> = {
      knowledge_first: 0,
      high_demo: 1,
      candidate: 2,
      operational: 3,
    };
    const leftScore = tierOrder[left.recognition_tier] ?? 9;
    const rightScore = tierOrder[right.recognition_tier] ?? 9;
    if (leftScore !== rightScore) return leftScore - rightScore;
    return left.cn_name.localeCompare(right.cn_name, "zh-Hans-CN");
  });
}

function isWildlifeCatalogSpecies(species: SpeciesEntry): boolean {
  return WILDLIFE_CATEGORIES.has(species.category);
}

function isDirectRecognitionSpecies(species: SpeciesEntry): boolean {
  return DIRECT_RECOGNITION_TIERS.has(species.recognition_tier);
}

function isDirectRecognitionSpeciesFromKnowledge(entry: KnowledgeEntry): boolean {
  return Boolean(entry.recognitionTier && DIRECT_RECOGNITION_TIERS.has(entry.recognitionTier));
}

function recognitionScopeLabel(recognitionTier?: string): string {
  return recognitionTier && DIRECT_RECOGNITION_TIERS.has(recognitionTier) ? "直接识别" : "图鉴参考";
}

function formatCategoryLabel(category: string): string {
  if (category === "animal") return "动物";
  if (category === "bird") return "鸟类";
  if (category === "reptile_amphibian") return "爬行与两栖类";
  if (category === "plant") return "植物";
  return category;
}

function formatTaxonomy(entry: KnowledgeEntry): string {
  const parts = [entry.category, entry.taxonGroup, entry.order, entry.family, entry.genus]
    .filter(Boolean)
    .map((part) => String(part));
  const category = formatCategoryLabel(parts[0] ?? "");
  const uniqueParts: string[] = [];
  [category, ...parts.slice(1)].filter(Boolean).forEach((part) => {
    if (!uniqueParts.includes(part)) uniqueParts.push(part);
  });
  return uniqueParts.join(" / ");
}

function matchesKnowledgeFilters(entry: KnowledgeEntry, query: string, protectionFilter: "all" | "level1" | "level2"): boolean {
  if (protectionFilter === "level1" && !entry.protectionLevel?.includes("一级")) return false;
  if (protectionFilter === "level2" && !entry.protectionLevel?.includes("二级")) return false;
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return true;

  const searchable = [
    entry.title,
    entry.latin,
    entry.category ?? "",
    entry.taxonGroup ?? "",
    entry.order ?? "",
    entry.family ?? "",
    entry.genus ?? "",
    entry.protectionLevel ?? "",
    entry.habitat,
    entry.habits ?? "",
    entry.diet ?? "",
    entry.note,
    entry.reviewTips ?? "",
    entry.monitoringValue ?? "",
    entry.lifeForm ?? "",
    entry.phenology ?? "",
    entry.distribution ?? "",
    ...entry.tags,
    ...entry.features,
    ...(entry.similarSpecies ?? []),
  ]
    .join(" ")
    .toLowerCase();

  return searchable.includes(normalizedQuery);
}

function matchesAnimalTier(entry: KnowledgeEntry, tierFilter: "all" | "priority" | "candidate" | "operational"): boolean {
  if (tierFilter === "all") return true;
  if (tierFilter === "priority") return Boolean(entry.protectionLevel?.includes("一级")) || entry.recognitionTier === "knowledge_first" || entry.recognitionTier === "high_demo";
  if (tierFilter === "candidate") return entry.recognitionTier === "candidate" || Boolean(entry.protectionLevel?.includes("二级"));
  return !entry.protectionLevel?.includes("一级") && !entry.protectionLevel?.includes("二级");
}

function matchesReferenceFilters(entry: ReferenceSpecies, query: string): boolean {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return true;

  const searchable = [
    entry.folder_name,
    ...entry.samples.flatMap((sample) => [
      sample.file_name,
      sample.source ?? "",
      sample.subspecies ?? "",
      sample.note ?? "",
    ]),
  ]
    .join(" ")
    .toLowerCase();

  return searchable.includes(normalizedQuery);
}

function matchesRecordFilters(
  item: AnalysisResponse,
  speciesKnowledge: SpeciesEntry[],
  query: string,
  mediaFilter: "all" | "image" | "video",
  reviewFilter: "all" | "ready" | "review" | "empty"
): boolean {
  if (mediaFilter !== "all" && item.media_type !== mediaFilter) return false;
  const status = summarizeReviewStatus(item.detections);
  if (reviewFilter === "ready" && status !== "高置信候选") return false;
  if (reviewFilter === "review" && status !== "需复核" && status !== "低置信") return false;
  if (reviewFilter === "empty" && status !== "无目标") return false;

  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return true;

  const knowledge = getKnowledge(item, speciesKnowledge);
  const firstDetection = item.detections[0];
  const searchable = [
    item.media_id,
    item.media_type,
    item.message,
    status,
    knowledge.title,
    knowledge.latin,
    knowledge.protectionLevel ?? "",
    firstDetection?.species_label ?? "",
    ...Object.keys(item.species_summary),
    ...(firstDetection?.top_candidates?.map((candidate) => `${candidate.label} ${candidate.latin_name ?? ""}`) ?? []),
  ]
    .join(" ")
    .toLowerCase();

  return searchable.includes(normalizedQuery);
}

function matchesRecordConfidence(item: AnalysisResponse, filter: "all" | "high" | "medium" | "low"): boolean {
  if (filter === "all") return true;
  const confidence = averageRecordConfidence(item);
  if (filter === "high") return confidence >= 0.7;
  if (filter === "medium") return confidence >= 0.45 && confidence < 0.7;
  return confidence < 0.45;
}

function sortRecordHistory(items: AnalysisResponse[], sortMode: "newest" | "oldest" | "confidence_desc" | "confidence_asc"): AnalysisResponse[] {
  const sorted = [...items];
  if (sortMode === "oldest") return sorted.reverse();
  if (sortMode === "confidence_desc") {
    return sorted.sort((left, right) => averageRecordConfidence(right) - averageRecordConfidence(left));
  }
  if (sortMode === "confidence_asc") {
    return sorted.sort((left, right) => averageRecordConfidence(left) - averageRecordConfidence(right));
  }
  return sorted;
}

function averageRecordConfidence(item: AnalysisResponse): number {
  if (!item.detections.length) return 0;
  return item.detections.reduce((sum, detection) => sum + detection.confidence, 0) / item.detections.length;
}

function protectionLevelGroup(value: string): string {
  if (value.includes("一级")) return "国家一级";
  if (value.includes("二级")) return "国家二级";
  if (value.includes("自治区")) return "自治区重点";
  return "其他保护";
}

function isFocusKnowledgeEntry(entry: KnowledgeEntry): boolean {
  return entry.recognitionTier === "knowledge_first" || entry.recognitionTier === "high_demo";
}

function recognitionTierLabel(tier?: string): string {
  if (tier === "knowledge_first") return "知识优先";
  if (tier === "high_demo") return "首批精识别";
  if (tier === "candidate") return "候选识别";
  if (tier === "operational") return "监测对照";
  return "待定位";
}

function matchesSpecies(label: string, species: SpeciesEntry): boolean {
  const normalized = normalizeLabel(label);
  return [
    species.cn_name,
    species.latin_name ?? "",
    species.species_id,
    species.family ?? "",
    species.genus ?? "",
    ...getSpeciesAliases(species.species_id),
  ]
    .filter(Boolean)
    .some((value) => {
      const normalizedValue = normalizeLabel(value);
      return normalizedValue.length > 1 && (normalized.includes(normalizedValue) || normalizedValue.includes(normalized));
    });
}

function matchesReference(label: string, reference: ReferenceSpecies): boolean {
  const normalized = normalizeLabel(label);
  const aliases = [reference.folder_name, ...getReferenceAliases(reference.folder_name)];
  return aliases.some((value) => {
    const normalizedValue = normalizeLabel(value);
    return normalizedValue.length > 1 && (normalized.includes(normalizedValue) || normalizedValue.includes(normalized));
  });
}

function getSpeciesAliases(speciesId: string): string[] {
  return SPECIES_ALIASES[speciesId] ?? [];
}

function getReferenceAliases(folderName: string): string[] {
  const normalizedFolder = normalizeLabel(folderName);
  return Object.entries(SPECIES_ALIASES)
    .filter(([, aliases]) => aliases.some((alias) => normalizeLabel(alias) === normalizedFolder))
    .flatMap(([, aliases]) => aliases);
}

function normalizeLabel(value: string): string {
  return value
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function sameNormalizedLabel(left: string, right: string): boolean {
  return normalizeLabel(left) === normalizeLabel(right);
}

function speciesToKnowledgeEntry(species: SpeciesEntry): KnowledgeEntry {
  return {
    speciesId: species.species_id,
    title: species.cn_name,
    latin: species.latin_name ?? "Unknown",
    tags: species.tags.length ? species.tags : [species.recognition_tier],
    category: species.category,
    taxonGroup: species.taxon_group,
    order: species.order,
    family: species.family,
    genus: species.genus,
    recognitionTier: species.recognition_tier,
    habitat: species.habitat,
    habits: species.habits,
    diet: species.diet,
    features: species.features,
    note: species.monitoring_value,
    protectionLevel: species.protection_level,
    similarSpecies: species.similar_species,
    reviewTips: species.review_tips,
    monitoringValue: species.monitoring_value,
    lifeForm: species.life_form,
    phenology: species.phenology,
    distribution: species.distribution,
    sourceUrls: species.source_urls,
    imageUrl: species.image_url,
    imageSourceUrl: species.image_source_url,
    imageAuthor: species.image_author,
    imageLicense: species.image_license,
    imageBasisOfRecord: species.image_basis_of_record,
  };
}

function formatSourceLabel(url: string, index: number): string {
  try {
    const hostname = new URL(url).hostname.replace(/^www\./, "");
    if (hostname.includes("gxzf.gov.cn")) return "广西壮族自治区公开资料";
    if (hostname.includes("gov.cn")) return "国家重点保护野生植物名录";
    if (hostname.includes("iplant.cn")) return "中国植物志数字资源";
    return hostname;
  } catch {
    return `资料来源 ${index + 1}`;
  }
}

createRoot(document.getElementById("root")!).render(<App />);
