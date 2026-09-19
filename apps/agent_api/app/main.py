"""Thin FastAPI entry point for health, readiness, and future chat APIs."""

from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Basic process health response."""

    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    """Service readiness response while dependencies are not configured."""

    status: Literal["not-ready"] = "not-ready"
    detail: str


class ChatRequest(BaseModel):
    """Typed request accepted by the future agent chat endpoint."""

    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1)
    user_id: str = Field(min_length=1)


class ChatResponse(BaseModel):
    """Placeholder response contract for future chat execution."""

    status: Literal["not-implemented"] = "not-implemented"
    detail: str


async def require_internal_service_authentication() -> None:
    """Fail closed until Django-to-FastAPI authentication is configured."""

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Internal service authentication is not configured.",
    )


InternalServiceAuth = Annotated[
    None,
    Depends(require_internal_service_authentication),
]

app = FastAPI(title="getnet-support Agent API", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report that the FastAPI process is running."""

    return HealthResponse()


@app.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
)
async def ready() -> ReadinessResponse:
    """Remain unready until required application dependencies are wired."""

    return ReadinessResponse(detail="RAG and internal authentication are not configured.")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, _: InternalServiceAuth) -> ChatResponse:
    """Reserve the authenticated chat boundary without executing an agent."""

    del request
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Chat execution is not implemented.",
    )

