import sqlite3
from contextlib import contextmanager
from .config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def db_session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db_session() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                plan_tier TEXT NOT NULL DEFAULT 'starter',
                gstin TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS client_briefs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                target_keywords_json TEXT NOT NULL DEFAULT '[]',
                icp TEXT NOT NULL DEFAULT '',
                tone TEXT NOT NULL DEFAULT 'authoritative and clear',
                conversion_goals TEXT NOT NULL DEFAULT '',
                chat_history_json TEXT NOT NULL DEFAULT '[]',
                completed INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                seo_score INTEGER DEFAULT 0,
                aeo_score INTEGER DEFAULT 0,
                overall_score INTEGER DEFAULT 0,
                crawl_result_json TEXT NOT NULL DEFAULT '{}',
                critical_errors_json TEXT NOT NULL DEFAULT '[]',
                error_message TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS optimizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                onpage_output_json TEXT NOT NULL DEFAULT '{}',
                offpage_output_json TEXT NOT NULL DEFAULT '{}',
                error_message TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT DEFAULT '',
                FOREIGN KEY (audit_id) REFERENCES audits(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS monitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                monitor_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                baseline_json TEXT NOT NULL DEFAULT '{}',
                latest_json TEXT NOT NULL DEFAULT '{}',
                alerts_json TEXT NOT NULL DEFAULT '[]',
                last_checked_at TEXT NOT NULL DEFAULT (datetime('now')),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS smo_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                audit_id INTEGER,
                source_url TEXT NOT NULL,
                topic TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'queued',
                platforms_json TEXT NOT NULL DEFAULT '{}',
                community_json TEXT NOT NULL DEFAULT '{}',
                draftpilot_queue_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT DEFAULT '',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tier TEXT NOT NULL,
                base_inr INTEGER NOT NULL,
                gst_inr INTEGER NOT NULL,
                total_inr INTEGER NOT NULL,
                outcome_cap_inr INTEGER NOT NULL,
                milestones_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
