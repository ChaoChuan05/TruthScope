import json
from collections import defaultdict, deque
from collections.abc import Mapping

from app.core.exceptions import GonkaUnavailableError
from app.schemas.agentOutput import GonkaInferenceRecord

type ScriptedValue = Mapping[str, object] | str | Exception


class ScriptedGonkaClient:
    """Deterministic fake that returns task-specific structured outputs in tests."""

    def __init__(self, responses: Mapping[str, list[ScriptedValue]]) -> None:
        self.responses = {
            taskName: deque(taskResponses) for taskName, taskResponses in responses.items()
        }
        self.calls: list[tuple[str, Mapping[str, object]]] = []
        self.callCounts: defaultdict[str, int] = defaultdict(int)

    async def infer(
        self,
        *,
        taskName: str,
        model: str,
        systemPrompt: str,
        inputPayload: Mapping[str, object],
        applicationRequestId: str | None = None,
        outputSchema: Mapping[str, object] | None = None,
        maxTokens: int | None = None,
    ) -> GonkaInferenceRecord:
        del systemPrompt, applicationRequestId, outputSchema, maxTokens
        self.calls.append((taskName, inputPayload))
        self.callCounts[taskName] += 1
        taskResponses = self.responses.get(taskName)
        if not taskResponses:
            raise GonkaUnavailableError(f"No scripted response for {taskName}.")
        response = taskResponses.popleft()
        if isinstance(response, Exception):
            raise response
        requestId = f"fake-{taskName}-{self.callCounts[taskName]}"
        outputText = response if isinstance(response, str) else json.dumps(response)
        return GonkaInferenceRecord(
            taskName=taskName,
            requestedModel=model,
            servedModel=model,
            requestId=requestId,
            providerResponseId=f"message-{requestId}",
            latencyMs=0,
            outputText=outputText,
        )


class UnavailableGonkaClient:
    """Safe runtime boundary used when Gonka credentials are absent."""

    async def infer(
        self,
        *,
        taskName: str,
        model: str,
        systemPrompt: str,
        inputPayload: Mapping[str, object],
        applicationRequestId: str | None = None,
        outputSchema: Mapping[str, object] | None = None,
        maxTokens: int | None = None,
    ) -> GonkaInferenceRecord:
        del (
            taskName,
            model,
            systemPrompt,
            inputPayload,
            applicationRequestId,
            outputSchema,
            maxTokens,
        )
        raise GonkaUnavailableError("Gonka API key is not configured.")
