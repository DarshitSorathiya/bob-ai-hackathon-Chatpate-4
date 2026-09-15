"""Health check endpoint — used for readiness probes and connectivity tests."""

from fastapi import APIRouter, Request

from app.core.responses import make_response

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check(request: Request) -> dict:
    """Returns 200 OK with the standard API envelope when the server is running."""
    request_id: str = request.headers.get("X-Request-ID", "")
    return make_response(data={"status": "ok"}, request_id=request_id)
