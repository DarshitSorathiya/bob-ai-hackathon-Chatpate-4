"""Standard API response envelope for MissionReady AI.

All responses follow the contract defined in docs/API.md:

  Success: { success: true, data: ..., meta: { request_id, timestamp }, error: null }
  Error:   { success: false, data: null, meta: ..., error: { code, message, details } }
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ResponseMeta(BaseModel):
    request_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiResponse(BaseModel):
    success: bool
    data: Any = None
    meta: ResponseMeta
    error: ErrorDetail | None = None

    @classmethod
    def ok(cls, data: Any, request_id: str) -> "ApiResponse":
        return cls(
            success=True,
            data=data,
            meta=ResponseMeta(request_id=request_id),
            error=None,
        )

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        request_id: str,
        details: dict[str, Any] | None = None,
    ) -> "ApiResponse":
        return cls(
            success=False,
            data=None,
            meta=ResponseMeta(request_id=request_id),
            error=ErrorDetail(code=code, message=message, details=details or {}),
        )


def make_response(data: Any, request_id: str) -> dict[str, Any]:
    """Convenience helper returning a plain dict for use as a FastAPI response body."""
    return ApiResponse.ok(data, request_id).model_dump()


def make_error(
    code: str,
    message: str,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ApiResponse.fail(code, message, request_id, details).model_dump()
