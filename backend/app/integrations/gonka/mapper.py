import json
import re

from pydantic import BaseModel, ValidationError

from app.core.exceptions import InvalidModelOutputError
from app.schemas.agentOutput import GonkaInferenceRecord

CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
UNSAFE_PATH_CHARACTERS = re.compile(r"[^A-Za-z0-9_.:\[\]-]+")


def _safeValidationPath(location: tuple[object, ...]) -> str:
    rawPath = ".".join(str(part) for part in location)
    safePath = UNSAFE_PATH_CHARACTERS.sub("?", rawPath).strip(".")
    return (safePath or "unknown")[:160]


def parseStructuredOutput[ModelType: BaseModel](
    outputText: str,
    modelType: type[ModelType],
) -> ModelType:
    """Parse one JSON object and validate it against the requested schema."""

    withoutThinking = THINK_BLOCK_PATTERN.sub("", outputText).strip()
    cleanedText = CODE_FENCE_PATTERN.sub("", withoutThinking).strip()
    try:
        decoded = json.loads(cleanedText)
    except json.JSONDecodeError as error:
        raise InvalidModelOutputError(
            f"Model output failed {modelType.__name__} validation.",
            reason="invalid_json",
            validationPaths=(f"line:{error.lineno}:column:{error.colno}",),
            outputLength=len(outputText),
        ) from error

    if not isinstance(decoded, dict):
        raise InvalidModelOutputError(
            f"Model output failed {modelType.__name__} validation.",
            reason="wrong_top_level_type",
            outputLength=len(outputText),
        )

    try:
        return modelType.model_validate(decoded)
    except ValidationError as error:
        validationPaths = tuple(
            "extra_field" if item["type"] == "extra_forbidden" else _safeValidationPath(item["loc"])
            for item in error.errors(include_url=False, include_input=False)[:10]
        )
        raise InvalidModelOutputError(
            f"Model output failed {modelType.__name__} validation.",
            reason="schema_validation",
            validationPaths=validationPaths,
            outputLength=len(outputText),
        ) from error


def parseStructuredInference[ModelType: BaseModel](
    inference: GonkaInferenceRecord,
    modelType: type[ModelType],
) -> ModelType:
    """Reject known truncation before parsing one structured inference."""

    if inference.stopReason == "max_tokens":
        raise InvalidModelOutputError(
            f"Model output was truncated before {modelType.__name__} validation.",
            reason="max_tokens",
            outputLength=len(inference.outputText),
        )
    return parseStructuredOutput(inference.outputText, modelType)
