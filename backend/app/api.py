from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.schemas import AnalysisResponse
from app.services.inference_service import InferenceService
from app.settings import get_settings

router = APIRouter(prefix="/api")


def get_inference_service() -> InferenceService:
    from app.main import inference_service

    return inference_service


@router.get("/health")
def health(service: InferenceService = Depends(get_inference_service)) -> dict[str, object]:
    return {"status": "ok", "models": service.registry.status()}


@router.post("/analyze/image", response_model=AnalysisResponse)
async def analyze_image(
    file: UploadFile = File(...),
    confidence_threshold: float = Form(default_factory=lambda: get_settings().default_confidence_threshold),
    include_low_confidence: bool = Form(False),
    service: InferenceService = Depends(get_inference_service),
) -> AnalysisResponse:
    return await service.analyze_image(file, confidence_threshold, include_low_confidence)


@router.post("/analyze/video", response_model=AnalysisResponse)
async def analyze_video(
    file: UploadFile = File(...),
    confidence_threshold: float = Form(default_factory=lambda: get_settings().default_confidence_threshold),
    frame_interval_seconds: float = Form(default_factory=lambda: get_settings().default_frame_interval_seconds),
    include_low_confidence: bool = Form(False),
    service: InferenceService = Depends(get_inference_service),
) -> AnalysisResponse:
    return await service.analyze_video(file, confidence_threshold, frame_interval_seconds, include_low_confidence)


@router.get("/results/{media_id}", response_model=AnalysisResponse)
def get_result(media_id: str, service: InferenceService = Depends(get_inference_service)) -> AnalysisResponse:
    result = service.store.get(media_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


@router.get("/results", response_model=list[AnalysisResponse])
def list_results(service: InferenceService = Depends(get_inference_service)) -> list[AnalysisResponse]:
    return service.store.list_recent()
