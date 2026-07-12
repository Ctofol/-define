import React from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  BookOpen,
  Camera,
  Database,
  FileVideo,
  History,
  ImageUp,
  Leaf,
  Loader2,
  PawPrint,
  Settings2,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import "./styles.css";

type Page = "overview" | "animal" | "plant" | "records" | "system";

type BoundingBox = { x: number; y: number; width: number; height: number };

type Detection = {
  media_id: string;
  frame_time: number;
  bbox: BoundingBox;
  detected_type: string;
  species_label: string;
  confidence: number;
  preview_crop_path: string;
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
  title: string;
  latin: string;
  tags: string[];
  habitat: string;
  features: string[];
  note: string;
};

type DemoMedia = {
  title: string;
  label: string;
  note: string;
  src: string;
  fileName: string;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

const DEMO_MEDIA: DemoMedia[] = [
  { title: "梅花鹿", label: "稳定演示", note: "主体完整，适合先演示检测框和结果表。", src: "/demo/deer.jpg?v=2", fileName: "demo-deer.jpg" },
  { title: "野猪", label: "稳定演示", note: "体型和轮廓明显，适合作为第二张测试图。", src: "/demo/boar.jpg?v=2", fileName: "demo-boar.jpg" },
  { title: "狐狸", label: "补充样本", note: "背景较复杂，适合说明真实野外场景。", src: "/demo/fox.jpg?v=2", fileName: "demo-fox.jpg" },
  { title: "狼", label: "候选识别", note: "犬科特征明显，但分类结果需保守展示。", src: "/demo/wolf.jpg?v=2", fileName: "demo-wolf.jpg" },
  { title: "夜间空场景", label: "对照样本", note: "用于演示低光或无动物场景。", src: "/demo/empty_scene.jpg?v=2", fileName: "demo-empty-scene.jpg" },
];

const NAV_ITEMS: Array<{ page: Page; label: string; icon: React.ReactNode }> = [
  { page: "overview", label: "平台总览", icon: <BarChart3 size={18} /> },
  { page: "animal", label: "动物识别", icon: <PawPrint size={18} /> },
  { page: "plant", label: "植物知识库", icon: <Leaf size={18} /> },
  { page: "records", label: "分析记录", icon: <History size={18} /> },
  { page: "system", label: "系统说明", icon: <ShieldCheck size={18} /> },
];

const ANIMAL_KNOWLEDGE: Record<string, KnowledgeEntry> = {
  梅花鹿: {
    title: "梅花鹿",
    latin: "Cervus nippon",
    tags: ["哺乳动物", "鹿科", "林缘活动"],
    habitat: "林地、草坡、林缘和开阔灌丛区域。",
    features: ["体表白色斑点明显", "四肢细长", "警觉性强"],
    note: "当前部署版对内置稳定样本使用演示映射，真实物种结论仍建议结合模型版和人工复核。",
  },
  野猪: {
    title: "野猪",
    latin: "Sus scrofa",
    tags: ["哺乳动物", "偶蹄目", "夜间活动"],
    habitat: "森林、灌丛、农田边缘和山地沟谷。",
    features: ["体型粗壮", "吻部突出", "背部轮廓较高"],
    note: "适合作为 camera-trap MVP 的稳定演示样本，但真实部署仍需要区域物种库支持。",
  },
  狐狸: {
    title: "狐狸",
    latin: "Vulpes",
    tags: ["哺乳动物", "犬科", "候选分类"],
    habitat: "林缘、草地、荒坡和农田周边。",
    features: ["吻部较尖", "尾部蓬松", "行动灵活"],
    note: "狐狸类结果建议作为候选展示，后续可用本地物种清单细分到具体种。",
  },
  狼: {
    title: "狼",
    latin: "Canis lupus",
    tags: ["哺乳动物", "犬科", "需复核"],
    habitat: "山地、森林、草原和人类干扰较少区域。",
    features: ["体型较大", "吻部较长", "耳部直立"],
    note: "狼与犬、狐狸等容易在单帧中混淆，MVP 中建议显示为候选并保留复核口径。",
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
    note: "犬属包含多种动物，MVP 中建议把它展示为候选属类。",
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

const PLANT_LIBRARY: KnowledgeEntry[] = [
  {
    title: "银杏",
    latin: "Ginkgo biloba",
    tags: ["乔木", "扇形叶", "秋季识别"],
    habitat: "城市绿化、山地林缘、栽培环境。",
    features: ["扇形叶", "叶脉二叉分叉", "秋季叶色金黄"],
    note: "植物识别更依赖叶、花、果和季节信息，当前页面只做知识库预留。",
  },
  {
    title: "马尾松",
    latin: "Pinus massoniana",
    tags: ["针叶树", "常绿乔木", "山地"],
    habitat: "丘陵、山地、阳坡和疏林区域。",
    features: ["针叶成束", "树皮灰褐色", "球果明显"],
    note: "如果画面里只有远景树冠，分类通常不稳定。",
  },
  {
    title: "芒草",
    latin: "Miscanthus sinensis",
    tags: ["草本", "禾本科", "林缘"],
    habitat: "林缘、坡地、路旁和开阔草地。",
    features: ["线形叶", "大型圆锥花序", "秋季穗状明显"],
    note: "草本植物通常需要更近的细节图，适合作为后续采集样本。",
  },
  {
    title: "毛竹",
    latin: "Phyllostachys edulis",
    tags: ["竹类", "常绿", "林地"],
    habitat: "山坡、沟谷、竹林和人工栽培区域。",
    features: ["竹秆明显", "节间较长", "叶片披针形"],
    note: "竹类识别需要看竹秆、枝叶和生长环境，远景很容易只识别为植被。",
  },
  {
    title: "山茶",
    latin: "Camellia japonica",
    tags: ["灌木", "常绿", "花期特征"],
    habitat: "山地林缘、园林和湿润半阴环境。",
    features: ["叶片革质", "边缘有细锯齿", "花色醒目"],
    note: "花期图片更适合展示，非花期需要依赖叶片、枝条和生境信息。",
  },
  {
    title: "杉木",
    latin: "Cunninghamia lanceolata",
    tags: ["乔木", "针叶", "人工林"],
    habitat: "山地、人工林、丘陵和常绿林环境。",
    features: ["叶片狭长", "树干通直", "枝叶层次分明"],
    note: "针叶树在远景里常容易和周边植被混淆，更适合做结构化知识卡展示。",
  },
];

const ROADMAP_STEPS = [
  { phase: "一期", title: "演示闭环", points: ["动物检测", "候选分类", "结果回放", "本地保存"] },
  { phase: "二期", title: "知识库补强", points: ["植物知识库", "物种特征卡", "栖息地字段", "保护等级"] },
  { phase: "三期", title: "人工复核", points: ["待确认状态", "样本沉淀", "修正记录", "结果追踪"] },
  { phase: "四期", title: "模型升级", points: ["区域物种库", "自训练模型", "同一目标去重", "批量回放分析"] },
];

function App() {
  const [page, setPage] = React.useState<Page>("overview");
  const [file, setFile] = React.useState<File | null>(null);
  const [localPreview, setLocalPreview] = React.useState<string | null>(null);
  const [confidence, setConfidence] = React.useState(0.35);
  const [frameInterval, setFrameInterval] = React.useState(1);
  const [includeLowConfidence, setIncludeLowConfidence] = React.useState(false);
  const [result, setResult] = React.useState<AnalysisResponse | null>(null);
  const [history, setHistory] = React.useState<AnalysisResponse[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    fetch(`${API_BASE}/api/results`)
      .then((response) => (response.ok ? response.json() : []))
      .then(setHistory)
      .catch(() => setHistory([]));
  }, []);

  function selectFile(nextFile: File | null) {
    setFile(nextFile);
    setResult(null);
    setError(null);
    if (localPreview) URL.revokeObjectURL(localPreview);
    setLocalPreview(nextFile ? URL.createObjectURL(nextFile) : null);
  }

  async function useDemoMedia(media: DemoMedia) {
    try {
      const response = await fetch(media.src);
      if (!response.ok) throw new Error("示例素材加载失败");
      const blob = await response.blob();
      const demoFile = new File([blob], media.fileName, { type: blob.type || "image/jpeg" });
      selectFile(demoFile);
      setPage("animal");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "示例素材加载失败");
    }
  }

  async function analyze() {
    if (!file) return;
    setIsLoading(true);
    setError(null);

    const form = new FormData();
    form.append("file", file);
    form.append("confidence_threshold", String(confidence));
    form.append("frame_interval_seconds", String(frameInterval));
    form.append("include_low_confidence", String(includeLowConfidence));

    const endpoint = file.type.startsWith("video/") ? "/api/analyze/video" : "/api/analyze/image";

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, { method: "POST", body: form });
      if (!response.ok) throw new Error(await response.text());
      const payload = (await response.json()) as AnalysisResponse;
      setResult(payload);
      setHistory((items) => [payload, ...items.filter((item) => item.media_id !== payload.media_id)].slice(0, 25));
      setPage("animal");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "分析失败");
    } finally {
      setIsLoading(false);
    }
  }

  const previewSource = result?.preview_url ? `${API_BASE}${result.preview_url}` : localPreview;
  const activeKnowledge = getKnowledge(result);
  const modelStatus = result?.model_status;

  return (
    <main className="app-shell">
      <aside className="nav">
        <div className="brand">
          <Camera size={24} />
          <div>
            <h1>动植物识别平台</h1>
            <span>Camera-trap MVP</span>
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
      </aside>

      <section className={`page page-${page}`}>
        {page === "overview" ? <OverviewPage history={history} result={result} setPage={setPage} /> : null}
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
            demoMedia={DEMO_MEDIA}
            onFile={selectFile}
            onUseDemo={useDemoMedia}
            onAnalyze={analyze}
            setConfidence={setConfidence}
            setFrameInterval={setFrameInterval}
            setIncludeLowConfidence={setIncludeLowConfidence}
          />
        ) : null}
        {page === "plant" ? <PlantPage /> : null}
        {page === "records" ? <RecordsPage history={history} onOpen={(item) => { setResult(item); setPage("animal"); }} /> : null}
        {page === "system" ? <SystemPage modelStatus={modelStatus} /> : null}
      </section>
    </main>
  );
}

