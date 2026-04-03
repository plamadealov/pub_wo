"""Фаза 0: детерминированный mock-ответ от нормализованных весов (без котировок)."""

from __future__ import annotations

from typing import Dict, List, Tuple

from app.schemas.portfolio import (
    AnalyzeMeta,
    AnalyzeRequest,
    AnalyzeResponse,
    TickerMetrics,
)

# Условные β для демонстрации; в фазе 2 заменяются оценкой по данным
_MOCK_BETAS: Dict[str, float] = {
    "SBER": 1.12,
    "GAZP": 0.88,
    "LKOH": 1.05,
    "GMKN": 0.92,
    "YNDX": 1.25,
    "IMOEX": 1.0,
}


def _normalize_weights(request: AnalyzeRequest) -> List[Tuple[str, float]]:
    if request.positions[0].weight is not None:
        raw = [(p.ticker.strip().upper(), float(p.weight)) for p in request.positions]
        s = sum(w for _, w in raw)
        return [(t, w / s) for t, w in raw]
    raw = [(p.ticker.strip().upper(), float(p.notional)) for p in request.positions]
    s = sum(n for _, n in raw)
    return [(t, n / s) for t, n in raw]


def _mock_beta(ticker: str) -> float:
    return _MOCK_BETAS.get(ticker.upper(), 1.0)


def build_mock_analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    norm = _normalize_weights(request)
    per: List[TickerMetrics] = []
    port_beta = 0.0
    for t, w in norm:
        b = _mock_beta(t)
        per.append(TickerMetrics(ticker=t, weight=round(w, 6), beta=round(b, 4)))
        port_beta += w * b
    port_beta = round(port_beta, 4)

    # Положительные числа = доля потери; зависят от β только для разнообразия mock
    var_1d = round(0.018 + 0.012 * max(port_beta, 0.2), 6)
    es_1d = round(var_1d * 1.28, 6)
    alpha = request.alpha
    conf = round(1.0 - alpha, 6)

    meta = AnalyzeMeta(
        trading_days_requested=request.trading_days,
        observations=378,
        date_from=None,
        date_to=None,
        currency="RUB",
    )

    positions_normalized = [{"ticker": t, "weight": round(w, 6)} for t, w in norm]

    warnings = [
        "Режим mock: нет загрузки котировок; β, VaR и ES условные, заменятся в фазах 1–2.",
    ]

    return AnalyzeResponse(
        mode="mock",
        positions_normalized=positions_normalized,
        portfolio_beta=port_beta,
        per_ticker=per,
        var_1d=var_1d,
        es_1d=es_1d,
        alpha=alpha,
        confidence_level=conf,
        market_index=request.market_index.strip().upper(),
        meta=meta,
        warnings=warnings,
        chart=None,
    )
