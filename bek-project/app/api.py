"""FastAPI-приложение: игровой эндпоинт, health-check и статический фронтенд."""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import settings
from app.pipeline import ProcessingPipeline
from app.schemas import PredictRequest, PredictResponse

logger = logging.getLogger(__name__)

pipeline: Optional[ProcessingPipeline] = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global pipeline
    logger.info("Инициализация пайплайна...")
    pipeline = ProcessingPipeline()
    logger.info("Пайплайн успешно инициализирован")
    yield
    await pipeline.aclose()
    pipeline = None


app = FastAPI(
    title="Prompt Injection Defense Service",
    description="Сервис для обучения защите от промпт-инъекций LLM",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/predict", response_model=PredictResponse)
async def predict(data: PredictRequest) -> PredictResponse:
    """Принимает level и text, возвращает text и passed (пароль угадан)."""
    if pipeline is None:
        return PredictResponse(text="Сервис временно недоступен. Пайплайн не инициализирован.", passed=False)

    result = await pipeline.process(text=data.text, level=data.level)
    return PredictResponse(text=result.text, passed=result.passed)


@app.get("/health")
def health_check():
    return {"status": "ok", "pipeline_ready": pipeline is not None}


if settings.STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")


@app.get("/")
def serve_frontend():
    index_path = settings.STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index_path)
