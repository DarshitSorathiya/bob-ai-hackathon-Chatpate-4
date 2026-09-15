"""
/api/v1/copilot — grounded AI query endpoint.

The LLM explains retrieved evidence; it does NOT decide readiness.
"""
from __future__ import annotations

from pydantic import BaseModel

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, DbSession
from app.core.responses import make_response
from app.services.copilot_service import CopilotService

router = APIRouter(prefix="/copilot", tags=["copilot"])

_copilot = CopilotService()


class CopilotQueryRequest(BaseModel):
    question: str
    asset_code: str | None = None


@router.post("/query", summary="Ask the grounded AI copilot a question")
def copilot_query(
    request: Request,
    db: DbSession,
    _user: CurrentUser,
    body: CopilotQueryRequest,
):
    """Query the copilot with a natural-language question.

    The copilot:
    - Detects intent and routes to backend tools.
    - Retrieves real DB data (no invented values).
    - Passes evidence to IBM watsonx.ai Granite for explanation.
    - Returns both the answer and full evidence list for transparency.

    If watsonx.ai is not configured, returns structured evidence without
    an LLM-generated explanation.
    """
    rid = request.headers.get("X-Request-ID", "")
    response = _copilot.query(db, body.question, asset_code=body.asset_code)

    return make_response({
        "query": response.query,
        "answer": response.answer,
        "model_used": response.model_used,
        "grounded": response.grounded,
        "evidence": [
            {
                "tool_name": e.tool_name,
                "query": e.query,
                "data": e.data,
                "error": e.error,
            }
            for e in response.evidence
        ],
    }, rid)