function OverviewPage({ history, result, setPage }: { history: AnalysisResponse[]; result: AnalysisResponse | null; setPage: (page: Page) => void }) {
  return (
    <>
      <PageHeader
        eyebrow="平台总览"
        title="野外动植物识别 MVP"
        subtitle="把动物检测、候选分类、植物知识库和分析记录分成独立页面，汇报时更清楚。"
      />
      <section className="metric-grid">
        <MetricCard label="分析记录" value={String(history.length)} hint="本地保存的识别结果" />
        <MetricCard label="当前目标" value={String(result?.detections.length ?? 0)} hint="最近一次分析中的目标数" />
        <MetricCard label="动物模型" value="已接入" hint="MegaDetectorV6 + Amazon Rainforest" />
        <MetricCard label="植物模块" value="知识库" hint="识别接口预留" />
      </section>
      <section className="overview-grid">
        <ModuleCard icon={<PawPrint size={24} />} title="动物识别" text="上传图片或视频，查看框选、候选分类和置信度。" action="进入动物识别" onClick={() => setPage("animal")} />
        <ModuleCard icon={<Leaf size={24} />} title="植物知识库" text="展示植物字段结构和后续接入方式，不夸大当前能力。" action="查看植物库" onClick={() => setPage("plant")} />
        <ModuleCard icon={<History size={24} />} title="分析记录" text="集中查看最近的结果，适合演示回放和结果切换。" action="查看记录" onClick={() => setPage("records")} />
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
  demoMedia: DemoMedia[];
  onFile: (file: File | null) => void;
  onUseDemo: (media: DemoMedia) => void;
  onAnalyze: () => void;
  setConfidence: (value: number) => void;
  setFrameInterval: (value: number) => void;
  setIncludeLowConfidence: (value: boolean) => void;
}) {
  return (
    <>
      <PageHeader eyebrow="动物识别" title="动物检测与实验性分类" subtitle="当前分类结果更适合作为候选类别展示，低置信度时会保守表达。" />
      <section className="demo-strip">
        {props.demoMedia.map((item) => (
          <button key={item.src} type="button" className="demo-card" onClick={() => props.onUseDemo(item)}>
            <img src={item.src} alt={item.title} />
            <div>
              <strong>{item.title}</strong>
              <span>{item.label}</span>
              <p>{item.note}</p>
            </div>
          </button>
        ))}
      </section>
      <ResultInsight result={props.result} />
      <section className="animal-layout">
        <aside className="tool-panel">
          <UploadPanel file={props.file} isLoading={props.isLoading} onFile={props.onFile} onAnalyze={props.onAnalyze} />
          <SettingsPanel {...props} />
        </aside>
        <main className="work-panel">
          <PreviewPanel file={props.file} previewSource={props.previewSource} />
          <ResultTable result={props.result} error={props.error} />
        </main>
        <aside className="knowledge-panel">
          <SessionSummary result={props.result} file={props.file} />
          <KnowledgeCard entry={props.activeKnowledge} />
        </aside>
      </section>
    </>
  );
}

