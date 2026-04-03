from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd


def simple_returns_from_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Простая дневная доходность по закрытиям; первая строка — NaN, отбрасывается вызывающим."""
    return prices.pct_change()


def ols_beta_y_on_x(y: np.ndarray, x: np.ndarray) -> float:
    """Наклон OLS y ~ const + x; совпадает с cov(x,y)/var(x) при демированных рядах."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    if x.size < 5:
        return float("nan")
    vx = np.var(x, ddof=1)
    if vx < 1e-18:
        return float("nan")
    cx = x - x.mean()
    cy = y - y.mean()
    return float((cx * cy).sum() / (cx * cx).sum())


def portfolio_returns(stock_returns: pd.DataFrame, weights: List[float]) -> np.ndarray:
    """stock_returns — только колонки акций (без рынка), порядок совпадает с weights."""
    mat = stock_returns.to_numpy(dtype=float)
    w = np.asarray(weights, dtype=float)
    return (mat @ w).ravel()


def historical_var_es(returns: np.ndarray, alpha: float) -> Tuple[float, float]:
    """
    Исторические VaR и ES на уровне alpha (нижний хвост).
    returns — простые дневные доходности портфеля.
    VaR и ES — положительные числа (величина потери в долях).
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < 10:
        return float("nan"), float("nan")
    q = float(np.quantile(r, alpha))
    var_loss = float(-q)
    tail = r[r <= q]
    if tail.size == 0:
        es_loss = var_loss
    else:
        es_loss = float(-float(tail.mean()))
    if var_loss < 0:
        var_loss = 0.0
    if es_loss < 0:
        es_loss = 0.0
    if es_loss + 1e-12 < var_loss:
        es_loss = var_loss
    return var_loss, es_loss


def cumulative_nav(returns: np.ndarray) -> np.ndarray:
    """Нормированная «стоимость» от 1.0 по простым дневным доходностям."""
    r = np.asarray(returns, dtype=float)
    nav = np.cumprod(1.0 + r)
    if nav.size == 0:
        return nav
    base = nav[0]
    if abs(base) < 1e-15:
        return np.ones_like(nav)
    return nav / base
