# 野外摄像头动植物识别 Demo

这是一个用于 MVP 展示的动植物识别平台 Demo，目标是演示野外摄像头图片/视频的分析流程：上传素材、检测画面中的动物目标、展示候选结果、查看知识卡片和历史记录。

当前项目分为两种运行状态：

- 本地真实模型版：本机可加载 MegaDetectorV6 和 Amazon Rainforest 分类器。
- 线上轻量演示版：部署在轻量服务器上，使用 fallback/mock 模式和内置示例映射，保证演示页面稳定可访问。

线上演示地址：

- 前端：`http://82.156.50.58:5002`
- 后端健康检查：`http://82.156.50.58:5001/api/health`

## 当前已实现

- React + Vite 多页面前端
- FastAPI 后端接口
- 图片上传分析
- 视频上传与抽帧分析接口
- 目标框、置信度、裁剪图、结果表格展示
- 本地 JSON 历史记录保存与回放
- 动物演示样本卡片
- 植物知识库页面
- 系统说明和能力边界页面
- 线上轻量部署版

## 页面结构

- `平台总览`：展示项目概览、模块入口和当前数据概况。
- `动物识别`：选择演示样本或上传素材，查看检测框、结果解读、会话摘要和知识卡片。
- `植物知识库`：展示 6 个植物知识卡片，以及采集优先级、识别重点和后续接入方向。
- `分析记录`：查看最近分析结果，支持切回动物识别页回放。
- `系统说明`：说明当前能力边界、模型状态和后续路线。

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
demo-fox.jpg         -> 狐狸
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

## API

- `GET /api/health`
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
- 不支持保护级别自动判断、个体识别、年龄识别、性别识别。
- 视频分析为抽帧分析，尚未做同一动物跨帧去重。

## 后续计划

### 短期

- 将前端结果文案进一步区分“检测置信度”和“分类置信度”。
- 增加稳定演示样本和一键演示流程。
- 优化上传失败、空结果、低置信度结果的提示。

### 中期

- 接入更适合目标区域的动物分类模型。
- 接入植物识别模型或外部植物识别 API。
- 建立物种知识库字段：中文名、拉丁名、形态特征、栖息地、保护等级、相似物种。
- 增加人工复核状态和样本修正记录。

### 长期

- 建立区域化物种清单。
- 支持同一动物跨帧去重。
- 支持批量视频回放分析。
- 支持自训练模型替换和样本沉淀。

## 项目定位

当前项目的定位是 MVP 演示平台：展示完整业务流程和可扩展架构，而不是已经完成的生产级物种识别系统。文档只描述当前已经实现或明确预留的能力，不对尚未完成的模型效果做承诺。
