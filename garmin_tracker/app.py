"""Garmin Health Tracker - Web Application."""

import asyncio
import logging
import os
from functools import partial
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import database as db
from . import garmin_sync as sync
from . import llm_analyzer as llm

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db.init_db()

app = FastAPI(title="Garmin Health Tracker")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _is_configured() -> bool:
    """Check if minimum credentials are set."""
    return bool(os.environ.get("GARMIN_EMAIL") and os.environ.get("GARMIN_PASSWORD"))


def _mask_key(key: str | None) -> str:
    """Mask an API key for display."""
    if not key or len(key) < 15:
        return ""
    return key[:7] + "..." + key[-4:]


def _save_env(**kwargs):
    """Update .env file with new values, preserving existing ones."""
    existing = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()

    existing.update({k: v for k, v in kwargs.items() if v is not None})

    lines = [f"{k}={v}" for k, v in existing.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n")

    # Reload into current process
    for k, v in existing.items():
        os.environ[k] = v


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not _is_configured():
        return RedirectResponse(url="/setup", status_code=302)
    min_date, max_date = db.get_date_range()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "min_date": min_date,
            "max_date": max_date,
        },
    )


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    return templates.TemplateResponse(
        "setup.html",
        {
            "request": request,
            "garmin_email": os.environ.get("GARMIN_EMAIL", ""),
            "anthropic_key_masked": _mask_key(os.environ.get("ANTHROPIC_API_KEY")),
        },
    )


@app.post("/api/setup")
async def api_setup(request: Request):
    body = await request.json()
    email = body.get("garmin_email", "").strip()
    password = body.get("garmin_password")
    api_key = body.get("anthropic_key")
    skip_validation = body.get("skip_validation", False)

    if not email:
        return JSONResponse({"status": "error", "message": "Garmin email is required"}, status_code=400)

    if not password:
        password = os.environ.get("GARMIN_PASSWORD")
    if not password:
        return JSONResponse({"status": "error", "message": "Garmin password is required"}, status_code=400)

    garmin_verified = False
    if not skip_validation:
        try:
            from garminconnect import Garmin
            client = Garmin(email, password)
            client.login()
            token_dir = os.path.join(os.path.dirname(__file__), "..", ".garminconnect")
            client.garth.dump(token_dir)
            sync._client = None
            garmin_verified = True
        except Exception as e:
            logger.warning(f"Garmin login failed: {e}")
            return JSONResponse(
                {"status": "error", "message": f"Garmin login failed: {e}"},
                status_code=400,
            )

    env_updates = {"GARMIN_EMAIL": email, "GARMIN_PASSWORD": password}
    if api_key and not api_key.startswith("sk-ant-..."):
        env_updates["ANTHROPIC_API_KEY"] = api_key
    _save_env(**env_updates)

    msg = "Connected successfully" if garmin_verified else "Credentials saved (Garmin login will be tested on first sync)"
    return {"status": "ok", "message": msg}


@app.post("/api/sync")
async def api_sync(request: Request):
    body = await request.json()
    days = body.get("days", 7)
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, partial(sync.sync_recent, days=days))
        return {"status": "ok", "results": results}
    except Exception as e:
        logger.exception("Sync failed")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/ask")
async def api_ask(request: Request):
    body = await request.json()
    question = body.get("question", "").strip()
    days = body.get("days", 30)
    model = body.get("model")
    if not question:
        return JSONResponse({"error": "No question provided"}, status_code=400)
    try:
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(None, partial(llm.analyze, question, days=days, model=model))
        return {"answer": answer}
    except Exception as e:
        logger.exception("LLM analysis failed")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/models")
async def api_models():
    """Return available models and Ollama status."""
    models = llm.get_available_models()
    ollama = llm.check_ollama_status()
    return {"models": models, "ollama": ollama}


@app.get("/api/chart/{metric}")
async def api_chart(metric: str, days: int = 30):
    data = db.get_chart_data(metric, days=days)
    return {"metric": metric, "data": data}


@app.get("/api/stats")
async def api_stats():
    with db.get_db() as conn:
        total_days = conn.execute("SELECT COUNT(*) as c FROM daily_stats").fetchone()["c"]
        total_activities = conn.execute("SELECT COUNT(*) as c FROM activities").fetchone()["c"]
        min_date, max_date = db.get_date_range()
    return {
        "total_days": total_days,
        "total_activities": total_activities,
        "date_range": {"min": min_date, "max": max_date},
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("garmin_tracker.app:app", host="0.0.0.0", port=8001, reload=True)
