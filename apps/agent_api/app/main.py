"""FastAPI process boundary over the completed Phase 9 application runtime."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, AsyncIterator, Literal, Protocol

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from apps.agent_api.app.auth import (
    AuthenticatedPrincipal,
    PrincipalRole,
    ServiceAuthConfig,
    authenticate_internal_admin,
    authenticate_internal_service,
    load_service_auth_config,
)
from apps.agent_api.app.agents.human_escalation import (
    ConversationReference,
    HandoffFact,
    HandoffInference,
    HandoffPackage,
    HumanEscalationAction,
    HumanEscalationAgent,
    HumanEscalationReason,
    HumanEscalationRequest,
    HumanEscalationResult,
    HumanEscalationState,
    HumanEscalationStatus,
    SupportOperatorAuthorization,
)
from apps.agent_api.app.chat import ChatHandoffPackage
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
from apps.agent_api.app.security.dashboard_models import (
    SecurityDashboardBreakdowns,
    SecurityDashboardDay,
    SecurityDashboardEventDetail,
    SecurityDashboardEventPage,
    SecurityDashboardFilters,
    SecurityDashboardPage,
    SecurityDashboardSummary,
)
from apps.agent_api.app.security.dashboard_service import (
    SecurityDashboardEventMissing,
    SecurityDashboardService,
    SecurityDashboardServiceContract,
    SecurityDashboardUnavailable,
)
from apps.agent_api.app.security.models import SecurityEventType
from apps.agent_api.app.telemetry import RuntimeTelemetrySink


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["ready", "not-ready"]
    detail: str


class HandoffTransitionRequest(BaseModel):
    """Narrow internal transition contract; actor claims come from auth headers."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    conversation_id: str = Field(min_length=1, max_length=128)
    current_state: HumanEscalationState
    action: Literal[
        HumanEscalationAction.CONFIRM,
        HumanEscalationAction.ACCEPT,
        HumanEscalationAction.RESOLVE,
    ]
    reason: HumanEscalationReason | None = None
    handoff: ChatHandoffPackage | None = None
    active_operator_id: str | None = Field(default=None, min_length=1, max_length=128)


class HumanTransitionCapability(Protocol):
    def transition(self, request: HumanEscalationRequest) -> HumanEscalationResult: ...


def _handoff_package(value: ChatHandoffPackage | None, conversation_id: str) -> HandoffPackage | None:
    if value is None:
        return None
    if value.conversation_id != conversation_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="HANDOFF_CONVERSATION_MISMATCH")
    return HandoffPackage(
        conversation=ConversationReference(conversation_id=conversation_id),
        reason=value.reason,
        problem_summary=value.problem_summary,
        protocol_reference=value.protocol_reference,
        run_reference=value.run_reference,
        observed_operational_state=value.observed_operational_state,
        last_successful_stage=value.last_successful_stage,
        failure_stage=value.failure_stage,
        sanitized_error=value.sanitized_error,
        timeline=value.timeline,
        facts=tuple(HandoffFact(source=item.source, statement=item.statement) for item in value.facts),
        inferences=tuple(HandoffInference(statement=item.statement) for item in value.inferences),
        user_confirmation=value.user_confirmation,
    )


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
AdminPrincipal = Annotated[AuthenticatedPrincipal, Depends(authenticate_internal_admin)]


def _audit_dashboard_service(request: Request) -> SecurityDashboardServiceContract:
    service: SecurityDashboardServiceContract | None = getattr(
        request.app.state, "audit_dashboard_service", None
    )
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUDIT_DASHBOARD_UNAVAILABLE",
        )
    return service


AuditDashboardService = Annotated[
    SecurityDashboardServiceContract,
    Depends(_audit_dashboard_service),
]


def _audit_dashboard_filters(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    event_type: SecurityEventType | None = Query(default=None),
    source_component: str | None = Query(default=None, max_length=128),
    user_identifier: str | None = Query(default=None, max_length=128),
) -> SecurityDashboardFilters:
    try:
        return SecurityDashboardFilters(
            date_from=date_from,
            date_to=date_to,
            event_type=event_type,
            source_component=source_component,
            user_identifier=user_identifier,
        )
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="INVALID_AUDIT_FILTERS",
        ) from None


AuditDashboardFilters = Annotated[
    SecurityDashboardFilters,
    Depends(_audit_dashboard_filters),
]


