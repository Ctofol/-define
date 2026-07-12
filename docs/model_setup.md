# 真实模型接入说明

当前项目已经有模型接入点。没有真实依赖或权重时，后端会自动使用 fallback 模型，保证 Demo 可启动。

## 1. 检查当前环境

```powershell
.\scripts\check_env.ps1
```

重点看：

- `PytorchWildlife` 是否存在
- `transformers` 是否存在
- `torch` 是否存在
- `models/megadetector` 和 `models/species-classifier` 是否存在
- `YOLO_CONFIG_DIR` 会被项目重定向到 `storage/ultralytics`，避免 Ultralytics 写入系统用户目录

## 2. 安装真实模型依赖

推荐使用项目脚本：

```powershell
.\scripts\install_models.ps1
```

这个脚本会分步安装 `transformers`、`torch`、`PytorchWildlife` 和导入依赖，并尽量避免覆盖已有 OpenCV。

也可以手动安装：

```powershell
cd backend
python -m pip install -r requirements-models.txt
```

如果安装 `torch` 很慢或失败，建议按照 PyTorch 官网选择 CPU/GPU 对应命令安装，再安装 `transformers` 和 `PytorchWildlife`。

如果在 Windows/Anaconda 中遇到 `cv2.pyd` 权限错误，不要强行覆盖 OpenCV；使用 `scripts/install_models.ps1` 的分步安装方式。

## 3. 放置模型文件

推荐目录：

```text
models/
  megadetector/
    md_v6.pt
  species-classifier/
    amazon_v2.ckpt
```

也可以复制 `backend/.env.example` 为 `backend/.env`，用环境变量指定模型路径：

```text
WILDLIFE_DETECTOR_MODEL_PATH=models/megadetector/md_v6.pt
WILDLIFE_CLASSIFIER_MODEL_PATH=models/species-classifier/amazon_v2.ckpt
```

## 4. 切换后端模式

默认建议：

```text
WILDLIFE_DETECTOR_BACKEND=auto
WILDLIFE_CLASSIFIER_BACKEND=auto
```

验证真实模型是否接入：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

如果返回里仍然是 `fallback-detector` 或 `fallback-classifier`，说明真实依赖或模型路径还没有被后端成功加载。`detector_detail` 和 `classifier_detail` 会给出 fallback 原因。

## 5. 建议接入顺序

1. 先接 MegaDetector，只确认动物检测框是否可信。
2. 再接物种分类器，只对检测框裁剪图分类。
3. 最后用你准备的 10-30 张测试素材调阈值。

不要一开始就追求很多类别。首版更适合先覆盖鹿、野猪、狐狸、兔、鸟类、松鼠、未知动物等常见类别。

注意：MegaDetector 只判断 `animal/person/vehicle` 和目标框，不负责精确物种名。没有 `models/species-classifier/amazon_v2.ckpt` 时，系统会显示“未分类动物”，不会冒充鹿、野猪等具体物种。
