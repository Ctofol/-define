# 广西动植物智能识别与生态监测平台

> 面向野外巡护、生态监测、物种保护与公众科普的一体化智能平台

## 项目简介

广西拥有丰富而独特的生物多样性，但传统野外调查仍面临素材数量大、人工判读耗时、专业人员有限、识别结果难沉淀等问题。本项目围绕“采集—识别—复核—入库—分析—科普”全过程，构建移动使用端、PC 管理端和智能分析服务协同工作的动植物识别平台。

巡护人员可以通过手机上传现场图片或视频，获得目标位置、候选物种、置信度及保护信息；管理人员可以在 PC 端完成批量分析、专家复核、数据统计、物种资源和样本模型管理。识别结果经人工复核后可继续沉淀为区域化样本，为后续模型迭代提供数据基础。

本项目不是单一的图片分类工具，而是一套面向真实生态业务流程设计、可持续演进的数字化解决方案。

## 项目亮点

### 1. 识别、复核与样本沉淀形成闭环

平台将 AI 识别结果与专家复核流程连接起来。低置信度、重点保护物种和疑难样本可进入复核队列，复核结论可用于修正记录并沉淀高质量训练数据，解决“模型给出结果后无人校验、数据无法再利用”的问题。

### 2. 检测与分类结果分层表达

系统分别展示目标检测置信度、物种分类置信度、Top 3 候选和人工复核状态，避免把“画面中检测到动物”误解为“已经准确识别具体物种”。对于未知或低置信度目标，平台保留开放集结果并提示人工确认。

### 3. 双端协同覆盖真实使用场景

- 移动端服务巡护人员和公众，提供现场识别、重点物种上报、资源浏览、生态问答和个人记录。
- PC 管理端服务管理人员与专家，提供监测总览、批量任务、专家复核、统计报告、样本模型和系统管理。

### 4. 区域化知识库与可追溯资料

平台围绕广西重点保护和代表性动植物建设知识库，支持中文名、学名、分类、保护等级、生境、分布和识别特征等信息检索。植物知识库已整理 36 个重点或代表性物种，图片记录来源与授权信息；图册资料提取后先进入待复核区，不直接作为正式样本。

### 5. 模型与基础设施均可替换

智能分析层采用模块化设计，可按环境切换检测、分类、参考样本检索和大语言模型服务。开发环境可使用本地文件、SQLite 和进程内任务，正式环境可切换到 PostgreSQL、Redis/Celery 与 MinIO，便于从比赛演示平滑扩展到实际部署。

## 核心功能

| 功能模块 | 主要能力 |
| --- | --- |
| 智能识别 | 图片识别、视频抽帧分析、目标框定位、候选物种、置信度分层展示 |
| 重点物种上报 | 现场信息填写、图片上传、保护信息关联、复核流转 |
| 专家复核 | 任务领取、候选核验、复核结论、乐观锁防止重复处理 |
| 物种知识库 | 动植物分类检索、物种详情、保护等级、生境与广西分布 |
| 物种图鉴 | 广西重点保护野生动物图册浏览、图片与知识卡片联动 |
| 生态助手 | 基于本地知识库回答物种特征、相似物种和复核建议，可选接入兼容大模型接口 |
| 监测管理 | 批量图片、视频和 ZIP 安全导入，任务状态与结果统一管理 |
| 数据分析 | 识别趋势、物种分布、重点记录和统计报告展示 |
| 样本与模型 | 参考样本管理、元数据索引、训练清单、模型评估及版本迭代工具 |
| 权限管理 | JWT 登录、HttpOnly 刷新会话和四角色 RBAC 权限控制 |

## 系统架构

```mermaid
flowchart LR
    A["移动端<br/>巡护与公众使用"] --> C["FastAPI 业务 API"]
    B["PC 管理端<br/>管理与专家复核"] --> C
    C --> D["智能分析服务<br/>检测·分类·参考检索"]
    C --> E["业务数据<br/>PostgreSQL / SQLite"]
    C --> F["任务队列<br/>Redis + Celery"]
    C --> G["对象存储<br/>MinIO / 本地文件"]
    D --> H["物种知识库与参考样本"]
    D --> I["模型与训练评估工具链"]
    J["人工复核结果"] --> H
    J --> I
```

