from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WILDLIFE_", env_file=".env", extra="ignore")

    detector_backend: str = Field(default="auto")
    classifier_backend: str = Field(default="bioclip")
    inference_device: str = Field(default="cpu")
    models_dir: Path = Field(default=Path("models"))
    detector_model_path: Path | None = Field(default=None)
    classifier_model_path: Path | None = Field(default=Path("models") / "species-classifier-local-v14-manual")
    storage_dir: Path = Field(default=Path("storage"))
    yolo_config_dir: Path | None = Field(default=None)
    max_video_frames: int = Field(default=90)
    default_confidence_threshold: float = Field(default=0.35)
    default_frame_interval_seconds: float = Field(default=1.0)
    species_confidence_threshold: float = Field(default=0.65)
    species_ready_threshold: float = Field(default=0.7)
    species_candidate_threshold: float = Field(default=0.45)
    retrieval_display_override_threshold: float = Field(default=0.35)
    retrieval_display_override_classifier_max_confidence: float = Field(default=0.65)
    retrieval_display_override_margin: float = Field(default=0.08)
    reference_retrieval_backend: str = Field(default="transformers")
    reference_embedding_model_path: Path | None = Field(default=Path("models") / "species-classifier-local-v14-manual")
    weak_reference_manifest_path: Path | None = Field(default=Path("reference_species") / "pdf_guangxi_species_images_v2" / "weak_reference_manifest.csv")
    weak_reference_max_confidence: float = Field(default=0.46)
    weak_reference_confidence_boost: float = Field(default=0.08)
    weak_reference_override_margin: float = Field(default=0.06)
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")
    llm_api_key: str = Field(default="")
    llm_base_url: str = Field(default="https://api.openai.com/v1/chat/completions")
    llm_model: str = Field(default="gpt-4o-mini")
    llm_timeout_seconds: float = Field(default=30.0)
    database_url: str = Field(default="sqlite:///runtime/platform.db")
    jwt_secret: str = Field(default="change-me-before-production")
    access_token_minutes: int = Field(default=30)
    refresh_token_days: int = Field(default=7)
    cookie_secure: bool = Field(default=False)
    bootstrap_admin_username: str = Field(default="admin")
    bootstrap_admin_password: str = Field(default="admin123")
    redis_url: str = Field(default="redis://localhost:6379/0")
    task_backend: str = Field(default="local")
    object_storage_endpoint: str = Field(default="http://localhost:9000")
    object_storage_bucket: str = Field(default="wildlife-media")
    object_storage_access_key: str = Field(default="wildlife")
    object_storage_secret_key: str = Field(default="wildlife-secret")
    object_storage_enabled: bool = Field(default=False)
    plant_recognition_enabled: bool = Field(default=False)
    multimodal_api_key: str = Field(default="")
    multimodal_base_url: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    multimodal_model: str = Field(default="qwen-vl-plus")
    multimodal_timeout_seconds: float = Field(default=45.0)
    multimodal_target_labels: str = Field(
        default="中华斑羚,中华穿山甲,大灵猫,梅花鹿,水鹿,猕猴,白头叶猴,豹猫,赤狐,野猪,黄喉貂,黑熊,未知动物"
    )
    bioclip_model_name: str = Field(default="hf-hub:imageomics/bioclip-2")
    bioclip_hf_endpoint: str = Field(default="https://hf-mirror.com")
    bioclip_min_confidence: float = Field(default=0.6)
    bioclip_min_margin: float = Field(default=0.08)
    bioclip_expand_catalog: bool = Field(default=True)
    bioclip_target_labels: str = Field(
        default=(
            "中华斑羚|Naemorhedus griseus,中华穿山甲|Manis pentadactyla,"
            "大灵猫|Viverra zibetha,梅花鹿|Cervus nippon,水鹿|Rusa unicolor,"
            "猕猴|Macaca mulatta,白头叶猴|Trachypithecus leucocephalus,"
            "豹猫|Prionailurus bengalensis,赤狐|Vulpes vulpes,野猪|Sus scrofa,"
            "黄喉貂|Martes flavigula,黑熊|Ursus thibetanus"
        )
    )

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def crops_dir(self) -> Path:
        return self.storage_dir / "crops"

    @property
    def results_dir(self) -> Path:
        return self.storage_dir / "results"

    @property
    def ultralytics_dir(self) -> Path:
        return self.yolo_config_dir or self.storage_dir / "ultralytics"

    @property
    def reference_species_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "reference_species"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    base_dir = Path(__file__).resolve().parents[2]

    if not settings.models_dir.is_absolute():
        settings.models_dir = (base_dir / settings.models_dir).resolve()
    if not settings.storage_dir.is_absolute():
        settings.storage_dir = (base_dir / settings.storage_dir).resolve()
    if settings.detector_model_path and not settings.detector_model_path.is_absolute():
        settings.detector_model_path = (base_dir / settings.detector_model_path).resolve()
    if settings.classifier_model_path and not settings.classifier_model_path.is_absolute():
        settings.classifier_model_path = (base_dir / settings.classifier_model_path).resolve()
    if settings.reference_embedding_model_path and not settings.reference_embedding_model_path.is_absolute():
        settings.reference_embedding_model_path = (base_dir / settings.reference_embedding_model_path).resolve()
    if settings.weak_reference_manifest_path and not settings.weak_reference_manifest_path.is_absolute():
        settings.weak_reference_manifest_path = (base_dir / settings.weak_reference_manifest_path).resolve()
    if settings.yolo_config_dir and not settings.yolo_config_dir.is_absolute():
        settings.yolo_config_dir = (base_dir / settings.yolo_config_dir).resolve()

    settings.models_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    settings.ultralytics_dir.mkdir(parents=True, exist_ok=True)
    return settings
