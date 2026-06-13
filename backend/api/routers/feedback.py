"""
LangSmith Feedback router — ReasonSQL 2.0 Feature B

Provides a POST /feedback endpoint that annotates LangSmith traces
with user thumbs-up / thumbs-down feedback.

Why per-query feedback matters:
    - Builds a dataset of good/bad SQL generations automatically
    - LangSmith shows feedback annotations alongside traces
    - Feedback scores can be used to filter examples for fine-tuning
    - Free tier: 5k traces/month on LangSmith
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["Feedback"])
logger = logging.getLogger("reasonsql.feedback")

LANGSMITH_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"


# =============================================================================
# REQUEST / RESPONSE MODELS
# =============================================================================

class FeedbackRequest(BaseModel):
    """Request body for POST /feedback."""
    run_id: str = Field(..., description="LangSmith run ID from the query response")
    score: int = Field(..., ge=0, le=1, description="1 = thumbs up, 0 = thumbs down")
    comment: Optional[str] = Field(None, description="Optional user comment", max_length=500)


class FeedbackResponse(BaseModel):
    """Response for POST /feedback."""
    status: str
    message: str


# =============================================================================
# ENDPOINT
# =============================================================================

@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """
    Submit thumbs-up / thumbs-down feedback for a query result.

    When LangSmith tracing is enabled (LANGCHAIN_TRACING_V2=true),
    this annotates the run with a user_feedback score that appears
    in the LangSmith dashboard and dataset explorer.

    When LangSmith is disabled, feedback is logged locally (no-op).
    """
    label = "👍 helpful" if request.score == 1 else "👎 unhelpful"
    logger.info("Feedback received: run_id=%s score=%d (%s)", request.run_id, request.score, label)

    if not LANGSMITH_ENABLED:
        logger.info("LangSmith disabled — feedback logged locally only")
        return FeedbackResponse(
            status="logged",
            message="Feedback recorded locally (LangSmith tracing is disabled)"
        )

    try:
        from langsmith import Client
        ls_client = Client()
        ls_client.create_feedback(
            run_id=request.run_id,
            key="user_feedback",
            score=request.score,
            comment=request.comment or "",
        )
        logger.info("LangSmith feedback submitted: run_id=%s", request.run_id)
        return FeedbackResponse(
            status="submitted",
            message=f"Feedback submitted to LangSmith ({label})"
        )
    except Exception as exc:
        logger.warning("LangSmith feedback failed (non-critical): %s", exc)
        return FeedbackResponse(
            status="error",
            message=f"Failed to submit to LangSmith: {str(exc)[:100]}"
        )
