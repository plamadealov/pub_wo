from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict, List, Tuple

import httpx

from app.config import moex_user_agent


class MoexIssError(RuntimeError):
    pass


def _parse_history_block(payload: dict) -> Tuple[List[str], List[list]]:
    hist = payload.get("history")
    if not hist:
        return [], []
    cols = hist.get("columns") or []
    data = hist.get("data") or []
    return cols, data


def _rows_to_date_close(cols: List[str], rows: List[list]) -> List[Tuple[date, float]]:
    """
    Одна точка на календарный день. В ISS по одной дате может быть несколько строк
    (TRADINGSESSION). Предпочитаем сессию 3 (итог дня); если её нет — берём любую
    доступную, иначе пересечение дат между бумагами схлопывается почти в ноль.
    """
    if not cols or not rows:
        return []
    try:
        i_date = cols.index("TRADEDATE")
        i_close = cols.index("CLOSE")
    except ValueError as e:
        raise MoexIssError("Неожиданная схема MOEX ISS: нет TRADEDATE/CLOSE") from e
    i_sess = cols.index("TRADINGSESSION") if "TRADINGSESSION" in cols else None
    per_day: Dict[date, List[Tuple[int, float]]] = defaultdict(list)
    for row in rows:
        if i_date >= len(row) or i_close >= len(row):
            continue
        ds = row[i_date]
        cl = row[i_close]
        if ds is None or cl is None:
            continue
        sess_key = 99
        if i_sess is not None and i_sess < len(row) and row[i_sess] is not None:
            try:
                sess_key = int(row[i_sess])
            except (TypeError, ValueError):
                sess_key = 99
        try:
            d = date.fromisoformat(str(ds))
            per_day[d].append((sess_key, float(cl)))
        except (TypeError, ValueError):
            continue
    by_day: Dict[date, float] = {}
    for d, items in per_day.items():
        day_totals = [c for s, c in items if s == 3]
        if day_totals:
            by_day[d] = day_totals[-1]
        else:
            by_day[d] = sorted(items, key=lambda x: x[0])[0][1]
    return sorted(by_day.items(), key=lambda x: x[0])


class MoexIssClient:
    """Клиент исторических дневных закрытий MOEX ISS (акции TQBR и индексы)."""

    BASE = "https://iss.moex.com/iss"

    def __init__(self, timeout: float = 45.0) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": moex_user_agent()},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> MoexIssClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetch_share_history_tqbr(self, ticker: str, d0: date, d1: date) -> List[Tuple[date, float]]:
        t = ticker.strip().upper()
        url = f"{self.BASE}/history/engines/stock/markets/shares/boards/TQBR/securities/{t}.json"
        return self._fetch_paginated(url, d0, d1)

    def fetch_index_history(self, secid: str, d0: date, d1: date) -> List[Tuple[date, float]]:
        s = secid.strip().upper()
        url = f"{self.BASE}/history/engines/stock/markets/index/securities/{s}.json"
        return self._fetch_paginated(url, d0, d1)

    def probe_share_tqbr(self, ticker: str) -> bool:
        """Есть ли хотя бы одна строка истории."""
        t = ticker.strip().upper()
        url = f"{self.BASE}/history/engines/stock/markets/shares/boards/TQBR/securities/{t}.json"
        try:
            rows = self._fetch_paginated(url, date(2000, 1, 1), date.today(), limit=1, max_rows=1)
        except MoexIssError:
            return False
        return len(rows) > 0

    def _fetch_paginated(
        self,
        url: str,
        d0: date,
        d1: date,
        limit: int = 100,
        max_rows: int | None = None,
    ) -> List[Tuple[date, float]]:
        start = 0
        merged: Dict[date, float] = {}
        while True:
            params = {
                "from": d0.isoformat(),
                "till": d1.isoformat(),
                "start": start,
                "limit": limit,
            }
            r = self._client.get(url, params=params)
            if r.status_code >= 400:
                raise MoexIssError(f"MOEX HTTP {r.status_code} для {url}")
            cols, data = _parse_history_block(r.json())
            if not data:
                break
            chunk = _rows_to_date_close(cols, data)
            for d, c in chunk:
                merged[d] = c
                if max_rows is not None and len(merged) >= max_rows:
                    return sorted(merged.items(), key=lambda x: x[0])
            if len(data) < limit:
                break
            start += len(data)
        return sorted(merged.items(), key=lambda x: x[0])
