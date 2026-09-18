"""
CopilotService — grounded AI copilot backed by real backend data.

Architecture:
  1. Intent detection: route the query to the right backend tools.
  2. Tool execution: query real database records (NO invented values).
  3. Evidence assembly: build a structured context string.
  4. LLM call — provider priority:
       a) IBM watsonx.ai (WATSONX_API_KEY + WATSONX_PROJECT_ID)
       b) Groq           (GROQ_API_KEY) — automatic fallback
       c) "Service unavailable" — if neither key is present
     The model explains evidence; it does NOT invent readiness decisions.
  5. Evidence logging: every tool call and LLM response is logged.

The LLM is isolated from operational decisions:
  - It NEVER decides readiness (that is the ReadinessEngine).
  - It NEVER produces telemetry values (those come from the DB).
  - It ONLY explains retrieved evidence in natural language.

If neither provider is configured the copilot returns a clean
"service unavailable" message — no stack traces exposed to callers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.repositories.fleet_repository import AssetRepository
from app.repositories.operations_repository import (
    AlertRepository,
    MissionRepository,
    PredictionRepository,
    ReadinessRepository,
    WorkOrderRepository,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Evidence types
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Structured output from one backend tool call."""
    tool_name: str
    query: str
    data: Any
    error: str | None = None


@dataclass
class CopilotResponse:
    """Full response from the copilot for one query."""
    query: str
    answer: str
    evidence: list[ToolResult]
    model_used: str | None = None
    grounded: bool = True  # True = backed by real data


# ---------------------------------------------------------------------------
# Intent → tool mapping
# ---------------------------------------------------------------------------

_INTENT_PATTERNS: list[tuple[list[str], str]] = [
    (["fleet", "summary", "overview", "all assets", "how many"], "fleet_summary"),
    (["why", "risk", "readiness", "reason", "status", "not ready", "at risk", "unknown"], "asset_status"),
    (["rul", "remaining", "life", "prediction", "failure probability", "anomaly"], "asset_prediction"),
    (["maintenance", "work order", "repair", "overdue", "schedule"], "maintenance"),
    (["mission", "readiness", "go", "no-go", "gap", "capability"], "mission_readiness"),
    (["data quality", "stale", "sensor fault", "drift", "missing data"], "data_quality"),
    (["alert", "notification", "critical", "warning"], "alerts"),
]


def _detect_intent(query: str) -> str:
    q = query.lower()
    for patterns, intent in _INTENT_PATTERNS:
        if any(p in q for p in patterns):
            return intent
    return "fleet_summary"


# ---------------------------------------------------------------------------
# CopilotService
# ---------------------------------------------------------------------------

