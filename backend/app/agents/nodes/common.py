from collections.abc import Awaitable, Callable, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.agents.state import VerificationGraphState
from app.schemas.agentOutput import GonkaInferenceRecord, WorkflowError
from app.schemas.evidence import EvidenceRecord

PROMPT_DIRECTORY = Path(__file__).resolve().parents[2] / "prompts"
# LangGraph's public node contract requires a dynamic partial-state dictionary.
type NodeUpdate = dict[str, Any]
type AsyncNode = Callable[[VerificationGraphState], Awaitable[NodeUpdate]]


@lru_cache
def loadPrompt(promptName: str) -> str:
    return (PROMPT_DIRECTORY / promptName).read_text(encoding="utf-8")


def inferenceMetadata(record: GonkaInferenceRecord) -> NodeUpdate:
    requestIds = [record.requestId] if record.requestId else []
    return {"inferenceRecords": [record], "gonkaRequestIds": requestIds}


def evidenceForModel(
    evidenceRecords: Sequence[EvidenceRecord],
    *,
    maxExcerptChars: int,
) -> list[dict[str, object]]:
    """Build bounded model input while preserving full evidence in graph/API state."""

    payloads: list[dict[str, object]] = []
    for record in evidenceRecords:
        payload: dict[str, object] = record.model_dump(mode="json")
        if len(record.excerpt) > maxExcerptChars:
            payload["excerpt"] = record.excerpt[:maxExcerptChars]
            payload["limitations"] = [
                *record.limitations,
                f"Model input excerpt capped at {maxExcerptChars} characters.",
            ]
        payloads.append(payload)
    return payloads


def workflowError(
    *,
    code: str,
    stage: str,
    message: str,
    retryable: bool,
) -> WorkflowError:
    return WorkflowError(code=code, stage=stage, message=message, retryable=retryable)
