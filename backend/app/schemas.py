from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class DetectionResult(BaseModel):
    media_id: str
    frame_time: float = Field(description="Seconds from the start of the media.")
    bbox: BoundingBox
    detected_type: str
    species_label: str
    confidence: float
    preview_crop_path: str


class AnalysisResponse(BaseModel):
    media_id: str
    media_type: str
    preview_url: str | None
    detections: list[DetectionResult]
    species_summary: dict[str, int]
    model_status: dict[str, str]
    message: str