class CopilotService:
    """Grounded copilot service.

    Usage::

        svc = CopilotService()
        response = svc.query(db, "Why is AH-64-01 at risk?")
    """

    def __init__(self) -> None:
        self._asset_repo = AssetRepository()
        self._readiness_repo = ReadinessRepository()
        self._pred_repo = PredictionRepository()
        self._wo_repo = WorkOrderRepository()
        self._mission_repo = MissionRepository()
        self._alert_repo = AlertRepository()

    def query(self, db: Session, question: str, asset_code: str | None = None) -> CopilotResponse:
        """Answer a natural-language question backed by real DB data.

        Args:
            db:         Active database session.
            question:   The operator's question.
            asset_code: Optional hint to narrow tool selection.

        Returns:
            CopilotResponse with answer and full evidence list.
        """
        intent = _detect_intent(question)
        logger.info("copilot_query", intent=intent, question=question[:200])

        evidence: list[ToolResult] = []

        # Execute relevant tools
        if intent == "fleet_summary":
            evidence.append(self._tool_fleet_summary(db))
        elif intent in ("asset_status", "asset_prediction"):
            if asset_code:
                evidence.append(self._tool_asset_status(db, asset_code))
                evidence.append(self._tool_asset_prediction(db, asset_code))
            else:
                evidence.append(self._tool_fleet_summary(db))
        elif intent == "maintenance":
            if asset_code:
                evidence.append(self._tool_asset_maintenance(db, asset_code))
            else:
                evidence.append(self._tool_fleet_maintenance(db))
        elif intent == "mission_readiness":
            evidence.append(self._tool_fleet_summary(db))
            evidence.append(self._tool_active_missions(db))
        elif intent == "data_quality":
            evidence.append(self._tool_fleet_summary(db))
        elif intent == "alerts":
            evidence.append(self._tool_active_alerts(db))

        # Build context string from evidence
        context = self._build_context(question, evidence)

        # Call LLM — try watsonx, fall back to Groq, else unavailable
        settings = get_settings()
        if settings.copilot_llm_enabled:
            answer, model_used = self._call_llm(question, context, settings)
        else:
            answer = self._evidence_only_answer(evidence)
            model_used = None

        return CopilotResponse(
            query=question,
            answer=answer,
            evidence=evidence,
            model_used=model_used,
            grounded=True,
        )

    @staticmethod
    def _evidence_only_answer(evidence: list[ToolResult]) -> str:
        """Return deterministic guidance without inferring beyond evidence."""
        if not evidence:
            return "No operational evidence is available for this request."
        failed = [item.tool_name for item in evidence if item.error]
        if failed:
            return (
                "Some requested evidence could not be retrieved "
                f"({', '.join(failed)}). Review the returned records before acting."
            )
        return (
            "This response is evidence-only. Review the returned records for current "
            "telemetry, predictions, maintenance state, and deterministic readiness reasons. "
            "Do not treat this endpoint as a readiness decision."
        )

    # ------------------------------------------------------------------
    # Backend tools — all read from real DB
    # ------------------------------------------------------------------

    def _tool_fleet_summary(self, db: Session) -> ToolResult:
        try:
            all_readiness = self._readiness_repo.list(db)
            counts: dict[str, int] = {"READY": 0, "AT_RISK": 0, "NOT_READY": 0, "UNKNOWN": 0}
            for r in all_readiness:
                counts[r.status] = counts.get(r.status, 0) + 1
            total_assets = self._asset_repo.count(db)
            return ToolResult(
                tool_name="fleet_summary",
                query="Get fleet readiness counts",
                data={
                    "total_assets": total_assets,
                    "readiness_counts": counts,
                    "fleet_total_evaluated": len(all_readiness),
                },
            )
        except Exception as e:
            return ToolResult(tool_name="fleet_summary", query="Get fleet readiness counts", data=None, error=str(e))

    def _tool_asset_status(self, db: Session, asset_code: str) -> ToolResult:
        try:
            asset = self._asset_repo.get_by_code(db, asset_code)
            if not asset:
                return ToolResult(tool_name="asset_status", query=f"Get status for {asset_code}", data=None, error=f"Asset '{asset_code}' not found")
            import json
            rec = self._readiness_repo.get_for_asset(db, asset.id)
            factors = json.loads(rec.factors_json) if rec and rec.factors_json else []
            return ToolResult(
                tool_name="asset_status",
                query=f"Get readiness status for {asset_code}",
                data={
                    "asset_code": asset.asset_code,
                    "asset_type": asset.asset_type,
                    "total_hours": asset.total_hours,
                    "readiness_status": rec.status if rec else "UNKNOWN",
                    "primary_reason": rec.primary_reason if rec else "NO_PREDICTION_AVAILABLE",
                    "confidence": rec.confidence if rec else 0.0,
                    "contributing_factors": factors,
                    "evaluated_at": rec.evaluated_at.isoformat() if rec else None,
                },
            )
        except Exception as e:
            return ToolResult(tool_name="asset_status", query=f"Get status for {asset_code}", data=None, error=str(e))

    def _tool_asset_prediction(self, db: Session, asset_code: str) -> ToolResult:
        try:
            asset = self._asset_repo.get_by_code(db, asset_code)
            if not asset:
                return ToolResult(tool_name="asset_prediction", query=f"Get predictions for {asset_code}", data=None, error=f"Asset '{asset_code}' not found")
            rul = self._pred_repo.get_latest_for_asset(db, asset.id, "RUL")
            risk = self._pred_repo.get_latest_for_asset(db, asset.id, "FAILURE_RISK")
            anomaly = self._pred_repo.get_latest_for_asset(db, asset.id, "ANOMALY")
            return ToolResult(
                tool_name="asset_prediction",
                query=f"Get ML predictions for {asset_code}",
                data={
                    "asset_code": asset_code,
                    "rul_hours": rul.rul_estimate if rul else None,
                    "rul_lower": rul.rul_lower if rul else None,
                    "rul_upper": rul.rul_upper if rul else None,
                    "failure_probability": risk.failure_probability if risk else None,
                    "anomaly_score": anomaly.anomaly_score if anomaly else None,
                    "prediction_confidence": rul.confidence if rul else None,
                    "observation_count": rul.observation_count if rul else None,
                },
            )
        except Exception as e:
            return ToolResult(tool_name="asset_prediction", query=f"Get predictions for {asset_code}", data=None, error=str(e))

    def _tool_asset_maintenance(self, db: Session, asset_code: str) -> ToolResult:
        try:
            asset = self._asset_repo.get_by_code(db, asset_code)
            if not asset:
                return ToolResult(tool_name="asset_maintenance", query=f"Get maintenance for {asset_code}", data=None, error=f"Asset '{asset_code}' not found")
            wos = self._wo_repo.list(db, asset_id=asset.id, limit=10)
            return ToolResult(
                tool_name="asset_maintenance",
                query=f"Get open work orders for {asset_code}",
                data={
                    "asset_code": asset_code,
                    "open_work_orders": [
                        {"id": str(w.id), "title": w.title, "status": w.status, "urgency": w.urgency_level, "is_blocking": w.is_blocking}
                        for w in wos
                    ],
                    "blocking_count": sum(1 for w in wos if w.is_blocking),
                },
            )
        except Exception as e:
            return ToolResult(tool_name="asset_maintenance", query=f"Get maintenance for {asset_code}", data=None, error=str(e))

    def _tool_fleet_maintenance(self, db: Session) -> ToolResult:
        try:
            wos = self._wo_repo.list(db, status="OPEN", limit=20)
            return ToolResult(
                tool_name="fleet_maintenance",
                query="Get top open work orders across fleet",
                data={
                    "open_work_orders": len(wos),
                    "blocking": sum(1 for w in wos if w.is_blocking),
                    "items": [
                        {"asset_id": str(w.asset_id), "title": w.title, "urgency": w.urgency_level, "is_blocking": w.is_blocking}
                        for w in wos[:5]
                    ],
                },
            )
        except Exception as e:
            return ToolResult(tool_name="fleet_maintenance", query="Get fleet maintenance", data=None, error=str(e))

    def _tool_active_missions(self, db: Session) -> ToolResult:
        try:
            missions = self._mission_repo.list(db, limit=5)
            return ToolResult(
                tool_name="active_missions",
                query="List upcoming missions",
                data=[
                    {"mission_code": m.mission_code, "name": m.name, "status": m.status,
                     "duration_hours": m.duration_hours, "planned_start": m.planned_start.isoformat() if m.planned_start else None}
                    for m in missions
                ],
            )
        except Exception as e:
            return ToolResult(tool_name="active_missions", query="List missions", data=None, error=str(e))

    def _tool_active_alerts(self, db: Session) -> ToolResult:
        try:
            alerts = self._alert_repo.list(db, status="ACTIVE", limit=10)
            return ToolResult(
                tool_name="active_alerts",
                query="Get active alerts",
                data=[
                    {"id": str(a.id), "severity": a.severity, "title": a.title, "alert_type": a.alert_type}
                    for a in alerts
                ],
            )
        except Exception as e:
            return ToolResult(tool_name="active_alerts", query="Get alerts", data=None, error=str(e))

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_context(question: str, evidence: list[ToolResult]) -> str:
        """Build a structured context string from tool results."""
        import json
        parts = [f"QUESTION: {question}\n\nEVIDENCE FROM BACKEND DATABASE:"]
        for tool in evidence:
            parts.append(f"\n--- Tool: {tool.tool_name} ---")
            if tool.error:
                parts.append(f"ERROR: {tool.error}")
            elif tool.data is not None:
                parts.append(json.dumps(tool.data, indent=2, default=str))
            else:
                parts.append("No data returned.")
        parts.append(
            "\n\nINSTRUCTIONS: Answer the question using ONLY the evidence above. "
            "Do NOT invent telemetry values, predictions, or readiness decisions. "
            "If the evidence is insufficient, say so explicitly."
        )
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # LLM dispatch — watsonx.ai → Groq → unavailable
    # ------------------------------------------------------------------

    _SYSTEM_PROMPT = (
        "You are MissionReady Copilot, an AI assistant for military aviation maintenance operations. "
        "You ONLY explain information from the provided backend evidence. "
        "You NEVER invent sensor readings, predictions, or maintenance decisions."
    )

    @staticmethod
    def _call_llm(question: str, context: str, settings) -> tuple[str, str | None]:
        """Try watsonx.ai first, then Groq, then return a clean unavailable message.

        Returns (answer_text, model_id_used | None).
        No stack traces are ever surfaced to the caller.
        """
        # ── 1. IBM watsonx.ai ────────────────────────────────────────────
        if settings.watsonx_api_key and settings.watsonx_project_id:
            result = CopilotService._try_watsonx(context, settings)
            if result is not None:
                return result

        # ── 2. Groq fallback ─────────────────────────────────────────────
        if settings.groq_api_key:
            result = CopilotService._try_groq(context, settings)
            if result is not None:
                return result

        # ── 3. Neither provider available ────────────────────────────────
        if not settings.watsonx_api_key and not settings.groq_api_key:
            logger.info("copilot_no_llm_configured", msg="No LLM provider configured")
        else:
            logger.warning("copilot_all_providers_failed", msg="All configured LLM providers failed")

        return (
            "The AI copilot service is unavailable right now. "
            "Please try again later or contact your system administrator.",
            None,
        )

    @staticmethod
    def _try_watsonx(context: str, settings) -> tuple[str, str] | None:
        """Attempt a watsonx.ai call. Returns (answer, model_id) or None on any failure."""
        try:
            from ibm_watsonx_ai import Credentials
            from ibm_watsonx_ai.foundation_models import ModelInference
            from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

            credentials = Credentials(
                url=settings.watsonx_url,
                api_key=settings.watsonx_api_key,
            )
            model = ModelInference(
                model_id="ibm/granite-13b-instruct-v2",
                credentials=credentials,
                project_id=settings.watsonx_project_id,
                params={
                    GenParams.MAX_NEW_TOKENS: 512,
                    GenParams.TEMPERATURE: 0.1,
                    GenParams.REPETITION_PENALTY: 1.1,
                },
            )
            prompt = CopilotService._SYSTEM_PROMPT + "\n\n" + context
            response = model.generate_text(prompt=prompt)
            logger.info("copilot_llm_used", provider="watsonx", model="ibm/granite-13b-instruct-v2")
            return response, "ibm/granite-13b-instruct-v2"

        except ImportError:
            logger.warning("watsonx_sdk_not_installed", msg="ibm-watsonx-ai not installed; trying Groq fallback")
            return None
        except Exception as exc:
            logger.warning("watsonx_call_failed", exc_type=type(exc).__name__, msg="Trying Groq fallback")
            return None

    @staticmethod
    def _try_groq(context: str, settings) -> tuple[str, str] | None:
        """Attempt a Groq call. Returns (answer, model_id) or None on any failure."""
        try:
            from groq import Groq

            client = Groq(api_key=settings.groq_api_key)
            completion = client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": CopilotService._SYSTEM_PROMPT},
                    {"role": "user", "content": context},
                ],
                max_tokens=512,
                temperature=0.1,
            )
            answer = completion.choices[0].message.content or ""
            model_id = f"groq/{settings.groq_model}"
            logger.info("copilot_llm_used", provider="groq", model=settings.groq_model)
            return answer, model_id

        except ImportError:
            logger.warning("groq_sdk_not_installed", msg="groq package not installed")
            return None
        except Exception as exc:
            logger.warning("groq_call_failed", exc_type=type(exc).__name__, msg="Groq request failed")
            return None
