from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.moex.client import MoexIssClient, MoexIssError
from app.schemas.portfolio import AnalyzeRequest, AnalyzeResponse, InstrumentResolveResponse
from app.services.analyze_pipeline import run_analyze

router = APIRouter(tags=["portfolio"])


@router.post("/portfolio/analyze", response_model=AnalyzeResponse)
def analyze_portfolio(body: AnalyzeRequest) -> AnalyzeResponse:
    """Расчёт портфеля: MOEX + исторические β, VaR, ES; либо mock при use_mock=true."""
    return run_analyze(body)


@router.get("/instruments/resolve", response_model=InstrumentResolveResponse)
def resolve_instrument(
    ticker: str = Query(..., min_length=1, description="Строка тикера с фронта"),
) -> InstrumentResolveResponse:
    q = ticker.strip()
    try:
        with MoexIssClient() as client:
            ok = client.probe_share_tqbr(q)
    except MoexIssError as e:
        raise HTTPException(status_code=502, detail={"message": str(e)}) from e
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail={"message": f"Ошибка HTTP при обращении к MOEX: {e!s}"},
        ) from e
    if not ok:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Тикер «{q.upper()}» не найден в истории TQBR MOEX"},
        )
    return InstrumentResolveResponse(
        query=q,
        canonical_ticker=q.upper(),
        board="TQBR",
        source="moex",
        note="Проверено по истории MOEX ISS (TQBR)",
    )
