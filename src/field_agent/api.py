"""REST API. Run with: uvicorn field_agent.api:app"""

from __future__ import annotations

import hmac
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from . import __version__
from .actions import propose_actions
from .config import Settings
from .extraction import ExtractionFailed, Extractor
from .logging_setup import configure_logging
from .prompts import PROMPT_VERSION
from .providers.base import LLMProvider, ProviderRefused, ProviderUnavailable
from .providers.factory import build_provider
from .redact import fingerprint, redact
from .schemas import (
    ActionStatus,
    ExtractionResult,
    ExtractRequest,
    ExtractResponse,
    ProposedAction,
    ReviewRequest,
    UpdateRecord,
)
from .store import AlreadyReviewed, NotFound, Store


def create_app(settings: Settings | None = None, provider: LLMProvider | None = None, store: Store | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging()
    provider = provider or build_provider(settings)
    store = store or Store(settings.database_path)
    extractor = Extractor(provider, max_message_chars=settings.max_message_chars)
    if settings.api_key is None:
        logging.getLogger("field_agent").warning(
            "api_unauthenticated",
            extra={"detail": "AGENT_API_KEY is not set; /v1 endpoints are open. Set it for any shared deployment."},
        )

    app = FastAPI(
        title="Field Update AI Agent (prototype)",
        version=__version__,
        description="Turns unstructured construction site updates into validated structured data. "
        "Every proposed action requires human approval. Nothing is ever sent automatically.",
    )
    app.state.store = store
    app.state.provider = provider

    def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
        if settings.api_key is None:
            return
        if x_api_key is None or not hmac.compare_digest(x_api_key, settings.api_key):
            raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key")

    auth = [Depends(require_api_key)]

    @app.exception_handler(ExtractionFailed)
    async def _extraction_failed(_: Request, exc: ExtractionFailed) -> JSONResponse:
        return JSONResponse(status_code=502, content={"error": "extraction_failed", "detail": str(exc)[:500]})

    @app.exception_handler(ProviderUnavailable)
    async def _unavailable(_: Request, exc: ProviderUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"error": "provider_unavailable", "detail": str(exc)})

    @app.exception_handler(ProviderRefused)
    async def _refused(_: Request, exc: ProviderRefused) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": "provider_refused", "detail": str(exc)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "provider": provider.name, "model": provider.model, "prompt_version": PROMPT_VERSION}

    @app.get("/v1/schema/extraction", dependencies=auth)
    def extraction_schema() -> dict:
        return ExtractionResult.model_json_schema()

    @app.post("/v1/extract", response_model=ExtractResponse, dependencies=auth)
    def extract(body: ExtractRequest) -> ExtractResponse:
        """Stateless extraction. Nothing is stored and no actions are proposed."""
        outcome = extractor.extract(body.message, body.project_hint, body.sender_role, body.received_on, body.schedule_context)
        return ExtractResponse(
            request_id=outcome.request_id,
            extraction=outcome.final,
            guardrails=outcome.report,
            conflicts=outcome.conflicts,
            provider=outcome.provider,
            model=outcome.model,
            latency_ms=outcome.latency_ms,
        )

    @app.post("/v1/updates", response_model=UpdateRecord, status_code=201, dependencies=auth)
    def create_update(body: ExtractRequest) -> UpdateRecord:
        """Extract, store the update, and queue proposed actions for human approval."""
        outcome = extractor.extract(body.message, body.project_hint, body.sender_role, body.received_on, body.schedule_context)
        return store.save_update(
            message=outcome.message if settings.store_raw_messages else redact(outcome.message),
            message_fingerprint=fingerprint(outcome.message),
            extraction=outcome.final,
            guardrails=outcome.report,
            provider=outcome.provider,
            model=outcome.model,
            actions=propose_actions(outcome.final, outcome.conflicts),
            conflicts=outcome.conflicts,
        )

    @app.get("/v1/updates/{update_id}", response_model=UpdateRecord, dependencies=auth)
    def get_update(update_id: str) -> UpdateRecord:
        try:
            return store.get_update(update_id)
        except NotFound:
            raise HTTPException(status_code=404, detail="Update not found") from None

    @app.get("/v1/actions", response_model=list[ProposedAction], dependencies=auth)
    def list_actions(
        status: ActionStatus | None = None, limit: Annotated[int, Query(ge=1, le=500)] = 100
    ) -> list[ProposedAction]:
        return store.list_actions(status, limit)

    def _review(action_id: str, decision: ActionStatus, body: ReviewRequest) -> ProposedAction:
        try:
            return store.review(action_id, decision, body.reviewer, body.note)
        except NotFound:
            raise HTTPException(status_code=404, detail="Action not found") from None
        except AlreadyReviewed:
            raise HTTPException(status_code=409, detail="Action has already been reviewed") from None

    @app.post("/v1/actions/{action_id}/approve", response_model=ProposedAction, dependencies=auth)
    def approve(action_id: str, body: ReviewRequest) -> ProposedAction:
        """A person approves the action. It is written to the outbox; this prototype never sends anything."""
        return _review(action_id, ActionStatus.approved, body)

    @app.post("/v1/actions/{action_id}/reject", response_model=ProposedAction, dependencies=auth)
    def reject(action_id: str, body: ReviewRequest) -> ProposedAction:
        return _review(action_id, ActionStatus.rejected, body)

    return app


def __getattr__(name: str):
    # `uvicorn field_agent.api:app` builds the app lazily from the environment,
    # so importing this module in tests has no side effects.
    if name == "app":
        return create_app()
    raise AttributeError(name)
