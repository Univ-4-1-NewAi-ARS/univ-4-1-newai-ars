from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agents.answer_analyzer import AnswerAnalyzer
from app.core.settings import Settings, get_settings
from app.models import (
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    HealthResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionSummaryResponse,
)
from app.providers.llm_router import LLMRouter
from app.providers.speech import build_stt_provider, build_tts_provider
from app.repositories.factory import build_repository
from app.survey_loader import SurveyLoader
from app.services.orchestrator import OrchestratorService


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    repository = build_repository(resolved_settings)
    survey_loader = SurveyLoader(resolved_settings.survey_dir)
    llm_router = LLMRouter(resolved_settings)
    answer_analyzer = AnswerAnalyzer(settings=resolved_settings, router=llm_router)
    service = OrchestratorService(
        settings=resolved_settings,
        repository=repository,
        survey_loader=survey_loader,
        answer_analyzer=answer_analyzer,
        stt_provider=build_stt_provider(resolved_settings),
        tts_provider=build_tts_provider(resolved_settings),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await repository.connect()
        await repository.ensure_schema()
        app.state.settings = resolved_settings
        app.state.repository = repository
        app.state.service = service
        yield
        await repository.close()

    app = FastAPI(title="AI Orchestrator", version="0.1.0", lifespan=lifespan)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service="ai-orchestrator", repository=resolved_settings.repository_provider)

    @app.post("/sessions", response_model=SessionCreateResponse, status_code=201)
    async def create_session(request: SessionCreateRequest) -> SessionCreateResponse:
        return await service.start_session(request)

    @app.post("/sessions/{session_id}/answers", response_model=AnswerSubmitResponse)
    async def submit_answer(session_id: str, request: AnswerSubmitRequest) -> AnswerSubmitResponse:
        return await service.submit_answer(session_id, request)

    @app.get("/sessions/{session_id}/summary", response_model=SessionSummaryResponse)
    async def get_summary(session_id: str) -> SessionSummaryResponse:
        return await service.get_summary(session_id)

    return app


app = create_app()