def create_app(
    *,
    chat_service: ChatApplicationService | None = None,
    auth_config: ServiceAuthConfig | None = None,
    telemetry_sink: RuntimeTelemetrySink | None = None,
    human_escalation_agent: HumanTransitionCapability | None = None,
    audit_dashboard_service: SecurityDashboardServiceContract | None = None,
) -> FastAPI:
    """Build an app without opening database/provider resources at import time."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        runtime: RuntimeComposition | None = None
        application.state.chat_service = chat_service
        application.state.auth_config = auth_config
        application.state.telemetry_sink = telemetry_sink
        application.state.human_escalation_agent = human_escalation_agent or HumanEscalationAgent()
        application.state.audit_dashboard_service = audit_dashboard_service
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
                application.state.audit_dashboard_service = (
                    application.state.audit_dashboard_service
                    or SecurityDashboardService(runtime.database)
                )
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
        http_request: Request,
        chat_request: ChatRequest,
        principal: Principal,
        service: ChatService,
    ) -> ChatResponse:
        if principal.role is PrincipalRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CHAT_ROLE_FORBIDDEN",
            )
        try:
            return await service.handle(
                chat_request,
                principal,
                telemetry_sink=getattr(http_request.app.state, "telemetry_sink", None),
            )
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

    @application.get(
        "/internal/admin/audit/summary",
        response_model=SecurityDashboardSummary,
    )
    async def audit_dashboard_summary(
        filters: AuditDashboardFilters,
        _principal: AdminPrincipal,
        service: AuditDashboardService,
    ) -> SecurityDashboardSummary:
        try:
            return await service.summary(filters)
        except SecurityDashboardUnavailable:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AUDIT_DASHBOARD_UNAVAILABLE",
            ) from None

    @application.get(
        "/internal/admin/audit/timeseries",
        response_model=tuple[SecurityDashboardDay, ...],
    )
    async def audit_dashboard_timeseries(
        filters: AuditDashboardFilters,
        _principal: AdminPrincipal,
        service: AuditDashboardService,
    ) -> tuple[SecurityDashboardDay, ...]:
        try:
            return await service.timeseries(filters)
        except SecurityDashboardUnavailable:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AUDIT_DASHBOARD_UNAVAILABLE",
            ) from None

    @application.get(
        "/internal/admin/audit/breakdowns",
        response_model=SecurityDashboardBreakdowns,
    )
    async def audit_dashboard_breakdowns(
        filters: AuditDashboardFilters,
        _principal: AdminPrincipal,
        service: AuditDashboardService,
    ) -> SecurityDashboardBreakdowns:
        try:
            return await service.breakdowns(filters)
        except SecurityDashboardUnavailable:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AUDIT_DASHBOARD_UNAVAILABLE",
            ) from None

    @application.get(
        "/internal/admin/audit/events",
        response_model=SecurityDashboardEventPage,
    )
    async def audit_dashboard_events(
        filters: AuditDashboardFilters,
        _principal: AdminPrincipal,
        service: AuditDashboardService,
        page: int = Query(default=1, ge=1, le=1000),
        page_size: int = Query(default=25, ge=1, le=100),
    ) -> SecurityDashboardEventPage:
        try:
            return await service.events(filters, SecurityDashboardPage(page=page, page_size=page_size))
        except SecurityDashboardUnavailable:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AUDIT_DASHBOARD_UNAVAILABLE",
            ) from None

    @application.get(
        "/internal/admin/audit/events/{event_id}",
        response_model=SecurityDashboardEventDetail,
    )
    async def audit_dashboard_event_detail(
        event_id: Annotated[int, Path(ge=1)],
        _principal: AdminPrincipal,
        service: AuditDashboardService,
    ) -> SecurityDashboardEventDetail:
        try:
            return await service.event_detail(event_id)
        except SecurityDashboardEventMissing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AUDIT_EVENT_NOT_FOUND",
            ) from None
        except SecurityDashboardUnavailable:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AUDIT_DASHBOARD_UNAVAILABLE",
            ) from None

    @application.post(
        "/internal/human-escalation/transition",
        response_model=HumanEscalationResult,
        responses={401: {"model": SafeErrorResponse}, 403: {"model": SafeErrorResponse}, 409: {"model": SafeErrorResponse}, 422: {"model": SafeErrorResponse}, 503: {"model": SafeErrorResponse}},
    )
    async def human_escalation_transition(
        body: HandoffTransitionRequest,
        request: Request,
        principal: Principal,
    ) -> HumanEscalationResult:
        action = body.action
        if action is HumanEscalationAction.CONFIRM:
            if principal.role is not PrincipalRole.CLIENT:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HANDOFF_ACTOR_FORBIDDEN")
        elif principal.role is not PrincipalRole.SUPPORT_AGENT:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HANDOFF_ACTOR_FORBIDDEN")
        try:
            package = _handoff_package(body.handoff, body.conversation_id)
        except ValidationError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="INVALID_HANDOFF_PACKAGE") from None
        if action in {HumanEscalationAction.CONFIRM, HumanEscalationAction.ACCEPT} and package is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="HANDOFF_PACKAGE_REQUIRED")
        if action is HumanEscalationAction.RESOLVE and package is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="HANDOFF_PACKAGE_NOT_ALLOWED")
        if action is HumanEscalationAction.RESOLVE and not body.active_operator_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="ACTIVE_OPERATOR_REQUIRED")
        if action is not HumanEscalationAction.RESOLVE and body.active_operator_id is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="ACTIVE_OPERATOR_NOT_ALLOWED")
        operator = (
            SupportOperatorAuthorization(operator_id=principal.user_id, is_support_agent=True)
            if principal.role is PrincipalRole.SUPPORT_AGENT
            else None
        )
        try:
            transition = HumanEscalationRequest(
                conversation=ConversationReference(conversation_id=body.conversation_id),
                current_state=body.current_state,
                action=action,
                reason=body.reason,
                handoff_package=package,
                explicit_user_confirmation=(action is HumanEscalationAction.CONFIRM),
                operator=operator,
                active_operator_id=body.active_operator_id,
            )
        except ValidationError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="INVALID_TRANSITION_REQUEST") from None
        agent: HumanTransitionCapability | None = getattr(request.app.state, "human_escalation_agent", None)
        if agent is None:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="HUMAN_TRANSITION_UNAVAILABLE")
        try:
            result = agent.transition(transition)
        except Exception:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="HUMAN_TRANSITION_UNAVAILABLE") from None
        if result.status is HumanEscalationStatus.REJECTED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="HUMAN_TRANSITION_REJECTED")
        if result.conversation.conversation_id != body.conversation_id:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="HUMAN_TRANSITION_INVALID_RESULT")
        return result

    return application


app = create_app()
