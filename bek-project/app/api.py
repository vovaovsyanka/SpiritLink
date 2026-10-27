"""FastAPI-приложение: аккаунты, прогресс, свободный промпт, health-check и статический фронтенд."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, update

from app import auth, game, settings
from app.auth import CurrentUser, get_current_user
from app.db import SessionLocal, engine
from app.limits import check_attempt_limits, user_request_slot
from app.llm import LLMBusy
from app.models import Attempt, UserGameState, UserPass
from app.pipeline import ProcessingPipeline
from app.schemas import PredictRequest, PredictResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Инициализация пайплайна (загрузка BERT и языковых моделей, это занимает время)...")
    app.state.pipeline = await ProcessingPipeline.create()
    logger.info(
        "Пайплайн успешно инициализирован, уровни мира: %s", app.state.pipeline.available_world_levels
    )
    yield
    await app.state.pipeline.aclose()
    app.state.pipeline = None
    await engine.dispose()


app = FastAPI(
    title="Prompt Injection Defense Service",
    description="Сервис для обучения защите от промпт-инъекций LLM",
    version="2.0.0",
    lifespan=lifespan,
)

# Токен идёт в заголовке Authorization, cookie не используются — credentials не нужны
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(game.router)


@app.post("/predict", response_model=PredictResponse, tags=["game"])
async def predict(
    data: PredictRequest, request: Request, user: CurrentUser = Depends(get_current_user)
) -> PredictResponse:
    """
    Попытка в свободном промпте. Доступна в фазе free_prompt, с лимитами (429 + Retry-After).
    Если текст совпал со словом-якорем — passed=true, фаза становится done. Каждая попытка пишется в attempts.
    """
    pipeline: ProcessingPipeline | None = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Пайплайн не инициализирован")

    async with user_request_slot(user.id):
        # Короткая транзакция до LLM: соединение с БД не держим, пока ждём модель
        async with SessionLocal() as db:
            row = await db.get(UserPass, (user.id, data.pass_id))
            if row is None or row.phase != "free_prompt":
                raise HTTPException(status.HTTP_409_CONFLICT, "Свободный промпт этого уровня ещё не открыт")
            world_level = await db.scalar(
                select(UserGameState.world_level).where(UserGameState.user_id == user.id)
            ) or settings.DEFAULT_WORLD_LEVEL
            await check_attempt_limits(db, user.id)
            secret = row.secret

        start = time.perf_counter()
        try:
            result = await pipeline.process(
                text=data.text,
                category=settings.LEVEL_TO_CATEGORY[data.pass_id],
                secret=secret,
                world_level=world_level,
            )
        except LLMBusy as e:  # попытка не состоялась: в attempts не пишется и в лимит не идёт
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Сервер сейчас занят, попробуйте ещё раз",
                headers={"Retry-After": str(e.retry_after)},
            )
        latency_ms = round((time.perf_counter() - start) * 1000)

        async with SessionLocal() as db:
            db.add(Attempt(
                user_id=user.id,
                pass_id=data.pass_id,
                prompt_text=data.text,
                llm_response=result.llm_response,
                success=result.passed,
                classifier_output=result.trace,
                world_level=world_level,
                latency_ms=latency_ms,
            ))
            if result.passed:
                await db.execute(
                    update(UserPass)
                    .where(
                        UserPass.user_id == user.id,
                        UserPass.pass_id == data.pass_id,
                        UserPass.phase == "free_prompt",
                    )
                    .values(
                        phase="done",
                        completed_at=func.coalesce(UserPass.completed_at, func.now()),
                        used_secrets=func.array_append(UserPass.used_secrets, secret),
                    )
                )
            await db.commit()

    return PredictResponse(text=result.text, passed=result.passed)


@app.get("/health")
def health_check(request: Request):
    pipeline = getattr(request.app.state, "pipeline", None)
    return {"status": "ok", "pipeline_ready": pipeline is not None, **(pipeline.health() if pipeline else {})}


if settings.STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")


@app.get("/")
def serve_frontend():
    index_path = settings.STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index_path)
