from fastapi import APIRouter

from app.api.v1.trendingTopics import router as trendingTopicsRouter
from app.api.v1.verifications import router as verificationRouter

router = APIRouter(prefix="/api/v1")
router.include_router(verificationRouter)
router.include_router(trendingTopicsRouter)
