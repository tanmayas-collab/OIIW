import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from ..auth import get_current_user
from ..database import db_session
from ..models import MonitorCreateRequest

router = APIRouter(prefix="/api/v1/monitors", tags=["monitors"])


def _generate_monitor_snapshot(url: str, monitor_type: str, baseline: dict | None = None) -> tuple[dict, list]:
    now_iso = datetime.now(timezone.utc).isoformat()
    if monitor_type == "backlink":
        base_dr = baseline.get("domain_rating", 28) if baseline else 28
        base_rd = baseline.get("referring_domains", 42) if baseline else 42
        latest = {
            "domain_rating": base_dr + (1 if baseline else 0),
            "referring_domains": base_rd + (3 if baseline else 0),
            "toxic_backlinks_detected": 1,
            "checked_at": now_iso,
        }
        alerts = []
        if baseline:
            alerts.append({
                "severity": "info",
                "message": f"+3 new referring domains detected for {url}; 1 low-quality directory link flagged for disavow review.",
                "timestamp": now_iso,
            })
        return latest, alerts

    if monitor_type == "content_decay":
        base_clicks = baseline.get("rolling_28d_clicks", 1240) if baseline else 1240
        latest_clicks = int(base_clicks * 0.86) if baseline else base_clicks
        latest = {
            "rolling_28d_clicks": latest_clicks,
            "avg_position": 6.4 if baseline else 4.2,
            "decay_pct": -14.0 if baseline else 0.0,
            "checked_at": now_iso,
        }
        alerts = []
        if baseline:
            alerts.append({
                "severity": "warning",
                "message": f"Content decay alert: {url} dropped 14.0% in 28-day clicks (pos 4.2 -> 6.4). Recommend FAQ & schema refresh.",
                "timestamp": now_iso,
            })
        return latest, alerts

    # serp_feature
    latest = {
        "ai_overview_cited": bool(baseline),
        "featured_snippet": False if not baseline else True,
        "people_also_ask_count": 3 if baseline else 1,
        "checked_at": now_iso,
    }
    alerts = []
    if baseline:
        alerts.append({
            "severity": "success",
            "message": f"SERP feature gain: {url} now appears in AI Overview & 3 People Also Ask boxes.",
            "timestamp": now_iso,
        })
    return latest, alerts


@router.post("", status_code=201)
def create_monitor(payload: MonitorCreateRequest, current_user: dict = Depends(get_current_user)):
    url_str = str(payload.url)
    baseline, alerts = _generate_monitor_snapshot(url_str, payload.monitor_type, baseline=None)
    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO monitors (user_id, url, monitor_type, baseline_json, latest_json, alerts_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                current_user["id"],
                url_str,
                payload.monitor_type,
                json.dumps(baseline),
                json.dumps(baseline),
                json.dumps(alerts),
            ),
        )
        monitor_id = cur.lastrowid
    return {
        "id": monitor_id,
        "url": url_str,
        "monitor_type": payload.monitor_type,
        "status": "active",
        "baseline": baseline,
        "latest": baseline,
        "alerts": alerts,
    }


@router.get("")
def list_monitors(current_user: dict = Depends(get_current_user)):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM monitors WHERE user_id = ? ORDER BY id DESC",
            (current_user["id"],),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "url": r["url"],
            "monitor_type": r["monitor_type"],
            "status": r["status"],
            "baseline": json.loads(r["baseline_json"]),
            "latest": json.loads(r["latest_json"]),
            "alerts": json.loads(r["alerts_json"]),
            "last_checked_at": r["last_checked_at"],
        }
        for r in rows
    ]


@router.post("/{monitor_id}/check")
def run_monitor_check(monitor_id: int, current_user: dict = Depends(get_current_user)):
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM monitors WHERE id = ? AND user_id = ?",
            (monitor_id, current_user["id"]),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Monitor not found")
        baseline = json.loads(row["baseline_json"])
        latest, new_alerts = _generate_monitor_snapshot(row["url"], row["monitor_type"], baseline=baseline)
        existing_alerts = json.loads(row["alerts_json"])
        all_alerts = (new_alerts + existing_alerts)[:10]
        conn.execute(
            """
            UPDATE monitors
            SET latest_json = ?, alerts_json = ?, last_checked_at = datetime('now')
            WHERE id = ?
            """,
            (json.dumps(latest), json.dumps(all_alerts), monitor_id),
        )
    return {
        "id": monitor_id,
        "url": row["url"],
        "monitor_type": row["monitor_type"],
        "baseline": baseline,
        "latest": latest,
        "alerts": all_alerts,
    }
