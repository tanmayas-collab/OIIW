from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .agents.crew_orchestrator import using_crewai_runtime
from .config import APP_TITLE, APP_VERSION
from .database import get_connection, init_db
from .routers import audits, auth, billing, monitors, onboarding, smo

BASE_APP_DIR = Path(__file__).resolve().parent

init_db()

app = FastAPI(title=APP_TITLE, version=APP_VERSION)

app.mount("/static", StaticFiles(directory=str(BASE_APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_APP_DIR / "templates"))

app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(audits.router)
app.include_router(monitors.router)
app.include_router(smo.router)
app.include_router(billing.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health_check():
    conn = get_connection()
    try:
        wal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    finally:
        conn.close()
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "sqlite_journal_mode": wal_mode,
        "agent_runtime": "crewai" if using_crewai_runtime() else "local_pydantic_crew_adapter",
    }


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "title": APP_TITLE})