function PlantPage() {
  return (
    <>
      <PageHeader eyebrow="植物知识库" title="植物识别接口与知识库" subtitle="当前只展示知识库结构和字段占位，不承诺已经接入植物自动识别模型。" />
      <section className="card plant-note">
        <div className="card-title"><Leaf size={18} /><span>当前状态</span></div>
        <ul className="compact-list">
          <li>植物页用于展示知识库结构，不是假装已经能稳定识别植物。</li>
          <li>后续可接入本地植物模型或外部 API，再把结果映射到这套字段。</li>
          <li>目前建议把它当成二期能力入口，而不是一期演示重点。</li>
        </ul>
      </section>
      <section className="plant-grid">
        {PLANT_LIBRARY.map((entry) => <KnowledgeCard key={entry.latin} entry={entry} />)}
      </section>
      <section className="plant-feature-grid">
        <InfoBlock title="采集优先级" items={["叶片近景优先", "花果其次", "树皮和枝条作为补充", "尽量保留整株与环境信息"]} />
        <InfoBlock title="识别重点" items={["叶形与叶缘", "叶脉走向", "花果颜色与形态", "季节和生境"]} />
        <InfoBlock title="后续接入" items={["本地植物模型", "外部识别 API", "知识库映射", "人工复核与样本沉淀"]} />
      </section>
    </>
  );
}

