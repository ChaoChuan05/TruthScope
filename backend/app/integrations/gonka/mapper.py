import json
import re

from pydantic import BaseModel, ValidationError

from app.core.exceptions import InvalidModelOutputError

CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


def parseStructuredOutput[ModelType: BaseModel](
    outputText: str,
    modelType: type[ModelType],
) -> ModelType:
    """Parse one JSON object and validate it against the requested schema."""

    withoutThinking = THINK_BLOCK_PATTERN.sub("", outputText).strip()
    cleanedText = CODE_FENCE_PATTERN.sub("", withoutThinking).strip()
    try:
        decoded = json.loads(cleanedText)
        if not isinstance(decoded, dict):
            raise ValueError("Model output must be one JSON object.")
        return modelType.model_validate(decoded)
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        raise InvalidModelOutputError(
            f"Model output failed {modelType.__name__} validation."
        ) from error
