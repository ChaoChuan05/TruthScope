import asyncio

from app.core.exceptions import RetrievalError
from app.services.trendingTopicsService import TrendingTopicsService


class CountingTopicsProvider:
    def __init__(self, titles: list[str]) -> None:
        self.titles = titles
        self.callCount = 0

    async def fetchRecentTitles(self) -> list[str]:
        self.callCount += 1
        await asyncio.sleep(0)
        return self.titles


class FailingTopicsProvider:
    def __init__(self) -> None:
        self.callCount = 0

    async def fetchRecentTitles(self) -> list[str]:
        self.callCount += 1
        raise RetrievalError("Brave unavailable")


async def test_trendingTopicsService_coalescesConcurrentRequestsAndCachesResult() -> None:
    provider = CountingTopicsProvider(
        [
            "Malaysia announces a new public transport policy this week",
            "Parliament debates amendments to an existing national law",
            "Malaysia publishes updated economic figures for the quarter",
        ]
    )
    service = TrendingTopicsService(provider)

    first, second = await asyncio.gather(service.getTopics(), service.getTopics())
    third = await service.getTopics()

    assert provider.callCount == 1
    assert first == second == third
    assert first.source == "brave_news"
    assert len(first.topics) == 3


async def test_trendingTopicsService_cachesFallbackWhenProviderFails() -> None:
    provider = FailingTopicsProvider()
    service = TrendingTopicsService(provider)

    first = await service.getTopics()
    second = await service.getTopics()

    assert provider.callCount == 1
    assert first == second
    assert first.source == "fallback"
    assert len(first.topics) == 3
