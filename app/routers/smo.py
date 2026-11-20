import json
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from ..agents.crew_orchestrator import run_smo_and_community_crew
from ..auth import get_current_user
from ..compat import to_dict
from ..database import db_session
from ..models import ClientBriefPayload, SMOCampaignRequest

router = APIRouter(prefix="/api/v1/smo", tags=["smo"])


async def _execute_smo_job(
    campaign_id: int,
    user_id: int,
    source_url: str,
    topic: str,
    platforms: list[str],
) -> None:
    try:
        with db_session() as conn:
            conn.execute("UPDATE smo_campaigns SET status = 'running' WHERE id = ?", (campaign_id,))
            brief_row = conn.execute(
                "SELECT * FROM client_briefs WHERE user_id = ?",
                (user_id,),
            ).fetchone()

        if brief_row:
            brief = ClientBriefPayload(
                target_keywords=json.loads(brief_row["target_keywords_json"]),
                icp=brief_row["icp"],
                tone=brief_row["tone"],
                conversion_goals=brief_row["conversion_goals"],
            )
        else:
            brief = ClientBriefPayload()

        output = await run_smo_and_community_crew(source_url, topic, platforms, brief)
        with db_session() as conn:
            conn.execute(
                """
                UPDATE smo_campaigns
                SET status = 'completed',
                    platforms_json = ?,
                    community_json = ?,
                    draftpilot_queue_json = ?,
                    completed_at = datetime('now')
                WHERE id = ?
                """,
                (
                    json.dumps([to_dict(a) for a in output.platform_assets]),
                    json.dumps([to_dict(c) for c in output.community_engagements]),
                    json.dumps(output.draftpilot_queue),
                    campaign_id,
                ),
            )
    except Exception:
        with db_session() as conn:
            conn.execute("UPDATE smo_campaigns SET status = 'failed' WHERE id = ?", (campaign_id,))


@router.post("/campaigns", status_code=status.HTTP_202_ACCEPTED)
def create_smo_campaign(
    payload: SMOCampaignRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    url_str = str(payload.source_url)
    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO smo_campaigns (user_id, audit_id, source_url, topic, status)
            VALUES (?, ?, ?, ?, 'queued')
            """,
            (current_user["id"], payload.audit_id, url_str, payload.topic.strip()),
        )
        campaign_id = cur.lastrowid

    background_tasks.add_task(
        _execute_smo_job,
        campaign_id,
        current_user["id"],
        url_str,
        payload.topic.strip(),
        payload.platforms,
    )
    return {
        "campaign_id": campaign_id,
        "status": "queued",
        "platforms": payload.platforms,
        "message": "SMO & Community campaign queued (LinkedIn, Instagram, Facebook, YouTube, DraftPilot, Reddit, Quora).",
    }


@router.get("/campaigns")
def list_smo_campaigns(current_user: dict = Depends(get_current_user)):
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM smo_campaigns WHERE user_id = ? ORDER BY id DESC",
            (current_user["id"],),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "audit_id": r["audit_id"],
            "source_url": r["source_url"],
            "topic": r["topic"],
            "status": r["status"],
            "platform_assets": json.loads(r["platforms_json"] or "[]"),
            "community_engagements": json.loads(r["community_json"] or "[]"),
            "draftpilot_queue": json.loads(r["draftpilot_queue_json"] or "[]"),
            "created_at": r["created_at"],
            "completed_at": r["completed_at"],
        }
        for r in rows
    ]


@router.patch("/campaigns/{campaign_id}/draftpilot/{item_index}")
def approve_draftpilot_item(
    campaign_id: int,
    item_index: int,
    current_user: dict = Depends(get_current_user),
):
    with db_session() as conn:
        row = conn.execute(
            "SELECT draftpilot_queue_json FROM smo_campaigns WHERE id = ? AND user_id = ?",
            (campaign_id, current_user["id"]),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")
        queue = json.loads(row["draftpilot_queue_json"] or "[]")
        if item_index < 0 or item_index >= len(queue):
            raise HTTPException(status_code=404, detail="DraftPilot item index out of range")
        queue[item_index]["status"] = "approved_and_scheduled"
        conn.execute(
            "UPDATE smo_campaigns SET draftpilot_queue_json = ? WHERE id = ?",
            (json.dumps(queue), campaign_id),
        )
    return {"campaign_id": campaign_id, "item": queue[item_index]}
