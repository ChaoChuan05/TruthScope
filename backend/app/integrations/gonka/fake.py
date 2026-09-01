import json
from collections import defaultdict, deque
from collections.abc import Mapping

from app.core.exceptions import GonkaUnavailableError
from app.schemas.agentOutput import GonkaInferenceRecord

type ScriptedValue = Mapping[str, object] | Exception


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
    ) -> GonkaInferenceRecord:
        del systemPrompt
        self.calls.append((taskName, inputPayload))
        self.callCounts[taskName] += 1
        taskResponses = self.responses.get(taskName)
        if not taskResponses:
            raise GonkaUnavailableError(f"No scripted response for {taskName}.")
        response = taskResponses.popleft()
        if isinstance(response, Exception):
            raise response
        requestId = f"fake-{taskName}-{self.callCounts[taskName]}"
        return GonkaInferenceRecord(
            taskName=taskName,
            requestedModel=model,
            servedModel=model,
            requestId=requestId,
            providerResponseId=f"message-{requestId}",
            latencyMs=0,
            outputText=json.dumps(response),
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
    ) -> GonkaInferenceRecord:
        del taskName, model, systemPrompt, inputPayload
        raise GonkaUnavailableError("Gonka API key is not configured.")
