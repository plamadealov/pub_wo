from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.schemas.news import NewsBundleResponse
from app.services.news_fetch import gather_news

router = APIRouter(tags=["news"])

MAX_TICKERS = 16
MAX_DAYS = 30


@router.get("/news", response_model=NewsBundleResponse)
def get_news(
    tickers: str = Query(
        ...,
        min_length=1,
        description="Тикеры через запятую, напр. SBER,GAZP",
    ),
    days: int = Query(10, ge=1, le=MAX_DAYS, description="Глубина в календарных днях"),
) -> NewsBundleResponse:
    parts: List[str] = [p.strip() for p in tickers.split(",") if p.strip()]
    if not parts:
        raise HTTPException(status_code=422, detail={"message": "Укажите хотя бы один тикер"})
    if len(parts) > MAX_TICKERS:
        raise HTTPException(
            status_code=422,
            detail={"message": f"Не более {MAX_TICKERS} тикеров за запрос"},
        )
    return gather_news(parts, days)
