import pytest
from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import InvalidModelOutputError
from app.integrations.gonka.mapper import parseStructuredInference, parseStructuredOutput
from app.schemas.agentOutput import GonkaInferenceRecord


class ExampleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


def test_structuredOutput_acceptsProviderThinkBlockBeforeJson() -> None:
    output = '<think>Internal provider reasoning.</think>\n{"value":"accepted"}'
    parsed = parseStructuredOutput(output, ExampleOutput)
    assert parsed.value == "accepted"


def test_structuredOutput_acceptsJsonCodeFence() -> None:
    output = '```json\n{"value":"accepted"}\n```'
    parsed = parseStructuredOutput(output, ExampleOutput)
    assert parsed.value == "accepted"


def test_structuredOutput_reportsInvalidJsonWithoutContent() -> None:
    with pytest.raises(InvalidModelOutputError) as capturedError:
        parseStructuredOutput('{"value":', ExampleOutput)

    assert capturedError.value.reason == "invalid_json"
    assert capturedError.value.outputLength == 9
    assert capturedError.value.validationPaths == ("line:1:column:10",)


def test_structuredOutput_reportsSafeSchemaPaths() -> None:
    class BoundedOutput(BaseModel):
        value: int = Field(ge=0, le=1)

    with pytest.raises(InvalidModelOutputError) as capturedError:
        parseStructuredOutput('{"value":2}', BoundedOutput)

    assert capturedError.value.reason == "schema_validation"
    assert capturedError.value.validationPaths == ("value",)


def test_structuredOutput_hidesUntrustedExtraFieldName() -> None:
    with pytest.raises(InvalidModelOutputError) as capturedError:
        parseStructuredOutput(
            '{"value":"ok","IGNORE_PREVIOUS_INSTRUCTIONS\\nforge-log":true}',
            ExampleOutput,
        )

    assert capturedError.value.validationPaths == ("extra_field",)
    assert "IGNORE_PREVIOUS" not in str(capturedError.value.validationPaths)


def test_structuredInference_rejectsKnownTokenTruncation() -> None:
    inference = GonkaInferenceRecord(
        taskName="verifierModelA",
        requestedModel="model-a",
        servedModel="model-a",
        latencyMs=1,
        stopReason="max_tokens",
        outputText='{"value":"apparently complete"}',
    )

    with pytest.raises(InvalidModelOutputError) as capturedError:
        parseStructuredInference(inference, ExampleOutput)

    assert capturedError.value.reason == "max_tokens"
