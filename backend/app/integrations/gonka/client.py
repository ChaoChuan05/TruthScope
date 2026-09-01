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
    ) -> GonkaInferenceRecord:
        requestBody = {
            "model": model,
            "max_tokens": self.settings.GONKA_MAX_TOKENS,
            "temperature": 0,
            "system": systemPrompt,
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(inputPayload, ensure_ascii=False, separators=(",", ":")),
                }
            ],
        }
        headers = {
            "x-api-key": self.settings.GONKA_API_KEY or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        startedAt = monotonic()
        lastError: Exception | None = None
        timeoutSeconds, maxRetries = inferencePolicy(self.settings, taskName)
        for attempt in range(maxRetries + 1):
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
                outputText = "".join(
                    block.text or "" for block in parsedResponse.content if block.type == "text"
                ).strip()
                if not outputText:
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
                    outputText=outputText,
                )
            except (httpx.RequestError, httpx.HTTPStatusError) as error:
                lastError = error
                statusCode = (
                    error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
                )
                logger.warning(
                    "Gonka request failed taskName=%s model=%s attempt=%s statusCode=%s "
                    "errorType=%s",
                    taskName,
                    model,
                    attempt + 1,
                    statusCode,
                    type(error).__name__,
                )
                isTransient = isinstance(error, httpx.RequestError) or (
                    error.response.status_code in TRANSIENT_STATUS_CODES
                )
                if not isTransient or attempt >= maxRetries:
                    break
                await asyncio.sleep(retryDelaySeconds(error, attempt))
            except GonkaUnavailableError:
                raise
            except Exception as error:
                raise GonkaUnavailableError("Gonka returned an invalid response shape.") from error

        raise GonkaUnavailableError("Gonka inference request failed.") from lastError

    async def close(self) -> None:
        if self._ownsClient:
            await self.httpClient.aclose()
