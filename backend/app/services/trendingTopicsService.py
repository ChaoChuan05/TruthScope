import asyncio
import logging
import time

from app.core.exceptions import RetrievalError
from app.integrations.retrieval.trendingTopics import NewsTopicsProviderProtocol
from app.schemas.common import utcNow
from app.schemas.trending import TrendingTopic, TrendingTopicsResponse

logger = logging.getLogger(__name__)

DEFAULT_TOPICS = [
    TrendingTopic(
        label="Malaysia population claim",
        claim="Malaysia reported a population of 34.1 million in 2024.",
    ),
    TrendingTopic(
        label="Fuel subsidy rumour",
        claim="The Malaysian government will remove every fuel subsidy next month.",
    ),
    TrendingTopic(
        label="Parliament quotation",
        claim="A Member of Parliament said healthcare would be fully privatised.",
    ),
]


class TrendingTopicsService:
    """Cache current topic suggestions so UI traffic does not multiply Brave requests."""

    def __init__(
        self,
        provider: NewsTopicsProviderProtocol | None,
        *,
        cacheSeconds: float = 900,
        failureCacheSeconds: float = 300,
    ) -> None:
        if cacheSeconds <= 0 or failureCacheSeconds <= 0:
            raise ValueError("Trending topic cache durations must be positive.")
        self.provider = provider
        self.cacheSeconds = cacheSeconds
        self.failureCacheSeconds = failureCacheSeconds
        self._cachedResponse: TrendingTopicsResponse | None = None
        self._cacheExpiresAt = 0.0
        self._cacheLock = asyncio.Lock()

    async def getTopics(self) -> TrendingTopicsResponse:
        cachedResponse = self._currentCache()
        if cachedResponse is not None:
            return cachedResponse

        async with self._cacheLock:
            cachedResponse = self._currentCache()
            if cachedResponse is not None:
                return cachedResponse

            topics: list[TrendingTopic] = []
            source = "fallback"
            cacheDuration = self.failureCacheSeconds
            if self.provider is not None:
                try:
                    topics = self._topicsFromTitles(await self.provider.fetchRecentTitles())
                except RetrievalError as error:
                    logger.warning(
                        "Trending topics unavailable errorType=%s",
                        type(error.__cause__ or error).__name__,
                    )
                if topics:
                    source = "brave_news"
                    cacheDuration = self.cacheSeconds

            topics = self._fillTopics(topics)
            response = TrendingTopicsResponse(
                topics=topics,
                source=source,
                generatedAt=utcNow(),
            )
            self._cachedResponse = response
            self._cacheExpiresAt = time.monotonic() + cacheDuration
            return response

    def _currentCache(self) -> TrendingTopicsResponse | None:
        if self._cachedResponse is None or time.monotonic() >= self._cacheExpiresAt:
            return None
        return self._cachedResponse

    def _topicsFromTitles(self, titles: list[str]) -> list[TrendingTopic]:
        topics: list[TrendingTopic] = []
        seenTitles: set[str] = set()
        for title in titles:
            normalizedTitle = " ".join(title.split())[:500]
            titleKey = normalizedTitle.casefold()
            if len(normalizedTitle) < 10 or titleKey in seenTitles:
                continue
            seenTitles.add(titleKey)
            topics.append(
                TrendingTopic(
                    label=self._shortLabel(normalizedTitle),
                    claim=normalizedTitle,
                )
            )
            if len(topics) == 3:
                break
        return topics

    def _fillTopics(self, topics: list[TrendingTopic]) -> list[TrendingTopic]:
        filledTopics = list(topics)
        seenClaims = {topic.claim.casefold() for topic in filledTopics}
        for fallbackTopic in DEFAULT_TOPICS:
            if len(filledTopics) == 3:
                break
            if fallbackTopic.claim.casefold() not in seenClaims:
                filledTopics.append(fallbackTopic)
                seenClaims.add(fallbackTopic.claim.casefold())
        return filledTopics

    def _shortLabel(self, title: str) -> str:
        if len(title) <= 64:
            return title
        shortened = title[:61].rsplit(" ", 1)[0]
        return f"{shortened or title[:61]}…"
