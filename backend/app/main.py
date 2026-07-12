from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.models.model_registry import ModelRegistry
from app.services.inference_service import InferenceService
from app.services.result_store import ResultStore
from app.settings import get_settings

settings = get_settings()
registry = ModelRegistry(settings)
store = ResultStore(settings.results_dir)
inference_service = InferenceService(settings, registry, store)

app = FastAPI(title="Wildlife Camera Trap Demo", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media/uploads", StaticFiles(directory=settings.uploads_dir), name="uploads")
app.mount("/media/crops", StaticFiles(directory=settings.crops_dir), name="crops")
app.include_router(router)
