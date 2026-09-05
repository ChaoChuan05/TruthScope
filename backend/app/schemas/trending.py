from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import StrictSchema


class TrendingTopic(StrictSchema):
    label: str = Field(min_length=1, max_length=72)
    claim: str = Field(min_length=1, max_length=500)


class TrendingTopicsResponse(StrictSchema):
    topics: list[TrendingTopic] = Field(min_length=1, max_length=3)
    source: Literal["brave_news", "fallback"]
    generatedAt: datetime
