from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.api_v1 import router as v1_router
from app.auth import bootstrap_admin
from app.database import initialize_database
from app.models.model_registry import ModelRegistry
from app.services.inference_service import InferenceService
from app.services.reference_retrieval_service import get_reference_retrieval_service
from app.services.result_store import ResultStore
from app.services.species_catalog_service import get_species_catalog_service
from app.settings import get_settings

settings = get_settings()
registry = ModelRegistry(settings)
store = ResultStore(settings.results_dir)
reference_retrieval_service = get_reference_retrieval_service()
species_catalog_service = get_species_catalog_service()
inference_service = InferenceService(settings, registry, store, reference_retrieval_service, species_catalog_service)

app = FastAPI(title="Wildlife Camera Trap Demo", version="0.1.0")

initialize_database()
bootstrap_admin()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media/uploads", StaticFiles(directory=settings.uploads_dir), name="uploads")
app.mount("/media/crops", StaticFiles(directory=settings.crops_dir), name="crops")
app.mount("/media/reference-species", StaticFiles(directory=settings.reference_species_dir), name="reference_species")
app.include_router(router)
app.include_router(v1_router)
