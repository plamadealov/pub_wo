from __future__ import annotations

import os
from pathlib import Path

# Корень проекта capm-var-proj (родитель каталога backend)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DB_PATH = DATA_DIR / "moex_cache.sqlite"

DEFAULT_MOEX_USER_AGENT = "capm-var-proj/0.1 (educational; contact: local)"


def moex_user_agent() -> str:
    return os.environ.get("MOEX_ISS_USER_AGENT", DEFAULT_MOEX_USER_AGENT).strip() or DEFAULT_MOEX_USER_AGENT


DEFAULT_NEWS_HTTP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def news_http_user_agent() -> str:
    return (
        os.environ.get("NEWS_HTTP_USER_AGENT", DEFAULT_NEWS_HTTP_USER_AGENT).strip()
        or DEFAULT_NEWS_HTTP_USER_AGENT
    )


def news_api_key() -> str:
    """Пустая строка, если ключа нет (не читаем файлы .env — только os.environ)."""
    return os.environ.get("NEWS_API_KEY", "").strip()
