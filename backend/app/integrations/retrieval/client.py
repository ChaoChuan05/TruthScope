import hashlib
from collections.abc import Sequence
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urljoin, urlsplit

import httpx

from app.core.exceptions import RetrievalError
from app.core.security import validatePublicHostResolution
from app.schemas.common import EvidenceStance, InputType, SourceType
from app.schemas.evidence import (
    EvidenceQuality,
    EvidenceQuery,
    EvidenceRecord,
    RetrievedDocument,
    SourceMetadata,
)
from app.schemas.verification import Claim

MAX_RETRIEVAL_BYTES = 1_000_000
MAX_DOCUMENT_CHARS = 12_000
MAX_REDIRECTS = 3


class EvidenceRetrieverProtocol(Protocol):
    async def retrieve(
        self,
        *,
        queries: Sequence[EvidenceQuery],
        originalInput: str,
        inputType: InputType,
        claims: Sequence[Claim],
    ) -> list[EvidenceRecord]: ...


class DocumentFetcherProtocol(Protocol):
    async def fetch(self, url: str) -> RetrievedDocument: ...


class NullEvidenceRetriever:
    """Explicit no-search adapter used when a search provider is not configured."""

    async def retrieve(
        self,
        *,
        queries: Sequence[EvidenceQuery],
        originalInput: str,
        inputType: InputType,
        claims: Sequence[Claim],
    ) -> list[EvidenceRecord]:
        del queries, originalInput, inputType, claims
        return []


class FixtureEvidenceRetriever:
    def __init__(self, evidence: Sequence[EvidenceRecord]) -> None:
        self.evidence = list(evidence)

    async def retrieve(
        self,
        *,
        queries: Sequence[EvidenceQuery],
        originalInput: str,
        inputType: InputType,
        claims: Sequence[Claim],
    ) -> list[EvidenceRecord]:
        del queries, originalInput, inputType, claims
        return list(self.evidence)


class FixtureDocumentFetcher:
    def __init__(self, document: RetrievedDocument | None = None) -> None:
        self.document = document

    async def fetch(self, url: str) -> RetrievedDocument:
        del url
        if self.document is None:
            raise RetrievalError("No fixture document was configured.")
        return self.document


class UnavailableDocumentFetcher:
    async def fetch(self, url: str) -> RetrievedDocument:
        del url
        raise RetrievalError("URL document retrieval is not configured.")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.titleParts: list[str] = []
        self.inTitle = False
        self.ignoredDepth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style", "noscript", "svg"}:
            self.ignoredDepth += 1
        if tag == "title":
            self.inTitle = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.ignoredDepth:
            self.ignoredDepth -= 1
        if tag == "title":
            self.inTitle = False

    def handle_data(self, data: str) -> None:
        if self.ignoredDepth:
            return
        normalized = " ".join(data.split())
        if not normalized:
            return
        self.parts.append(normalized)
        if self.inTitle:
            self.titleParts.append(normalized)


class UrlDocumentFetcher:
    """Fetch a public text document with redirect, DNS, size, and content-type controls."""

    def __init__(self, httpClient: httpx.AsyncClient | None = None) -> None:
        self._ownsClient = httpClient is None
        self.httpClient = httpClient or httpx.AsyncClient(
            timeout=10,
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "TruthScope/0.1 evidence-retriever"},
        )

    async def fetch(self, url: str) -> RetrievedDocument:
        finalUrl, contentType, body = await self._fetchPublicDocument(url)
        title = finalUrl
        if "html" in contentType:
            extractor = _TextExtractor()
            extractor.feed(body)
            text = " ".join(extractor.parts)
            if extractor.titleParts:
                title = " ".join(extractor.titleParts)[:500]
        else:
            text = " ".join(body.split())
        if not text:
            raise RetrievalError("Retrieved URL contained no readable text.")

        hostname = urlsplit(finalUrl).hostname
        return RetrievedDocument(
            source=SourceMetadata(
                url=finalUrl,
                title=title[:500],
                publisher=hostname[:300] if hostname else None,
            ),
            text=text[:MAX_DOCUMENT_CHARS],
            contentType=contentType[:200],
        )

    async def _fetchPublicDocument(self, initialUrl: str) -> tuple[str, str, str]:
        currentUrl = initialUrl
        for redirectCount in range(MAX_REDIRECTS + 1):
            await validatePublicHostResolution(currentUrl)
            try:
                async with self.httpClient.stream("GET", currentUrl) as response:
                    if response.is_redirect:
                        if redirectCount >= MAX_REDIRECTS:
                            raise RetrievalError("URL exceeded the redirect limit.")
                        location = response.headers.get("location")
                        if not location:
                            raise RetrievalError("URL returned a redirect without a destination.")
                        currentUrl = urljoin(currentUrl, location)
                        continue
                    response.raise_for_status()
                    contentType = response.headers.get("content-type", "").lower()
                    if not any(value in contentType for value in ("text/html", "text/plain")):
                        raise RetrievalError("URL content type is not supported.")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_RETRIEVAL_BYTES:
                            raise RetrievalError("URL content exceeded the size limit.")
                    return currentUrl, contentType, body.decode("utf-8", errors="replace")
            except httpx.HTTPError as error:
                raise RetrievalError("URL retrieval failed.") from error
        raise RetrievalError("URL retrieval failed.")

    async def close(self) -> None:
        if self._ownsClient:
            await self.httpClient.aclose()


def documentToEvidence(
    document: RetrievedDocument,
    claimIds: Sequence[str],
    *,
    sourceType: SourceType,
    limitations: Sequence[str],
) -> EvidenceRecord:
    evidenceDigest = hashlib.sha256(str(document.source.url).encode()).hexdigest()[:16]
    if sourceType == SourceType.USER_PROVIDED:
        quality = EvidenceQuality(
            provenance=3,
            directness=1,
            dateRelevance=1,
            contextCompleteness=2,
            corroboration=0,
        )
    else:
        quality = EvidenceQuality(
            provenance=2,
            directness=2,
            dateRelevance=1,
            contextCompleteness=2,
            corroboration=0,
        )
    return EvidenceRecord(
        evidenceId=f"url-{evidenceDigest}",
        source=document.source.model_copy(update={"sourceType": sourceType}),
        excerpt=document.text,
        claimIds=list(dict.fromkeys(claimIds)),
        stance=EvidenceStance.UNCLEAR,
        stanceStrength=0,
        quality=quality,
        limitations=list(limitations),
    )


class UrlEvidenceRetriever:
    """Compatibility adapter for fetching only a user-supplied URL."""

    def __init__(self, documentFetcher: DocumentFetcherProtocol | None = None) -> None:
        self.documentFetcher = documentFetcher or UrlDocumentFetcher()

    async def retrieve(
        self,
        *,
        queries: Sequence[EvidenceQuery],
        originalInput: str,
        inputType: InputType,
        claims: Sequence[Claim],
    ) -> list[EvidenceRecord]:
        del queries
        if inputType != InputType.URL:
            return []
        document = await self.documentFetcher.fetch(originalInput)
        return [
            documentToEvidence(
                document,
                [claim.claimId for claim in claims],
                sourceType=SourceType.USER_PROVIDED,
                limitations=[
                    "User-provided page is uncorroborated and does not establish claim truth."
                ],
            )
        ]

    async def close(self) -> None:
        close = getattr(self.documentFetcher, "close", None)
        if close is not None:
            await close()