function RecordsPage({ history, onOpen }: { history: AnalysisResponse[]; onOpen: (item: AnalysisResponse) => void }) {
  const imageCount = history.filter((item) => item.media_type === "image").length;
  const videoCount = history.filter((item) => item.media_type === "video").length;
  const latest = history[0];

  return (
    <>
      <PageHeader eyebrow="分析记录" title="历史任务与演示回放" subtitle="这里汇总本地分析结果，适合汇报时快速切回前一次识别。" />
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
          <section className="records-list">
            {history.length === 0 ? (
              <EmptyState text="暂无分析记录" />
            ) : (
              history.map((item) => (
                <button key={item.media_id} className="record-row" onClick={() => onOpen(item)}>
                  <div>
                    <strong>{item.media_type === "video" ? "视频分析" : "图片分析"}</strong>
                    <span>{item.message}</span>
                  </div>
                  <b>{item.detections.length} 个目标</b>
                </button>
              ))
            )}
          </section>
        </div>
        <aside className="records-side">
          <InfoBlock title="使用方式" items={["点击记录可切回对应结果", "适合演示回放和中途改图", "历史结果保存在本地 JSON 文件中"]} />
          <InfoBlock
            title="结果提示"
            items={
              latest
                ? [`最新媒体类型：${latest.media_type}`, `最新目标数：${latest.detections.length}`, `最新结果：${latest.message}`]
                : ["暂无最近结果", "上传素材后会自动出现在这里", "可作为演示回放入口"]
            }
          />
        </aside>
      </section>
    </>
  );
}