## 技术路线

- 前端：React 19、TypeScript、Vite、Ant Design、ECharts
- 后端：FastAPI、Pydantic、SQLAlchemy、Alembic
- 智能分析：PyTorch、Pytorch-Wildlife、OpenCV、Pillow
- 数据与任务：PostgreSQL、Redis、Celery、MinIO
- 安全机制：JWT、HttpOnly 刷新会话、RBAC、上传文件校验
- 工程化：Docker Compose、Pytest、数据清洗与模型评估工具链

## 业务闭环

1. 巡护人员在移动端拍照或选择图片、视频并提交分析。
2. 系统完成动物目标检测、裁剪、候选分类和参考样本检索。
3. 前端展示目标框、检测置信度、分类置信度、Top 3 候选及物种知识卡片。
4. 低置信度、疑难或重点物种记录进入专家复核队列。
5. 专家在 PC 管理端核验候选、填写意见并形成可信记录。
6. 经确认的素材与元数据进入样本管理流程，用于统计分析和后续模型训练。

## 当前成果

- 完成移动使用端、PC 管理端和平台 API 的双端协同架构。
- 打通图片/视频分析、候选识别、重点上报、专家复核和历史记录闭环。
- 建成动物知识库、36 种广西重点或代表性植物知识库及图册浏览能力。
- 建立参考样本元数据索引、候选数据审核、训练清单生成和模型评估工具链。
- 支持本地轻量运行及 PostgreSQL、Redis/Celery、MinIO 生产化部署方案。
- 建立自动化测试、发布清单、构建验证和回滚脚本。

## 应用价值

- **提升巡护效率**：辅助处理大量相机或现场采集素材，缩短人工初筛时间。
- **强化保护响应**：让重点保护物种记录更快进入上报和专家核验流程。
- **沉淀区域数据资产**：将分散的图片、识别结果和复核意见转化为结构化数据。
- **服务科研与管理**：为物种出现记录、监测趋势和资源调查提供数字化支撑。
- **促进公众科普**：通过知识库、图鉴和生态助手降低专业知识获取门槛。

## 在线演示与快速部署

- 移动端演示：<http://82.156.50.58:5002>
- 后端健康检查：<http://82.156.50.58:5001/api/health>

完整环境可通过 Docker Compose 一键启动：

```powershell
docker compose up --build
```

启动后，移动端位于 <http://localhost:8080/>，PC 管理端位于 <http://localhost:8080/admin/>。

> 在线演示部署在轻量服务器，主要展示产品交互和业务闭环。真实模型推理建议在配置模型权重的本地或 GPU 环境中运行。

## 项目边界与发展计划

当前版本已完成可运行的 MVP 和主要业务闭环。模型效果受训练数据、拍摄条件、设备性能和物种分布差异影响，平台不会将低置信度候选直接表述为确定结论。视频目前采用抽帧分析，跨帧目标去重仍在持续优化。

下一阶段将重点扩充经过授权审核的广西本地物种样本，训练区域化分类模型；接入植物识别能力；优化相似物种判别、开放集拒识和跨帧去重；进一步建设物种时空分布分析、预警和多机构协作能力。

## 参赛建议体验路径

建议评审按照“移动端现场识别与上报 → PC 端专家复核 → 知识库与统计分析 → 样本和模型迭代”的顺序体验，从而完整了解项目如何把人工智能能力嵌入生态保护业务流程。

**项目愿景：让每一次野外记录都能被识别、被核验、被沉淀，并最终服务于生物多样性保护。**

<details>
<summary><strong>展开查看详细技术资料、接口与部署说明</strong></summary>

这是一个面向巡护、监测和科普场景的动植物识别平台，提供素材识别、物种知识库、图鉴浏览、生态问答助手和历史记录管理。

