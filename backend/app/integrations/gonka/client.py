import asyncio
import json
import logging
from collections.abc import Mapping
from time import monotonic
from typing import Protocol

import httpx

from app.core.config import Settings
from app.core.exceptions import GonkaUnavailableError
from app.integrations.gonka.models import GonkaMessageResponse
from app.schemas.agentOutput import GonkaInferenceRecord, GonkaUsage

TRANSIENT_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
DEFAULT_RATE_LIMIT_DELAY_SECONDS = 30.0
MAX_RATE_LIMIT_DELAY_SECONDS = 60.0
logger = logging.getLogger(__name__)


def normalizeToolSchema(schema: Mapping[str, object]) -> dict[str, object]:
    """Inline local definitions and remove annotations rejected by some model adapters."""

    definitions = schema.get("$defs", {})
    if not isinstance(definitions, Mapping):
        definitions = {}

    def normalize(value: object, resolving: frozenset[str] = frozenset()) -> object:
        if isinstance(value, list):
            return [normalize(item, resolving) for item in value]
        if not isinstance(value, Mapping):
            return value

        reference = value.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            definitionName = reference.removeprefix("#/$defs/")
            definition = definitions.get(definitionName)
            if not isinstance(definition, Mapping) or definitionName in resolving:
                raise ValueError("Structured-output schema contains an invalid local reference.")
            mergedDefinition = dict(definition)
            mergedDefinition.update({key: item for key, item in value.items() if key != "$ref"})
            return normalize(mergedDefinition, resolving | {definitionName})

        return {
            key: normalize(item, resolving)
            for key, item in value.items()
            if key not in {"$defs", "title", "default"}
        }

    normalized = normalize(schema)
    if not isinstance(normalized, dict):  # pragma: no cover - Mapping always normalizes to dict
        raise ValueError("Structured-output schema must be an object.")
    return normalized


def providerErrorType(response: httpx.Response) -> str | None:
    """Return a bounded provider error category without logging its untrusted message/body."""

    try:
        payload = response.json()
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    error = payload.get("error")
    candidates: list[object] = []
    if isinstance(error, Mapping):
        candidates.extend((error.get("type"), error.get("code")))
    candidates.extend((payload.get("type"), payload.get("code")))
    for candidate in candidates:
        if (
            isinstance(candidate, str)
            and 1 <= len(candidate) <= 80
            and all(character.isalnum() or character in "._-" for character in candidate)
        ):
            return candidate
    return None


def normalizeGonkaBaseUrl(baseUrl: object) -> str:
    normalizedUrl = str(baseUrl).rstrip("/")
    if normalizedUrl.endswith("/v1"):
        return normalizedUrl[:-3]
    return normalizedUrl


def retryDelaySeconds(error: Exception, attempt: int) -> float:
    if isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 429:
        retryAfter = error.response.headers.get("Retry-After")
        if retryAfter is not None:
            try:
                retryAfterSeconds = float(str(retryAfter))
                return max(0.0, min(retryAfterSeconds, MAX_RATE_LIMIT_DELAY_SECONDS))
            except ValueError:
                pass
        return DEFAULT_RATE_LIMIT_DELAY_SECONDS
    return min(2.0**attempt, 4.0)


def inferencePolicy(settings: Settings, taskName: str) -> tuple[float, int]:
    if taskName in {"verifierModelA", "verifierModelB"}:
        return settings.GONKA_VERIFIER_TIMEOUT_SECONDS, settings.GONKA_VERIFIER_MAX_RETRIES
    if taskName in {"consensusJudge", "consensusRetry"}:
        return settings.GONKA_JUDGE_TIMEOUT_SECONDS, settings.GONKA_JUDGE_MAX_RETRIES
    if taskName in {"biasAudit", "biasAuditRetry"}:
        return settings.GONKA_AUDIT_TIMEOUT_SECONDS, settings.GONKA_AUDIT_MAX_RETRIES
    return settings.GONKA_TIMEOUT_SECONDS, settings.GONKA_MAX_RETRIES


class GonkaClientProtocol(Protocol):
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
    ) -> GonkaInferenceRecord: ...


