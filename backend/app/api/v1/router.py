from fastapi import APIRouter

from app.api.v1.verifications import router as verificationRouter

router = APIRouter(prefix="/api/v1")
router.include_router(verificationRouter)