## 双端架构

- 移动使用端：`frontend/`，提供实名登录、现场识别、动植物资源中心、重点物种上报、生态助手和个人记录。
- PC 管理端：`frontend/admin/`，提供数据总览、批量分析、专家复核、监测数据、物种资源、样本模型、统计报告和系统管理。
- 平台 API：兼容接口保留在 `/api`，新增带 JWT/RBAC 的业务接口位于 `/api/v1`。
- 数据与任务：本地开发可使用 SQLite 和进程内后台任务；正式部署使用 PostgreSQL、Redis/Celery 和 MinIO。
- 物种资料统一保存在动植物知识库，通过分类、科属和保护等级筛选与浏览。

完整部署可执行：

```powershell
docker compose up --build
```

启动后移动端位于 `http://localhost:8080/`，PC 管理端位于 `http://localhost:8080/admin/`。首次部署必须通过环境变量修改管理员密码和 JWT 密钥。

当前项目分为两种运行状态：

- 本地真实模型版：本机可加载 MegaDetectorV6 和 Amazon Rainforest 分类器。
- 线上轻量演示版：部署在轻量服务器上，使用 fallback/mock 模式和内置示例映射，保证演示页面稳定可访问。

线上演示地址：

- 前端：`http://82.156.50.58:5002`
- 后端健康检查：`http://82.156.50.58:5001/api/health`

## 当前已实现

- React + Vite 移动端和独立 PC 管理端
- FastAPI 后端接口
- JWT 登录、HttpOnly 刷新会话和四角色 RBAC
- PostgreSQL 兼容业务模型、Alembic 基线迁移和幂等旧数据迁移工具
- Redis/Celery 异步识别任务与 MinIO 对象存储适配
- 重点物种上报、规则自动复核入队、专家领取与乐观锁决策
- 批量图片、视频和 ZIP 安全导入
- 图片上传分析
- 视频上传与抽帧分析接口
- 目标框、置信度、裁剪图、结果表格展示
- 检测置信度、分类置信度、Top 3 候选和人工复核状态拆分展示
- 本地 JSON 历史记录保存与回放
- 物种知识库和参考样本联动
- 动物物种知识库 API 和前端知识卡片
- 参考样本目录 API 和静态预览
- PDF 图册图片提取到待复核区，并生成元数据和联系表
- 动物知识库、植物知识库和物种图鉴分栏展示
- 植物知识库收录 36 个广西重点保护或代表性物种，覆盖分类、保护等级、生活型、生境、花果期、广西分布、识别特征、真实图片和资料来源
- 36 个植物条目均已收录可追溯来源与授权信息的真实照片，不以生成图或来源不明图片替代
- 移动端已适配首页、拍照/相册识别入口、动植物知识库、物种详情、历史记录和底部导航
- 生态助手：默认使用本地知识库，可选接入 OpenAI 兼容大模型接口增强回答
- 线上轻量部署版

## 页面结构

- `智能识别`：上传图片或视频，查看目标框、候选物种、置信度、复核提示和参考图。
- `动物知识库`：检索动物中文名、学名、分类、保护等级、习性、食性和识别特征。
- `植物知识库`：检索 36 个广西重点植物条目，按生活型和保护等级筛选，查看真实图片、形态、生境、花果期、广西分布、现场记录提示和权威资料来源。
- `物种图鉴`：浏览广西重点保护野生动物口袋书图像，点击查看大图和物种资料。
- `生态助手`：围绕识别结果、物种特征、相似物种和复核建议进行问答。
- `识别记录`：查看最近识别结果，支持切回识别页回放和复制报告摘要。

## 模型状态

### 本地真实模型版

本地已经配置以下模型文件：

```text
models/megadetector/md_v6.pt
models/species-classifier/amazon_v2.ckpt
```

本地后端可加载：

- 检测模型：`Pytorch-Wildlife MegaDetectorV6`
- 分类模型：`Pytorch-Wildlife AI4GAmazonRainforest`