class GonkaClient:
    """Typed async adapter for GonkaRouter's Anthropic-compatible Messages API."""

    def __init__(
        self,
        settings: Settings,
        httpClient: httpx.AsyncClient | None = None,
    ) -> None:
        if not settings.gonkaConfigured:
            raise GonkaUnavailableError("Gonka API key is not configured.")
        self.settings = settings
        self._ownsClient = httpClient is None
        self.httpClient = httpClient or httpx.AsyncClient(
            base_url=normalizeGonkaBaseUrl(settings.GONKA_BASE_URL),
            timeout=settings.GONKA_TIMEOUT_SECONDS,
            trust_env=False,
        )

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
        if maxTokens is not None and not 1024 <= maxTokens <= 4096:
            raise ValueError("Gonka maxTokens override must be between 1024 and 4096.")
        requestBody: dict[str, object] = {
            "model": model,
            "max_tokens": maxTokens or self.settings.GONKA_MAX_TOKENS,
            "temperature": 0,
            "system": systemPrompt,
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(inputPayload, ensure_ascii=False, separators=(",", ":")),
                }
            ],
        }
        structuredToolName = "submit_structured_output"
        if outputSchema is not None:
            requestBody["tools"] = [
                {
                    "name": structuredToolName,
                    "description": "Submit the complete result matching the required schema.",
                    "input_schema": normalizeToolSchema(outputSchema),
                }
            ]
            requestBody["tool_choice"] = {
                "type": "tool",
                "name": structuredToolName,
            }
        headers = {
            "x-api-key": self.settings.GONKA_API_KEY or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        startedAt = monotonic()
        lastError: Exception | None = None
        timeoutSeconds, maxRetries = inferencePolicy(self.settings, taskName)
        attempt = 0
        plainJsonFallbackUsed = False
        while attempt <= maxRetries:
            try:
                response = await self.httpClient.post(
                    "/v1/messages",
                    headers=headers,
                    json=requestBody,
                    timeout=timeoutSeconds,
                )
                if response.status_code in TRANSIENT_STATUS_CODES:
                    raise httpx.HTTPStatusError(
                        "Transient Gonka response.",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                parsedResponse = GonkaMessageResponse.model_validate(response.json())
                structuredBlocks = [
                    block
                    for block in parsedResponse.content
                    if block.type == "tool_use"
                    and block.name == structuredToolName
                    and block.input is not None
                ]
                if outputSchema is not None and len(structuredBlocks) == 1:
                    outputText = json.dumps(
                        structuredBlocks[0].input,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                elif outputSchema is not None and len(structuredBlocks) > 1:
                    outputText = ""
                else:
                    outputText = "".join(
                        block.text or "" for block in parsedResponse.content if block.type == "text"
                    ).strip()
                if not outputText and outputSchema is None:
                    raise GonkaUnavailableError("Gonka returned no text content.")

                usage = parsedResponse.usage
                return GonkaInferenceRecord(
                    taskName=taskName,
                    requestedModel=model,
                    servedModel=parsedResponse.model,
                    requestId=response.headers.get("X-Request-Id"),
                    providerResponseId=parsedResponse.id,
                    latencyMs=round((monotonic() - startedAt) * 1000),
                    usage=GonkaUsage(
                        inputTokens=usage.input_tokens if usage else None,
                        outputTokens=usage.output_tokens if usage else None,
                    ),
                    fallback=response.headers.get("X-Gonka-Fallback"),
                    stopReason=parsedResponse.stop_reason,
                    outputText=outputText,
                )
            except (httpx.RequestError, httpx.HTTPStatusError) as error:
                lastError = error
                statusCode = (
                    error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
                )
                providerRequestId = (
                    error.response.headers.get("X-Request-Id")
                    if isinstance(error, httpx.HTTPStatusError)
                    else None
                )
                errorType = (
                    providerErrorType(error.response)
                    if isinstance(error, httpx.HTTPStatusError)
                    else None
                )
                shouldUsePlainJsonFallback = (
                    outputSchema is not None
                    and isinstance(error, httpx.HTTPStatusError)
                    and error.response.status_code == 400
                    and "tools" in requestBody
                    and not plainJsonFallbackUsed
                )
                if shouldUsePlainJsonFallback:
                    plainJsonFallbackUsed = True
                    requestBody.pop("tools", None)
                    requestBody.pop("tool_choice", None)
                    logger.warning(
                        "Gonka structured output rejected requestId=%s taskName=%s model=%s "
                        "statusCode=400 providerRequestId=%s providerErrorType=%s "
                        "retryingWithoutTool=True",
                        applicationRequestId,
                        taskName,
                        model,
                        providerRequestId,
                        errorType,
                    )
                    continue
                isTransient = isinstance(error, httpx.RequestError) or (
                    error.response.status_code in TRANSIENT_STATUS_CODES
                )
                willRetry = isTransient and attempt < maxRetries
                log = logger.info if willRetry else logger.warning
                log(
                    "Gonka request failed requestId=%s taskName=%s model=%s attempt=%s "
                    "statusCode=%s providerRequestId=%s providerErrorType=%s errorType=%s "
                    "timeoutSeconds=%s willRetry=%s",
                    applicationRequestId,
                    taskName,
                    model,
                    attempt + 1,
                    statusCode,
                    providerRequestId,
                    errorType,
                    type(error).__name__,
                    timeoutSeconds,
                    willRetry,
                )
                if not willRetry:
                    break
                await asyncio.sleep(retryDelaySeconds(error, attempt))
                attempt += 1
            except GonkaUnavailableError:
                raise
            except Exception as error:
                raise GonkaUnavailableError("Gonka returned an invalid response shape.") from error

        raise GonkaUnavailableError("Gonka inference request failed.") from lastError

    async def close(self) -> None:
        if self._ownsClient:
            await self.httpClient.aclose()
