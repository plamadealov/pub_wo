import os

from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import PROJECT_ROOT
from app.routers import news as news_router
from app.routers import portfolio as portfolio_router

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "backend" / ".env")


def _cors_origins() -> list[str]:
    raw = os.environ.get("ALLOW_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


app = FastAPI(title="CAPM / VaR / ES API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio_router.router, prefix="/api")
app.include_router(news_router.router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Продакшн: один хост (VPS) — отдаём `frontend/dist` после `npm run build`.
_dist = PROJECT_ROOT / "frontend" / "dist"
if _dist.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(_dist), html=True),
        name="frontend",
    )
