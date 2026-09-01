import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field

import httpx
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, ValidationError

from app.core.exceptions import RetrievalError
from app.core.security import validatePublicUrl
from app.integrations.retrieval.client import DocumentFetcherProtocol, documentToEvidence
from app.schemas.common import InputType, SourceType
from app.schemas.evidence import EvidenceQuery, EvidenceRecord
from app.schemas.verification import Claim


class _BraveSearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=1000)
    url: AnyHttpUrl


class _BraveWebResults(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results: list[_BraveSearchResult] = Field(default_factory=list)


class _BraveSearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    web: _BraveWebResults | None = None


@dataclass
class _SearchCandidate:
    url: str
    claimIds: list[str] = field(default_factory=list)


class BraveSearchEvidenceRetriever:
    """Search Brave's web index, then fetch original pages through the SSRF-safe fetcher."""

    def __init__(
        self,
        *,
        apiKey: str,
        documentFetcher: DocumentFetcherProtocol,
        baseUrl: str = "https://api.search.brave.com",
        country: str = "MY",
        searchLanguage: str = "en",
        resultsPerQuery: int = 3,
        maxEvidencePerClaim: int = 12,
        httpClient: httpx.AsyncClient | None = None,
    ) -> None:
        if not apiKey.strip():
            raise ValueError("Brave Search API key must not be blank.")
        self.apiKey = apiKey
        self.documentFetcher = documentFetcher
        self.country = country
        self.searchLanguage = searchLanguage
        self.resultsPerQuery = resultsPerQuery
        self.maxEvidencePerClaim = maxEvidencePerClaim
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

    async def retrieve(
        self,
        *,
        queries: Sequence[EvidenceQuery],
        originalInput: str,
        inputType: InputType,
        claims: Sequence[Claim],
    ) -> list[EvidenceRecord]:
        del originalInput, inputType
        if not queries or not claims:
            return []

        searchCalls = [self._search(query) for query in queries]
        searchResults = await asyncio.gather(*searchCalls, return_exceptions=True)
        candidatesByUrl: dict[str, _SearchCandidate] = {}
        failedSearches = 0
        for query, result in zip(queries, searchResults, strict=True):
            if isinstance(result, BaseException):
                failedSearches += 1
                continue
            for item in result[: self.maxEvidencePerClaim]:
                normalizedUrl = str(item.url)
                try:
                    validatePublicUrl(normalizedUrl)
                except Exception:
                    continue
                candidate = candidatesByUrl.setdefault(
                    normalizedUrl,
                    _SearchCandidate(url=normalizedUrl),
                )
                if query.claimId not in candidate.claimIds:
                    candidate.claimIds.append(query.claimId)

        if failedSearches == len(searchCalls):
            raise RetrievalError("All Brave Search requests failed.")
        if not candidatesByUrl:
            return []

        candidates = list(candidatesByUrl.values())
        semaphore = asyncio.Semaphore(5)

        async def fetchCandidate(candidate: _SearchCandidate) -> EvidenceRecord | None:
            async with semaphore:
                try:
                    document = await self.documentFetcher.fetch(candidate.url)
                except Exception:
                    return None
                return documentToEvidence(
                    document,
                    candidate.claimIds,
                    sourceType=SourceType.UNKNOWN,
                    limitations=[
                        "Search-selected page; source type and publication date were not "
                        "independently verified."
                    ],
                )

        fetchedEvidence = await asyncio.gather(
            *(fetchCandidate(candidate) for candidate in candidates)
        )
        evidenceById: dict[str, EvidenceRecord] = {}
        for record in fetchedEvidence:
            if record is None:
                continue
            existing = evidenceById.get(record.evidenceId)
            if existing is None:
                evidenceById[record.evidenceId] = record
                continue
            mergedClaimIds = list(dict.fromkeys([*existing.claimIds, *record.claimIds]))
            evidenceById[record.evidenceId] = existing.model_copy(
                update={"claimIds": mergedClaimIds}
            )
        evidence = list(evidenceById.values())
        if candidates and not evidence:
            raise RetrievalError("Search results were found, but no source page could be fetched.")
        return evidence

    async def _search(self, query: EvidenceQuery) -> list[_BraveSearchResult]:
        normalizedQuery = " ".join(query.query.split()[:50])[:400]
        if not normalizedQuery:
            return []
        try:
            response = await self.httpClient.get(
                "/res/v1/web/search",
                headers={"X-Subscription-Token": self.apiKey},
                params={
                    "q": normalizedQuery,
                    "count": self.resultsPerQuery,
                    "country": self.country,
                    "search_lang": self.searchLanguage,
                },
            )
            response.raise_for_status()
            parsedResponse = _BraveSearchResponse.model_validate(response.json())
        except (httpx.HTTPError, ValueError, ValidationError) as error:
            raise RetrievalError("Brave Search request failed.") from error
        return parsedResponse.web.results if parsedResponse.web else []

    async def close(self) -> None:
        if self._ownsClient:
            await self.httpClient.aclose()
