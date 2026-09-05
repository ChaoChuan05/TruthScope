import asyncio

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.main import createApp
from app.services.trendingTopicsService import TrendingTopicsService


class FakeSupabaseAuthClient:
    async def getUserId(self, accessToken: str) -> str:
        usersByToken = {
            "token-user-1": "user-1",
            "token-user-2": "user-2",
        }
        userId = usersByToken.get(accessToken)
        if userId is None:
            raise AuthenticationError("Supabase access token is invalid or expired.")
        return userId


def useFakeAuth(application: FastAPI) -> None:
    application.state.supabaseAuthClient = FakeSupabaseAuthClient()


async def test_verificationEndpoints_returnTransparentResult(
    sampleEvidence,
    serviceFactory,
) -> None:
    service, _ = serviceFactory([sampleEvidence])
    application = createApp(
        settings=Settings(_env_file=None),
        verificationService=service,
    )
    useFakeAuth(application)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/verifications",
            json={
                "input": "The measured value was 42 units.",
                "outputLanguage": "zh-CN",
            },
            headers={"Authorization": "Bearer token-user-1"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["score"]["truthScore"] == 95
        assert body["outputLanguage"] == "zh-CN"
        assert body["evidence"][0]["source"]["url"]
        assert len(body["gonkaRequestIds"]) == 7
        assert "outputText" not in body["inferenceRecords"][0]
        assert "userId" not in body

        verificationId = body["verificationId"]
        getResponse = await client.get(
            f"/api/v1/verifications/{verificationId}",
            headers={"Authorization": "Bearer token-user-1"},
        )
        assert getResponse.status_code == 200

        evidenceResponse = await client.get(
            f"/api/v1/verifications/{verificationId}/evidence",
            headers={"Authorization": "Bearer token-user-1"},
        )
        assert evidenceResponse.status_code == 200
        assert evidenceResponse.json()["evidence"][0]["evidenceId"] == "evidence-1"

        forbiddenResponse = await client.get(
            f"/api/v1/verifications/{verificationId}",
            headers={"Authorization": "Bearer token-user-2"},
        )
        assert forbiddenResponse.status_code == 403


async def test_verificationJob_canBePolledAndEnforcesOwnership(
    sampleEvidence,
    serviceFactory,
) -> None:
    service, _ = serviceFactory([sampleEvidence], reducedGonkaCalls=True)
    application = createApp(
        settings=Settings(_env_file=None),
        verificationService=service,
    )
    useFakeAuth(application)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        createResponse = await client.post(
            "/api/v1/verification-jobs",
            json={"input": "The measured value was 42 units."},
            headers={"Authorization": "Bearer token-user-1"},
        )
        assert createResponse.status_code == 202
        jobId = createResponse.json()["jobId"]

        for _ in range(100):
            response = await client.get(
                f"/api/v1/verification-jobs/{jobId}",
                headers={"Authorization": "Bearer token-user-1"},
            )
            if response.json()["status"] == "complete":
                break
            await asyncio.sleep(0.001)

        assert response.status_code == 200
        assert response.json()["status"] == "complete"
        assert response.json()["result"]["status"] == "complete"

        forbiddenResponse = await client.get(
            f"/api/v1/verification-jobs/{jobId}",
            headers={"Authorization": "Bearer token-user-2"},
        )
        assert forbiddenResponse.status_code == 403


async def test_oversizedInput_isRejected(
    sampleEvidence,
    serviceFactory,
) -> None:
    service, _ = serviceFactory([sampleEvidence])
    application = createApp(
        settings=Settings(_env_file=None),
        verificationService=service,
    )
    useFakeAuth(application)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/verifications",
            json={"input": "x" * 5001},
            headers={"Authorization": "Bearer token-user-1"},
        )

    assert response.status_code == 422


async def test_unknownOutputLanguage_isRejected(
    sampleEvidence,
    serviceFactory,
) -> None:
    service, _ = serviceFactory([sampleEvidence])
    application = createApp(
        settings=Settings(_env_file=None),
        verificationService=service,
    )
    useFakeAuth(application)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/verifications",
            json={"input": "Test claim.", "outputLanguage": "fr"},
            headers={"Authorization": "Bearer token-user-1"},
        )

    assert response.status_code == 422


async def test_health_doesNotLeakProviderDetails(
    sampleEvidence,
    serviceFactory,
) -> None:
    service, _ = serviceFactory([sampleEvidence])
    application = createApp(
        settings=Settings(
            _env_file=None,
            GONKA_API_KEY="secret",
        ),
        verificationService=service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "gonkaConfigured": True,
        "searchConfigured": False,
        "persistenceBackend": "memory",
    }
    assert "secret" not in response.text


async def test_verificationEndpoints_requireBearerToken(
    sampleEvidence,
    serviceFactory,
) -> None:
    service, _ = serviceFactory([sampleEvidence])
    application = createApp(
        settings=Settings(_env_file=None),
        verificationService=service,
    )
    useFakeAuth(application)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/verifications",
            json={"input": "The measured value was 42 units."},
        )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


async def test_trendingTopics_returnsCachedFallbackAndRequiresAuthentication(
    sampleEvidence,
    serviceFactory,
) -> None:
    service, _ = serviceFactory([sampleEvidence])
    application = createApp(
        settings=Settings(_env_file=None),
        verificationService=service,
        trendingTopicsService=TrendingTopicsService(None),
    )
    useFakeAuth(application)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        unauthorizedResponse = await client.get("/api/v1/trending-topics")
        response = await client.get(
            "/api/v1/trending-topics",
            headers={"Authorization": "Bearer token-user-1"},
        )

    assert unauthorizedResponse.status_code == 401
    assert response.status_code == 200
    assert response.json()["source"] == "fallback"
    assert len(response.json()["topics"]) == 3


async def test_corsPreflight_allowsConfiguredFrontendOrigin(
    sampleEvidence,
    serviceFactory,
) -> None:
    service, _ = serviceFactory([sampleEvidence])
    application = createApp(
        settings=Settings(
            _env_file=None,
            CORS_ALLOWED_ORIGINS="http://127.0.0.1:5500",
        ),
        verificationService=service,
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        response = await client.options(
            "/api/v1/verifications",
            headers={
                "Origin": "http://127.0.0.1:5500",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:5500"
    assert "authorization" in response.headers["Access-Control-Allow-Headers"].lower()
