from pydantic import BaseModel

from app.integrations.gonka.mapper import parseStructuredOutput


class ExampleOutput(BaseModel):
    value: str


def test_structuredOutput_acceptsProviderThinkBlockBeforeJson() -> None:
    output = '<think>Internal provider reasoning.</think>\n{"value":"accepted"}'
    parsed = parseStructuredOutput(output, ExampleOutput)
    assert parsed.value == "accepted"


def test_structuredOutput_acceptsJsonCodeFence() -> None:
    output = '```json\n{"value":"accepted"}\n```'
    parsed = parseStructuredOutput(output, ExampleOutput)
    assert parsed.value == "accepted"
