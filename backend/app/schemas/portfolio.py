from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class PositionInput(BaseModel):
    """Одна позиция: либо веса по всему портфелю, либо номиналы — не смешивать в одном запросе."""

    ticker: str = Field(..., min_length=1, description="Тикер в пользовательской нотации, напр. SBER")
    weight: Optional[float] = Field(
        default=None,
        gt=0,
        description="Доля в портфеле; сумма по портфелю > 0, нормализуется на бэкенде",
    )
    notional: Optional[float] = Field(
        default=None,
        gt=0,
        description="Условная сумма в одной валюте; веса = notional_i / sum(notional)",
    )

    @model_validator(mode="after")
    def weight_xor_notional(self) -> PositionInput:
        if (self.weight is None) == (self.notional is None):
            raise ValueError("Укажите ровно одно из полей: weight или notional")
        return self


class AnalyzeRequest(BaseModel):
    positions: List[PositionInput] = Field(..., min_length=1)
    trading_days: int = Field(
        default=500,
        ge=50,
        le=2500,
        description="Глубина окна в торговых днях для доходностей и рисков",
    )
    alpha: float = Field(
        default=0.05,
        gt=0,
        lt=0.5,
        description="Вероятность хвоста; VaR/ES на уровне доверия (1 - alpha), напр. alpha=0.05 → 95%",
    )
    market_index: str = Field(
        default="IMOEX",
        min_length=1,
        description="Идентификатор индекса MOEX для CAPM (доходность индекса)",
    )
    use_mock: bool = Field(
        default=False,
        description="Если true — ответ фазы 0 без MOEX (для тестов и демо)",
    )

    @model_validator(mode="after")
    def consistent_weighting_mode(self) -> AnalyzeRequest:
        use_weights = [p.weight is not None for p in self.positions]
        if all(use_weights):
            return self
        if not any(use_weights):
            return self
        raise ValueError("Смешивание weight и notional в одном портфеле не поддерживается")


class ChartSeries(BaseModel):
    dates: List[str]
    portfolio_nav: List[float]
    index_nav: List[float]


class AnalyzeMeta(BaseModel):
    trading_days_requested: int
    observations: Optional[int] = Field(
        description="Число дневных доходностей, на которых посчитаны риски"
    )
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    currency: str = "RUB"
    return_definition: Literal["simple_daily"] = "simple_daily"
    risk_convention: Literal["var_es_as_positive_loss_fraction"] = "var_es_as_positive_loss_fraction"


class TickerMetrics(BaseModel):
    ticker: str
    weight: float = Field(description="Нормализованный вес")
    beta: float = Field(description="β к доходности выбранного индекса (OLS)")


class AnalyzeResponse(BaseModel):
    mode: Literal["mock", "historical"]
    positions_normalized: List[Dict[str, Any]] = Field(
        description="Тикер и нормализованный вес после запроса"
    )
    portfolio_beta: float
    per_ticker: List[TickerMetrics]
    var_1d: float = Field(
        description="Однодневный исторический VaR: положительная доля = величина потери"
    )
    es_1d: float = Field(
        description="Expected Shortfall (пробой) на том же alpha: положительная доля — средний хвостовой убыток"
    )
    alpha: float
    confidence_level: float = Field(description="1 - alpha")
    market_index: str
    meta: AnalyzeMeta
    warnings: List[str] = Field(default_factory=list)
    chart: Optional[ChartSeries] = Field(
        default=None,
        description="Нормированные NAV (от 1.0) для графика; только для historical",
    )


class InstrumentResolveResponse(BaseModel):
    query: str
    canonical_ticker: Optional[str] = None
    board: Optional[str] = Field(default=None, description="Режим торгов MOEX, если известен")
    source: Literal["mock", "moex"] = "moex"
    note: str = ""
