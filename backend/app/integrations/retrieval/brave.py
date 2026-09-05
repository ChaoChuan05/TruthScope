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
        maxQueriesPerClaim: int = 3,
        maxEvidencePerClaim: int = 12,
        maxTotalEvidence: int = 20,
        httpClient: httpx.AsyncClient | None = None,
    ) -> None:
        if not apiKey.strip():
            raise ValueError("Brave Search API key must not be blank.")
        self.apiKey = apiKey
        self.documentFetcher = documentFetcher
        self.country = country
        self.searchLanguage = searchLanguage
        self.resultsPerQuery = resultsPerQuery
        self.maxQueriesPerClaim = maxQueriesPerClaim
        self.maxEvidencePerClaim = maxEvidencePerClaim
        self.maxTotalEvidence = maxTotalEvidence
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

        boundedQueries: list[EvidenceQuery] = []
        queryCountByClaim: dict[str, int] = {}
        for query in queries:
            queryCount = queryCountByClaim.get(query.claimId, 0)
            if queryCount >= self.maxQueriesPerClaim:
                continue
            boundedQueries.append(query)
            queryCountByClaim[query.claimId] = queryCount + 1

        searchCalls = [self._search(query) for query in boundedQueries]
        searchResults = await asyncio.gather(*searchCalls, return_exceptions=True)
        claimIds = list(dict.fromkeys(claim.claimId for claim in claims))
        searchResultsByClaim: dict[str, list[list[_BraveSearchResult]]] = {
            claimId: [] for claimId in claimIds
        }
        failedSearches = 0
        for query, result in zip(boundedQueries, searchResults, strict=True):
            if isinstance(result, BaseException):
                failedSearches += 1
                continue
            if query.claimId in searchResultsByClaim:
                searchResultsByClaim[query.claimId].append(result)

        urlsByClaim: dict[str, list[str]] = {claimId: [] for claimId in claimIds}
        for claimId in claimIds:
            seenUrls: set[str] = set()
            for result in searchResultsByClaim[claimId]:
                for item in result:
                    normalizedUrl = str(item.url)
                    try:
                        validatePublicUrl(normalizedUrl)
                    except Exception:
                        continue
                    if normalizedUrl in seenUrls:
                        continue
                    urlsByClaim[claimId].append(normalizedUrl)
                    seenUrls.add(normalizedUrl)

        candidatesByUrl: dict[str, _SearchCandidate] = {}
        candidates: list[_SearchCandidate] = []
        remainingUrls = {claimId: iter(urls) for claimId, urls in urlsByClaim.items()}
        activeClaimIds = list(claimIds)
        while activeClaimIds:
            nextActiveClaimIds: list[str] = []
            for claimId in activeClaimIds:
                try:
                    normalizedUrl = next(remainingUrls[claimId])
                except StopIteration:
                    continue
                nextActiveClaimIds.append(claimId)
                candidate = candidatesByUrl.get(normalizedUrl)
                if candidate is None:
                    candidate = _SearchCandidate(url=normalizedUrl)
                    candidatesByUrl[normalizedUrl] = candidate
                    candidates.append(candidate)
                if claimId not in candidate.claimIds:
                    candidate.claimIds.append(claimId)
            activeClaimIds = nextActiveClaimIds

        if failedSearches == len(searchCalls):
            raise RetrievalError("All Brave Search requests failed.")
        if not candidates:
            return []

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

        evidence: list[EvidenceRecord] = []
        evidenceIndexById: dict[str, int] = {}
        evidenceCountByClaim: dict[str, int] = {}
        candidateIndex = 0
        while len(evidence) < self.maxTotalEvidence and candidateIndex < len(candidates):
            batch: list[_SearchCandidate] = []
            provisionalCounts = dict(evidenceCountByClaim)
            batchLimit = min(5, self.maxTotalEvidence - len(evidence))
            while candidateIndex < len(candidates) and len(batch) < batchLimit:
                candidate = candidates[candidateIndex]
                candidateIndex += 1
                eligibleClaimIds = [
                    claimId
                    for claimId in candidate.claimIds
                    if provisionalCounts.get(claimId, 0) < self.maxEvidencePerClaim
                ]
                if not eligibleClaimIds:
                    continue
                batch.append(_SearchCandidate(url=candidate.url, claimIds=eligibleClaimIds))
                for claimId in eligibleClaimIds:
                    provisionalCounts[claimId] = provisionalCounts.get(claimId, 0) + 1
            if not batch:
                continue
            fetchedEvidence = await asyncio.gather(*(fetchCandidate(item) for item in batch))
            for record in fetchedEvidence:
                if record is None:
                    continue
                eligibleClaimIds = [
                    claimId
                    for claimId in record.claimIds
                    if evidenceCountByClaim.get(claimId, 0) < self.maxEvidencePerClaim
                ]
                if not eligibleClaimIds:
                    continue
                existingIndex = evidenceIndexById.get(record.evidenceId)
                if existingIndex is not None:
                    existing = evidence[existingIndex]
                    newClaimIds = [
                        claimId for claimId in eligibleClaimIds if claimId not in existing.claimIds
                    ]
                    if newClaimIds:
                        evidence[existingIndex] = existing.model_copy(
                            update={"claimIds": [*existing.claimIds, *newClaimIds]}
                        )
                        for claimId in newClaimIds:
                            evidenceCountByClaim[claimId] = evidenceCountByClaim.get(claimId, 0) + 1
                    continue
                if len(evidence) >= self.maxTotalEvidence:
                    break
                record = record.model_copy(update={"claimIds": eligibleClaimIds})
                evidenceIndexById[record.evidenceId] = len(evidence)
                evidence.append(record)
                for claimId in eligibleClaimIds:
                    evidenceCountByClaim[claimId] = evidenceCountByClaim.get(claimId, 0) + 1

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
