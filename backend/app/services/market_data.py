from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Callable, Dict, List, Tuple

import pandas as pd

from app.config import CACHE_DB_PATH
from app.moex.cache import count_in_range, init_db, read_series, upsert_rows
from app.moex.client import MoexIssClient, MoexIssError


def instrument_id_share(ticker: str) -> str:
    return f"share:{ticker.strip().upper()}"


def instrument_id_index(secid: str) -> str:
    return f"index:{secid.strip().upper()}"


def _need_calendar_span(trading_days: int) -> int:
    """Грубая оценка календарных дней, чтобы набрать достаточно торговых точек."""
    return int(trading_days * 1.75 + 60)


def load_series_with_cache(
    conn: sqlite3.Connection,
    client: MoexIssClient,
    instrument_id: str,
    fetcher: Callable[[date, date], List[Tuple[date, float]]],
    d0: date,
    d1: date,
    min_points: int,
) -> pd.Series:
    """
    Читает кэш; если строк мало — догружает MOEX и обновляет SQLite.
    Возвращает Series с индексом datetime64[ns] для унификации с pandas.
    """
    cached = read_series(conn, instrument_id, d0, d1)
    n = count_in_range(conn, instrument_id, d0, d1)
    if n < min_points:
        try:
            fresh = fetcher(d0, d1)
        except MoexIssError as e:
            if len(cached) >= min_points:
                pass
            elif not cached:
                raise
            else:
                raise MoexIssError(
                    f"{instrument_id}: в кэше только {len(cached)} дней за период "
                    f"(нужно ≥ {min_points}), повторный запрос к MOEX не удался: {e}"
                ) from e
        else:
            upsert_rows(conn, instrument_id, fresh)
            cached = read_series(conn, instrument_id, d0, d1)
    if not cached:
        raise MoexIssError(f"Нет данных MOEX для {instrument_id} за период {d0}…{d1}")
    if len(cached) < min_points:
        d_lo, d_hi = cached[0][0], cached[-1][0]
        hint = ""
        if (d1 - d_hi).days > 30:
            hint = (
                " Последняя доступная дата заметно раньше конца запрошенного окна — "
                "часто так бывает, если бумагу сняли с режима TQBR или она перестала "
                "торговаться на этой доске (например, TCSG на TQBR: данные MOEX до ~27.11.2024). "
                "Замените тикер или сократите окно так, чтобы все бумаги имели общую историю."
            )
        raise MoexIssError(
            f"{instrument_id}: после загрузки только {len(cached)} торговых дней в окне [{d0}…{d1}] "
            f"(нужно ≥ {min_points}). Фактический диапазон цен в ответе биржи: {d_lo} … {d_hi}.{hint}"
        )
    idx = pd.to_datetime([d.isoformat() for d, _ in cached])
    vals = [c for _, c in cached]
    return pd.Series(vals, index=idx, name=instrument_id).sort_index()


def build_aligned_closes(
    client: MoexIssClient,
    tickers: List[str],
    market_index: str,
    trading_days: int,
) -> Tuple[pd.DataFrame, date, date]:
    """
    DataFrame колонок: каждый тикер + колонка __market__ для индекса.
    Индекс — торговые даты пересечения (внутренние даты с полным набором цен).
    """
    init_db(CACHE_DB_PATH)
    d1 = date.today()
    span = _need_calendar_span(trading_days)
    d0 = d1 - timedelta(days=span)
    min_points = trading_days + 30

    conn = sqlite3.connect(CACHE_DB_PATH)

    series_map: Dict[str, pd.Series] = {}
    try:
        for t in tickers:
            iid = instrument_id_share(t)

            def _fetch_shares(a: date, b: date, tt: str = t) -> List[Tuple[date, float]]:
                return client.fetch_share_history_tqbr(tt, a, b)

            s = load_series_with_cache(conn, client, iid, _fetch_shares, d0, d1, min_points)
            series_map[t.upper()] = s

        mid = market_index.upper()
        miid = instrument_id_index(mid)

        def _fetch_idx(a: date, b: date) -> List[Tuple[date, float]]:
            return client.fetch_index_history(mid, a, b)

        sm = load_series_with_cache(conn, client, miid, _fetch_idx, d0, d1, min_points)
        series_map["__market__"] = sm
    finally:
        conn.close()

    df = pd.DataFrame(series_map)
    counts = {k: int(df[k].notna().sum()) for k in df.columns}
    df = df.dropna(how="any")
    if df.shape[0] < trading_days + 2:
        raise MoexIssError(
            f"После выравнивания слишком мало общих торговых дней: {df.shape[0]}, "
            f"нужно ≥ {trading_days + 2}. "
            f"Обычно один из тикеров имеет короткую историю или не совпадает с остальными по датам. "
            f"Число дней с ценой по каждому ряду (до пересечения): {counts}. "
            f"Если только что обновили приложение, удалите кэш: data/moex_cache.sqlite и повторите расчёт."
        )
    used = df.iloc[-(trading_days + 1) :]
    d_start = used.index.min().date()
    d_end = used.index.max().date()
    return used, d_start, d_end
