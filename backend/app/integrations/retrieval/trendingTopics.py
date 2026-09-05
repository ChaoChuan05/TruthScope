from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.exceptions import RetrievalError


class NewsTopicsProviderProtocol(Protocol):
    async def fetchRecentTitles(self) -> list[str]: ...


class _BraveNewsResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=1000)


class _BraveNewsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results: list[_BraveNewsResult] = Field(default_factory=list)


class BraveNewsTopicsProvider:
    """Read Brave-ranked recent Malaysian news with one bounded provider request."""

    def __init__(
        self,
        *,
        apiKey: str,
        baseUrl: str = "https://api.search.brave.com",
        country: str = "MY",
        searchLanguage: str = "en",
        httpClient: httpx.AsyncClient | None = None,
    ) -> None:
        if not apiKey.strip():
            raise ValueError("Brave Search API key must not be blank.")
        self.apiKey = apiKey
        self.country = country
        self.searchLanguage = searchLanguage
        self._ownsClient = httpClient is None
        self.httpClient = httpClient or httpx.AsyncClient(
            base_url=baseUrl.rstrip("/"),
            timeout=10,
            trust_env=False,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": apiKey,
            },
        )

    async def fetchRecentTitles(self) -> list[str]:
        try:
            response = await self.httpClient.get(
                "/res/v1/news/search",
                headers={"X-Subscription-Token": self.apiKey},
                params={
                    "q": "Malaysia",
                    "count": 10,
                    "country": self.country,
                    "search_lang": self.searchLanguage,
                    "freshness": "pw",
                    "safesearch": "moderate",
                },
            )
            response.raise_for_status()
            parsedResponse = _BraveNewsResponse.model_validate(response.json())
        except (httpx.HTTPError, ValueError, ValidationError) as error:
            raise RetrievalError("Brave News Search request failed.") from error
        return [result.title for result in parsedResponse.results]

    async def close(self) -> None:
        if self._ownsClient:
            await self.httpClient.aclose()
