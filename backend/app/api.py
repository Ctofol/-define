from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.schemas import (
    AnalysisResponse,
    AssistantChatRequest,
    AssistantChatResponse,
    ReferenceLibraryResponse,
    ReferenceSpeciesEntry,
    SpeciesCatalogResponse,
    SpeciesEntry,
)
from app.services.inference_service import InferenceService
from app.services.ecology_assistant_service import EcologyAssistantService, get_ecology_assistant_service
from app.services.reference_sample_service import ReferenceSampleService, get_reference_sample_service
from app.services.species_catalog_service import SpeciesCatalogService, get_species_catalog_service
from app.settings import get_settings

router = APIRouter(prefix="/api")


def get_inference_service() -> InferenceService:
    from app.main import inference_service

    return inference_service


def get_reference_sample_service_dep() -> ReferenceSampleService:
    return get_reference_sample_service()


def get_species_catalog_service_dep() -> SpeciesCatalogService:
    return get_species_catalog_service()


def get_ecology_assistant_service_dep() -> EcologyAssistantService:
    return get_ecology_assistant_service()


@router.get("/health")
def health(service: InferenceService = Depends(get_inference_service)) -> dict[str, object]:
    settings = get_settings()
    assistant_mode = "deepseek" if settings.llm_api_key.strip() else "local_knowledge"
    assistant_detail = settings.llm_model if settings.llm_api_key.strip() else "local fallback"
    return {
        "status": "ok",
        "models": service.status(),
        "assistant": {
            "mode": assistant_mode,
            "detail": assistant_detail,
        },
    }


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


@router.get("/species", response_model=list[SpeciesEntry])
def list_species(
    recognition_tier: str | None = None,
    category: str | None = None,
    service: SpeciesCatalogService = Depends(get_species_catalog_service_dep),
) -> list[SpeciesEntry]:
    return service.list_species(recognition_tier=recognition_tier, category=category)


@router.get("/species-catalog", response_model=SpeciesCatalogResponse)
def list_species_catalog(
    category: str | None = None,
    service: SpeciesCatalogService = Depends(get_species_catalog_service_dep),
) -> SpeciesCatalogResponse:
    species = service.list_species(category=category)
    return SpeciesCatalogResponse(species_count=len(species), species=species)


@router.get("/species/{species_id}", response_model=SpeciesEntry)
def get_species(species_id: str, service: SpeciesCatalogService = Depends(get_species_catalog_service_dep)) -> SpeciesEntry:
    species = service.get_species(species_id)
    if species is None:
        raise HTTPException(status_code=404, detail="Species not found")
    return species


@router.get("/reference-samples", response_model=ReferenceLibraryResponse)
def list_reference_samples(service: ReferenceSampleService = Depends(get_reference_sample_service_dep)) -> ReferenceLibraryResponse:
    return service.list_species()


@router.get("/pdf-weak-reference-samples", response_model=ReferenceLibraryResponse)
def list_pdf_weak_reference_samples(service: ReferenceSampleService = Depends(get_reference_sample_service_dep)) -> ReferenceLibraryResponse:
    return service.list_pdf_weak_reference_species()


@router.get("/knowledge-open-set-samples", response_model=ReferenceLibraryResponse)
def list_knowledge_open_set_samples(service: ReferenceSampleService = Depends(get_reference_sample_service_dep)) -> ReferenceLibraryResponse:
    return service.list_knowledge_open_set_species()


@router.get("/reference-samples/{folder_name}", response_model=ReferenceSpeciesEntry)
def get_reference_samples(folder_name: str, service: ReferenceSampleService = Depends(get_reference_sample_service_dep)) -> ReferenceSpeciesEntry:
    species = service.get_species(folder_name)
    if species is None:
        raise HTTPException(status_code=404, detail="Reference samples not found")
    return species


@router.post("/assistant/chat", response_model=AssistantChatResponse)
def chat_with_ecology_assistant(
    request: AssistantChatRequest,
    service: EcologyAssistantService = Depends(get_ecology_assistant_service_dep),
) -> AssistantChatResponse:
    return service.chat(request)
