from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WILDLIFE_", env_file=".env", extra="ignore")

    detector_backend: str = Field(default="auto")
    classifier_backend: str = Field(default="auto")
    inference_device: str = Field(default="cpu")
    models_dir: Path = Field(default=Path("models"))
    detector_model_path: Path | None = Field(default=None)
    classifier_model_path: Path | None = Field(default=None)
    storage_dir: Path = Field(default=Path("storage"))
    yolo_config_dir: Path | None = Field(default=None)
    max_video_frames: int = Field(default=90)
    default_confidence_threshold: float = Field(default=0.35)
    default_frame_interval_seconds: float = Field(default=1.0)
    species_confidence_threshold: float = Field(default=0.65)
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

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
    if settings.yolo_config_dir and not settings.yolo_config_dir.is_absolute():
        settings.yolo_config_dir = (base_dir / settings.yolo_config_dir).resolve()

    settings.models_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.crops_dir.mkdir(parents=True, exist_ok=True)
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    settings.ultralytics_dir.mkdir(parents=True, exist_ok=True)
    return settings
