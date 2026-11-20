import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "saas_portal.db"))
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
CREWAI_ENABLED = os.getenv("CREWAI_ENABLED", "auto")  # auto | true | false
APP_TITLE = "PulseRank AI — SEO, AEO & SMO SaaS Portal"
APP_VERSION = "1.0.0"
GST_RATE = 0.18
