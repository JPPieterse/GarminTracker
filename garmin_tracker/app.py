"""Garmin Health Tracker - Web Application."""

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import database as db
from . import garmin_sync as sync
from . import llm_analyzer as llm

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

db.init_db()

app = FastAPI(title="Garmin Health Tracker")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    min_date, max_date = db.get_date_range()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "min_date": min_date,
            "max_date": max_date,
        },
    )


@app.post("/api/sync")
async def api_sync(request: Request):
    body = await request.json()
    days = body.get("days", 7)
    try:
        results = sync.sync_recent(days=days)
        return {"status": "ok", "results": results}
    except Exception as e:
        logger.exception("Sync failed")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/ask")
async def api_ask(request: Request):
    body = await request.json()
    question = body.get("question", "").strip()
    days = body.get("days", 30)
    if not question:
        return JSONResponse({"error": "No question provided"}, status_code=400)
    try:
        answer = llm.analyze(question, days=days)
        return {"answer": answer}
    except Exception as e:
        logger.exception("LLM analysis failed")
        return JSONResponse({"error": str(e)}, status_code=500)


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

    uvicorn.run("garmin_tracker.app:app", host="0.0.0.0", port=8000, reload=True)