注意：Amazon Rainforest 分类器更偏向亚马逊雨林相机陷阱数据集，不等于中国本土物种级识别模型。对梅花鹿、狼、狐狸等样本，可能出现属级、错分、低置信度或未知结果。

### 线上轻量演示版

当前线上服务器资源较小，没有部署 PyTorch 大模型。线上使用：

- 检测：`fallback-detector`
- 分类：`fallback-classifier`

线上版的 88% 等置信度表示“检测到动物目标”的置信度，不表示“物种分类”的置信度。物种分类未接入时，普通上传图片会显示为“未知动物”或“未分类动物”。

为了保证 MVP 演示稳定，线上版对内置示例文件名做了演示映射：

```text
demo-deer.jpg        -> 梅花鹿
demo-boar.jpg        -> 野猪
demo-pangolin.png    -> 中华穿山甲
demo-leopard-cat.png -> 豹猫
demo-black-bear.png  -> 黑熊
demo-large-civet.png -> 大灵猫
demo-fox.jpg         -> 赤狐
demo-wolf.jpg        -> 狼
demo-empty-scene.jpg -> 空场景/无动物结果
```

这些映射只用于演示闭环，不代表真实模型已经具备对应物种级识别能力。

## 技术栈

- 后端：FastAPI、Pydantic、Pillow
- 本地视频处理：OpenCV
- 本地模型集成：Pytorch-Wildlife、PyTorch
- 前端：React、Vite、TypeScript、lucide-react
- 存储：本地文件系统 JSON、上传图、裁剪图
- 线上轻量部署：FastAPI + Python 静态文件服务

## 本地运行

### 一键启动

```powershell
.\scripts\start_demo.ps1
```

### 停止服务

```powershell
.\scripts\stop_demo.ps1
```

### 检查环境

```powershell
.\scripts\check_env.ps1
```

### 安装模型依赖

```powershell
.\scripts\install_models.ps1
```

## 分别启动

### 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 前端

```powershell
cd frontend
npm install
npm run dev
```

本地访问：

- 前端：`http://127.0.0.1:5173`
- 后端健康检查：`http://127.0.0.1:8000/api/health`

## 轻量部署说明

服务器资源较小时，不建议安装完整 PyTorch 模型依赖。项目提供轻量依赖文件：

```text
backend/requirements-lite.txt
```

轻量部署建议配置：

```text
WILDLIFE_DETECTOR_BACKEND=mock
WILDLIFE_CLASSIFIER_BACKEND=mock
WILDLIFE_STORAGE_DIR=storage
WILDLIFE_CORS_ORIGINS=http://服务器IP:5002
```

前端构建时需要指定线上后端地址：

```powershell
$env:VITE_API_BASE='http://82.156.50.58:5001'
npm run build
```

如果前后端同域部署，可以不设置 `VITE_API_BASE`，前端会默认请求同域 `/api`。

生态助手可选接入 OpenAI 兼容接口，后端 `.env` 中配置：

```text
WILDLIFE_LLM_API_KEY=你的密钥
WILDLIFE_LLM_BASE_URL=https://api.openai.com/v1/chat/completions
WILDLIFE_LLM_MODEL=gpt-4o-mini
```

如果密钥、接口地址或模型名未配置成功，助手会自动回退到本地知识库问答。

## API

- `GET /api/health`
- `GET /api/species`
- `GET /api/species/{species_id}`
- `GET /api/species-catalog`
- `GET /api/reference-samples`
- `GET /api/reference-samples/{folder_name}`
- `GET /api/pdf-weak-reference-samples`
- `GET /api/knowledge-open-set-samples`
- `POST /api/assistant/chat`
- `POST /api/analyze/image`
- `POST /api/analyze/video`
- `GET /api/results`
- `GET /api/results/{media_id}`

上传参数：

- `file`：上传文件
- `confidence_threshold`：检测阈值，默认 `0.35`
- `frame_interval_seconds`：视频抽帧间隔，默认 `1.0`
- `include_low_confidence`：是否保留低置信度结果

