import httpx

from app.integrations.retrieval.trendingTopics import BraveNewsTopicsProvider


async def test_braveNewsTopics_usesOneBoundedNewsSearchRequest() -> None:
    callCount = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal callCount
        callCount += 1
        assert request.url.path == "/res/v1/news/search"
        assert request.headers["X-Subscription-Token"] == "search-secret"
        assert request.url.params["q"] == "Malaysia"
        assert request.url.params["country"] == "MY"
        assert request.url.params["freshness"] == "pw"
        assert request.url.params["count"] == "10"
        return httpx.Response(
            200,
            json={
                "results": [
                    {"title": "Malaysia announces a public policy update", "url": "https://a"},
                    {"title": "Parliament debates a proposed amendment", "url": "https://b"},
                ]
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.search.brave.com",
    ) as httpClient:
        provider = BraveNewsTopicsProvider(
            apiKey="search-secret",
            httpClient=httpClient,
        )
        titles = await provider.fetchRecentTitles()

    assert callCount == 1
    assert titles == [
        "Malaysia announces a public policy update",
        "Parliament debates a proposed amendment",
    ]
