from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.agents.graph import VerificationWorkflow
from app.api.v1.router import router as v1Router
from app.core.config import Settings, getSettings
from app.core.exceptions import (
    AuthenticationError,
    PersistenceUnavailableError,
    VerificationAccessError,
    VerificationNotFoundError,
)
from app.core.logging import configureLogging
from app.integrations.gonka.client import GonkaClient, GonkaClientProtocol
from app.integrations.gonka.fake import UnavailableGonkaClient
from app.integrations.retrieval.brave import BraveSearchEvidenceRetriever
from app.integrations.retrieval.client import (
    EvidenceRetrieverProtocol,
    NullEvidenceRetriever,
    UrlDocumentFetcher,
)
from app.integrations.supabase.auth import SupabaseAuthClient
from app.integrations.supabase.client import (
    InMemoryVerificationRepository,
    SupabaseVerificationRepository,
    VerificationRepositoryProtocol,
)
from app.integrations.supabase.gateway import SupabaseRestGateway
from app.services.verificationService import VerificationService


def buildDefaultService(settings: Settings) -> tuple[VerificationService, list[object]]:
    closableResources: list[object] = []
    gonkaClient: GonkaClientProtocol
    if settings.gonkaConfigured:
        gonkaClient = GonkaClient(settings)
        closableResources.append(gonkaClient)
    else:
        gonkaClient = UnavailableGonkaClient()
    documentFetcher = UrlDocumentFetcher()
    closableResources.append(documentFetcher)
    retriever: EvidenceRetrieverProtocol
    if settings.searchConfigured:
        retriever = BraveSearchEvidenceRetriever(
            apiKey=settings.BRAVE_SEARCH_API_KEY or "",
            documentFetcher=documentFetcher,
            baseUrl=str(settings.BRAVE_SEARCH_BASE_URL),
            country=settings.BRAVE_SEARCH_COUNTRY,
            searchLanguage=settings.BRAVE_SEARCH_LANGUAGE,
            resultsPerQuery=settings.BRAVE_SEARCH_RESULTS_PER_QUERY,
            maxEvidencePerClaim=settings.MAX_EVIDENCE_PER_CLAIM,
        )
        closableResources.append(retriever)
    else:
        retriever = NullEvidenceRetriever()
    workflow = VerificationWorkflow(
        gonkaClient=gonkaClient,
        retriever=retriever,
        documentFetcher=documentFetcher,
        orchestratorModel=settings.GONKA_ORCHESTRATOR_MODEL,
        biasAuditorModel=settings.GONKA_BIAS_AUDITOR_MODEL,
        parallelVerifiers=settings.GONKA_PARALLEL_VERIFIERS,
        modelA=settings.GONKA_MODEL_A,
        modelB=settings.GONKA_MODEL_B,
        judgeModel=settings.GONKA_JUDGE_MODEL,
    )
    repository: VerificationRepositoryProtocol
    if settings.supabaseConfigured:
        supabaseGateway = SupabaseRestGateway(
            baseUrl=str(settings.SUPABASE_URL),
            apiKey=settings.SUPABASE_KEY or "",
        )
        closableResources.append(supabaseGateway)
        repository = SupabaseVerificationRepository(supabaseGateway)
    else:
        repository = InMemoryVerificationRepository()

    return VerificationService(workflow, repository), closableResources


def createApp(
    *,
    settings: Settings | None = None,
    verificationService: VerificationService | None = None,
) -> FastAPI:
    appSettings = settings or getSettings()
    configureLogging(appSettings.LOG_LEVEL)
    supabaseAuthClient: SupabaseAuthClient | None = None

    if verificationService is None:
        service, resources = buildDefaultService(appSettings)
    else:
        service = verificationService
        resources = []
    if appSettings.supabaseConfigured:
        supabaseAuthClient = SupabaseAuthClient(
            baseUrl=str(appSettings.SUPABASE_URL),
            apiKey=appSettings.SUPABASE_KEY or "",
        )
        resources.append(supabaseAuthClient)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        for resource in resources:
            close = getattr(resource, "close", None)
            if close is not None:
                await close()

    application = FastAPI(
        title="TruthScope API",
        version="0.1.0",
        description=(
            "Evidence-first verification API. Scores estimate support from collected evidence; "
            "they do not guarantee truth or political neutrality."
        ),
        lifespan=lifespan,
    )
    application.state.verificationService = service
    application.state.settings = appSettings
    application.state.supabaseAuthClient = supabaseAuthClient
    application.state.persistenceBackend = (
        "memory" if isinstance(service.repository, InMemoryVerificationRepository) else "external"
    )
    application.include_router(v1Router)

    @application.exception_handler(AuthenticationError)
    async def handleAuthenticationError(
        request: Request,
        error: AuthenticationError,
    ) -> JSONResponse:
        del error
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": {
                    "code": "AUTHENTICATION_REQUIRED",
                    "message": "A valid Supabase access token is required.",
                    "requestId": request.headers.get("X-Request-Id"),
                    "retryable": False,
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    @application.exception_handler(PersistenceUnavailableError)
    async def handlePersistenceUnavailable(
        request: Request,
        error: PersistenceUnavailableError,
    ) -> JSONResponse:
        del error
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": "PERSISTENCE_UNAVAILABLE",
                    "message": "Verification storage is temporarily unavailable.",
                    "requestId": request.headers.get("X-Request-Id"),
                    "retryable": True,
                }
            },
        )

    @application.exception_handler(VerificationNotFoundError)
    async def handleNotFound(
        request: Request,
        error: VerificationNotFoundError,
    ) -> JSONResponse:
        del error
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": "VERIFICATION_NOT_FOUND",
                    "message": "Verification was not found.",
                    "requestId": request.headers.get("X-Request-Id"),
                    "retryable": False,
                }
            },
        )

    @application.exception_handler(VerificationAccessError)
    async def handleForbidden(
        request: Request,
        error: VerificationAccessError,
    ) -> JSONResponse:
        del error
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "code": "VERIFICATION_FORBIDDEN",
                    "message": "Verification is not accessible to this user.",
                    "requestId": request.headers.get("X-Request-Id"),
                    "retryable": False,
                }
            },
        )

    return application


app = createApp()
