from app.integrations.retrieval.brave import BraveSearchEvidenceRetriever
from app.integrations.retrieval.client import (
    DocumentFetcherProtocol,
    EvidenceRetrieverProtocol,
    FixtureDocumentFetcher,
    FixtureEvidenceRetriever,
    NullEvidenceRetriever,
    UnavailableDocumentFetcher,
    UrlDocumentFetcher,
    UrlEvidenceRetriever,
)

__all__ = [
    "BraveSearchEvidenceRetriever",
    "DocumentFetcherProtocol",
    "EvidenceRetrieverProtocol",
    "FixtureDocumentFetcher",
    "FixtureEvidenceRetriever",
    "NullEvidenceRetriever",
    "UnavailableDocumentFetcher",
    "UrlDocumentFetcher",
    "UrlEvidenceRetriever",
]
