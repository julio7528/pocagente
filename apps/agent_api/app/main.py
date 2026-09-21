"""FastAPI process boundary over the completed Phase 9 application runtime."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from apps.agent_api.app.auth import (
    AuthenticatedPrincipal,
    ServiceAuthConfig,
    authenticate_internal_service,
    load_service_auth_config,
)
from apps.agent_api.app.chat import (
    ChatApplicationService,
    ChatAuthorizationError,
    ChatRequest,
    ChatResponse,
    ChatUnavailableError,
    SafeErrorDetail,
    SafeErrorResponse,
)
from apps.agent_api.app.composition import RuntimeComposition, compose_runtime


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["ready", "not-ready"]
    detail: str


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    payload = SafeErrorResponse(error=SafeErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def _chat_service(request: Request) -> ChatApplicationService:
    service: ChatApplicationService | None = getattr(request.app.state, "chat_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="APPLICATION_RUNTIME_UNAVAILABLE",
        )
    return service


ChatService = Annotated[ChatApplicationService, Depends(_chat_service)]
Principal = Annotated[AuthenticatedPrincipal, Depends(authenticate_internal_service)]


def create_app(
    *,
    chat_service: ChatApplicationService | None = None,
    auth_config: ServiceAuthConfig | None = None,
) -> FastAPI:
    """Build an app without opening database/provider resources at import time."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        runtime: RuntimeComposition | None = None
        application.state.chat_service = chat_service
        application.state.auth_config = auth_config
        application.state.readiness_detail = "Application dependencies are not configured."
        if application.state.auth_config is None:
            try:
                application.state.auth_config = load_service_auth_config()
            except RuntimeError:
                application.state.readiness_detail = "Internal service authentication is unavailable."
        if application.state.chat_service is None and application.state.auth_config is not None:
            try:
                runtime = await compose_runtime()
                application.state.chat_service = runtime.chat_service
                application.state.readiness_detail = "Application runtime is ready."
            except Exception:
                application.state.readiness_detail = "Application runtime dependencies are unavailable."
        elif application.state.chat_service is not None and application.state.auth_config is not None:
            application.state.readiness_detail = "Application runtime is ready."
        try:
            yield
        finally:
            if runtime is not None:
                await runtime.close()

    application = FastAPI(
        title="getnet-support Agent API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @application.exception_handler(RequestValidationError)
    async def validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
        return _error("INVALID_REQUEST", "The request body is invalid.", status.HTTP_422_UNPROCESSABLE_CONTENT)

    @application.exception_handler(HTTPException)
    async def http_error(_: Request, error: HTTPException) -> JSONResponse:
        code = error.detail if isinstance(error.detail, str) and error.detail.isupper() else "HTTP_REQUEST_REJECTED"
        message = {
            status.HTTP_401_UNAUTHORIZED: "Authentication is required or invalid.",
            status.HTTP_403_FORBIDDEN: "The authenticated principal is not authorized for this operation.",
            status.HTTP_503_SERVICE_UNAVAILABLE: "The application service is temporarily unavailable.",
        }.get(error.status_code, "The request could not be completed safely.")
        return _error(code, message, error.status_code)

    @application.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    @application.get("/ready", response_model=ReadinessResponse)
    async def ready(request: Request, response: Response) -> ReadinessResponse:
        is_ready = (
            getattr(request.app.state, "chat_service", None) is not None
            and getattr(request.app.state, "auth_config", None) is not None
        )
        if not is_ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="ready" if is_ready else "not-ready",
            detail=request.app.state.readiness_detail,
        )

    @application.post(
        "/chat",
        response_model=ChatResponse,
        responses={
            401: {"model": SafeErrorResponse},
            403: {"model": SafeErrorResponse},
            422: {"model": SafeErrorResponse},
            503: {"model": SafeErrorResponse},
        },
    )
    async def chat(
        request: ChatRequest,
        principal: Principal,
        service: ChatService,
    ) -> ChatResponse:
        try:
            return await service.handle(request, principal)
        except ChatAuthorizationError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="APPLICATION_OPERATION_FORBIDDEN",
            ) from None
        except ChatUnavailableError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ORCHESTRATION_UNAVAILABLE",
            ) from None
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="APPLICATION_RUNTIME_UNAVAILABLE",
            ) from None

    return application


app = create_app()
