from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class NewsArticle(BaseModel):
    title: str
    link: str
    published_at: str = Field(description="ISO 8601 UTC")
    source: Optional[str] = None


class NewsForTicker(BaseModel):
    ticker: str
    provider: Literal["google_rss", "newsapi"] = "google_rss"
    articles: List[NewsArticle] = Field(default_factory=list)
    error: Optional[str] = None


class NewsBundleResponse(BaseModel):
    days: int
    by_ticker: List[NewsForTicker]
    warnings: List[str] = Field(default_factory=list)