function SystemPage({ modelStatus }: { modelStatus?: Record<string, string> }) {
  return (
    <>
      <PageHeader
        eyebrow="系统说明"
        title="能力边界与后续路线"
        subtitle="把 MVP 已完成能力、模型边界和后续发展路径讲清楚，避免把候选识别说成确定结论。"
      />
      <section className="system-grid">
        <InfoBlock title="当前能力" items={["动物目标检测：MegaDetectorV6", "实验性动物候选分类：Amazon Rainforest 分类器", "植物模块：知识库页面与后续接口预留", "结果展示：框选图、候选分类、置信度、历史回放"]} />
        <InfoBlock title="能力边界" items={["动物分类多为候选类别或属级结果", "不保证中国本土物种级准确率", "植物暂未接入自动识别模型", "低置信度或类外动物应显示未知或待复核"]} />
        <InfoBlock title="后续材料" items={["目标动植物清单", "每类样本图片 50-200 张起步", "知识库字段与保护等级资料", "稳定演示图片和短视频"]} />
        <InfoBlock title="模型状态" items={[`检测：${modelStatus?.detector ?? "等待分析"}`, `分类：${modelStatus?.classifier ?? "等待分析"}`, "设备：CPU"]} />
      </section>
      <section className="roadmap-section">
        <div className="section-head">
          <div>
            <span className="eyebrow">推进路线</span>
            <h3>现在做什么，后面怎么扩展</h3>
          </div>
          <p>这部分适合直接拿来做汇报口径。</p>
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

function UploadPanel({ file, isLoading, onFile, onAnalyze }: { file: File | null; isLoading: boolean; onFile: (file: File | null) => void; onAnalyze: () => void }) {
  return (
    <section className="card">
      <div className="card-title">
        <ImageUp size={18} />
        <span>素材上传</span>
      </div>
      <label className="dropzone">
        <UploadCloud size={34} />
        <strong>{file ? file.name : "选择图片或视频"}</strong>
        <span>支持 camera-trap 图片、短视频片段</span>
        <input type="file" accept="image/*,video/*" onChange={(event) => onFile(event.target.files?.[0] ?? null)} />
      </label>
      <button className="primary" disabled={!file || isLoading} onClick={onAnalyze}>
        {isLoading ? <Loader2 className="spin" size={18} /> : <Activity size={18} />}
        <span>{isLoading ? "分析中..." : "开始识别"}</span>
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

function ResultTable({ result, error }: { result: AnalysisResponse | null; error: string | null }) {
  return (
    <section className="card">
      <div className="card-title">
        <Database size={18} />
        <span>{result?.message ?? "等待分析"}</span>
      </div>
      {error ? <p className="error">{error}</p> : null}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>截图</th>
              <th>分类结果</th>
              <th>类型</th>
              <th>时间</th>
              <th>置信度</th>
              <th>位置</th>
            </tr>
          </thead>
          <tbody>
            {result?.detections.map((item, index) => (
              <tr key={`${item.media_id}-${index}`}>
                <td>
                  <img className="crop" src={`${API_BASE}${item.preview_crop_path}`} alt={item.species_label} />
                </td>
                <td>{item.species_label}</td>
                <td>{item.detected_type}</td>
                <td>{item.frame_time.toFixed(2)}s</td>
                <td>{Math.round(item.confidence * 100)}%</td>
                <td>
                  {item.bbox.x},{item.bbox.y},{item.bbox.width}x{item.bbox.height}
                </td>
              </tr>
            )) ?? null}
            {result && result.detections.length === 0 ? (
              <tr>
                <td colSpan={6} className="muted">
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

function ResultInsight({ result }: { result: AnalysisResponse | null }) {
  const detection = result?.detections[0];
  const confidence = detection?.confidence ?? 0;
  const reviewLevel = getReviewLevel(confidence);
  const label = detection?.species_label ?? "未开始分析";

  return (
    <section className="card insight-card">
      <div className="card-title">
        <ShieldCheck size={18} />
        <span>结果解读</span>
      </div>
      <div className="insight-main">
        <strong>{label}</strong>
        <span>{detection ? `${Math.round(confidence * 100)}% 置信度` : "上传素材后会显示候选结果"}</span>
      </div>
      <div className="pill-row">
        <span className={`pill ${reviewLevel.className}`}>{reviewLevel.label}</span>
        <span className="pill neutral">目标数 {result?.detections.length ?? 0}</span>
      </div>
      <p className="insight-note">{reviewLevel.note}</p>
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
      <SideRow label="检测模型" value={result?.model_status?.detector ?? "待分析"} />
      <SideRow label="分类模型" value={result?.model_status?.classifier ?? "待分析"} />
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

function SideRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="side-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function KnowledgeCard({ entry }: { entry: KnowledgeEntry }) {
  return (
    <article className="knowledge-card">
      <span className="eyebrow">知识卡片</span>
      <h3>{entry.title}</h3>
      <p className="latin">{entry.latin}</p>
      <div className="tag-row">{entry.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
      <p>{entry.habitat}</p>
      <ul>{entry.features.map((feature) => <li key={feature}>{feature}</li>)}</ul>
      <p className="note">{entry.note}</p>
    </article>
  );
}

function getReviewLevel(confidence: number): { label: string; note: string; className: string } {
  if (confidence >= 0.8) {
    return {
      label: "可直接展示",
      note: "当前结果可用于演示，但仍建议结合现场图像和知识库复核。",
      className: "good",
    };
  }
  if (confidence >= 0.55) {
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

function getKnowledge(result: AnalysisResponse | null): KnowledgeEntry {
  const label = result?.detections[0]?.species_label ?? "Unknown";
  const matchedKey = Object.keys(ANIMAL_KNOWLEDGE).find((key) => label.includes(key));
  return ANIMAL_KNOWLEDGE[matchedKey ?? "Unknown"];
}

createRoot(document.getElementById("root")!).render(<App />);