## 结果字段

每条分析结果包含：

- `media_id`
- `media_type`
- `preview_url`
- `detections`
- `species_summary`
- `model_status`
- `message`

单个检测结果包含：

- `media_id`
- `frame_time`
- `bbox`
- `detected_type`
- `species_label`
- `confidence`
- `detection_confidence`
- `classification_confidence`
- `top_candidates`
- `review_status`
- `preview_crop_path`

## 文件存储

本地运行时，结果保存在：

```text
storage/results/
storage/uploads/
storage/crops/
```

演示素材位于：

```text
frontend/public/demo/
```

推荐演示包见：

```text
docs/demo_pack.md
```

物种知识库和参考样本位于：

```text
backend/app/data/species_knowledge.json
backend/app/data/plant_species_catalog.json
reference_species/
reference_species/待复核/
reference_species/metadata_index.csv
```

元数据索引说明见：

```text
docs/metadata_index.md
```

初版完成度清单见：

```text
docs/initial_completion_checklist.md
```

PDF 图册素材提取流程见：

```text
docs/pdf_species_asset_pipeline.md
docs/pdf_extraction_report_0719_guangxi.md
```

## 环境变量

主要配置项来自 `backend/app/settings.py`：

- `WILDLIFE_DETECTOR_BACKEND`
- `WILDLIFE_CLASSIFIER_BACKEND`
- `WILDLIFE_INFERENCE_DEVICE`
- `WILDLIFE_MODELS_DIR`
- `WILDLIFE_DETECTOR_MODEL_PATH`
- `WILDLIFE_CLASSIFIER_MODEL_PATH`
- `WILDLIFE_STORAGE_DIR`
- `WILDLIFE_YOLO_CONFIG_DIR`
- `WILDLIFE_CORS_ORIGINS`
- `WILDLIFE_MAX_VIDEO_FRAMES`
- `WILDLIFE_DEFAULT_CONFIDENCE_THRESHOLD`
- `WILDLIFE_DEFAULT_FRAME_INTERVAL_SECONDS`
- `WILDLIFE_SPECIES_CONFIDENCE_THRESHOLD`

## 已知边界

- 线上版不是完整真实模型推理，只是轻量演示版。
- 普通上传图片不能保证物种级分类准确。
- 本地 Amazon Rainforest 分类器不适合直接承诺中国本土物种级识别。
- 当前 88% 等数值在 fallback 模式下主要表示动物目标检测置信度，不代表物种分类置信度。
- 植物识别模型尚未接入，植物页目前是知识库和未来接口展示。
- 保护级别来自物种知识库关联，不代表模型能自动可靠判定物种保护等级。
- 不支持个体识别、年龄识别、性别识别。
- 视频分析为抽帧分析，尚未做同一动物跨帧去重。
- PDF 提取图片默认进入 `reference_species/待复核/`，未人工确认前不作为正式样本。

## 后续计划

### 短期

- 继续复核待复核图片，避免授权不明或物种不确定图片进入正式样本。
- 优化上传失败、空结果、低置信度结果和样本库筛选体验。
- 准备参赛/汇报材料，说明检测、候选分类、知识库、样本沉淀和人工复核闭环。

### 中期

- 接入更适合目标区域的动物分类模型。
- 把 `reference_species` 逐步扩充成训练集。
- 使用 `scripts/build_species_training_manifest.py` 生成清单，进入 `scripts/train_species_classifier.py` 的迁移学习流程。
- 接入植物识别模型或外部植物识别 API。
- 增加人工复核状态和样本修正记录。

### 长期

- 建立区域化物种清单。
- 支持同一动物跨帧去重。
- 支持批量视频回放分析。
- 支持自训练模型替换和样本沉淀。

## 项目定位

当前项目的定位是 MVP 演示平台：展示完整业务流程和可扩展架构，而不是已经完成的生产级物种识别系统。文档只描述当前已经实现或明确预留的能力，不对尚未完成的模型效果做承诺。

</details>
