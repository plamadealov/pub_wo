from __future__ import annotations

from typing import Any, Dict, List

import httpx
import numpy as np
import pandas as pd
from fastapi import HTTPException

from app.moex.client import MoexIssClient, MoexIssError
from app.schemas.portfolio import (
    AnalyzeMeta,
    AnalyzeRequest,
    AnalyzeResponse,
    ChartSeries,
    TickerMetrics,
)
from app.services import analytics
from app.services.market_data import build_aligned_closes
from app.services.mock_analyze import build_mock_analyze, _normalize_weights


def run_analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    if request.use_mock:
        return build_mock_analyze(request)

    norm = _normalize_weights(request)
    tickers_only = [t for t, _ in norm]
    w = np.array([wi for _, wi in norm], dtype=float)

    try:
        with MoexIssClient() as client:
            prices, d_start, d_end = build_aligned_closes(
                client,
                tickers_only,
                request.market_index,
                request.trading_days,
            )
    except MoexIssError as e:
        raise HTTPException(status_code=422, detail={"message": str(e)}) from e
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail={"message": f"Ошибка сети при запросе к MOEX: {e!s}"},
        ) from e

    mkt_col = "__market__"
    if mkt_col not in prices.columns:
        raise HTTPException(status_code=500, detail={"message": "Внутренняя ошибка: нет рыночной колонки"})

    stock_px = prices.drop(columns=[mkt_col])
    mkt_px = prices[mkt_col]

    rets = analytics.simple_returns_from_prices(pd.concat([stock_px, mkt_px.rename(mkt_col)], axis=1)).dropna(
        how="any"
    )
    if rets.shape[0] < request.trading_days:
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Недостаточно совместных дней доходности: {rets.shape[0]} < {request.trading_days}",
            },
        )

    rets = rets.iloc[-request.trading_days :]
    mkt_r = rets[mkt_col].to_numpy(dtype=float)
    stock_cols = [c for c in rets.columns if c != mkt_col]

    per: List[TickerMetrics] = []
    betas: List[float] = []
    for i, col in enumerate(stock_cols):
        ri = rets[col].to_numpy(dtype=float)
        b = analytics.ols_beta_y_on_x(ri, mkt_r)
        if not np.isfinite(b):
            b = 1.0
        betas.append(float(b))
        per.append(
            TickerMetrics(
                ticker=col,
                weight=round(float(w[i]), 6),
                beta=round(float(b), 4),
            )
        )

    port_beta = float((w * np.asarray(betas)).sum())
    pr = analytics.portfolio_returns(rets[stock_cols], w.tolist())
    var_1d, es_1d = analytics.historical_var_es(pr, request.alpha)

    alpha = request.alpha
    conf = round(1.0 - alpha, 6)

    meta = AnalyzeMeta(
        trading_days_requested=request.trading_days,
        observations=int(pr.size),
        date_from=d_start.isoformat(),
        date_to=d_end.isoformat(),
        currency="RUB",
    )

    positions_normalized: List[Dict[str, Any]] = [{"ticker": t, "weight": round(float(wi), 6)} for t, wi in norm]

    warnings: List[str] = [
        "β оценена по OLS доходности актива к доходности индекса без безрисковой ставки (учебная модель).",
        "VaR/ES — исторические по портфельной дневной доходности; не прогноз и не рекомендация.",
    ]

    mkt_only_rets = rets[mkt_col].to_numpy(dtype=float)
    chart = ChartSeries(
        dates=[d.strftime("%Y-%m-%d") for d in rets.index],
        portfolio_nav=analytics.cumulative_nav(pr).tolist(),
        index_nav=analytics.cumulative_nav(mkt_only_rets).tolist(),
    )

    return AnalyzeResponse(
        mode="historical",
        positions_normalized=positions_normalized,
        portfolio_beta=round(port_beta, 4),
        per_ticker=per,
        var_1d=round(float(var_1d), 6),
        es_1d=round(float(es_1d), 6),
        alpha=alpha,
        confidence_level=conf,
        market_index=request.market_index.strip().upper(),
        meta=meta,
        warnings=warnings,
        chart=chart,
    )
