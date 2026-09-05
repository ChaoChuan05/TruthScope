from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import getCurrentUserId, getTrendingTopicsService
from app.schemas.trending import TrendingTopicsResponse
from app.services.trendingTopicsService import TrendingTopicsService

router = APIRouter(tags=["topics"])


@router.get("/trending-topics", response_model=TrendingTopicsResponse)
async def getTrendingTopics(
    service: Annotated[TrendingTopicsService, Depends(getTrendingTopicsService)],
    userId: Annotated[str, Depends(getCurrentUserId)],
) -> TrendingTopicsResponse:
    del userId
    return await service.getTopics()
