import json
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from ..agents.crew_orchestrator import run_onpage_and_offpage_crews
from ..auth import get_current_user
from ..compat import to_json
from ..database import db_session
from ..models import AuditCreateRequest, ClientBriefPayload, CrawlResult
from ..services.crawler import crawl_single_url

router = APIRouter(prefix="/api/v1/audits", tags=["audits"])


async def _execute_audit_job(audit_id: int, url: str) -> None:
    try:
        with db_session() as conn:
            conn.execute(
                "UPDATE audits SET status = 'running', updated_at = datetime('now') WHERE id = ?",
                (audit_id,),
            )
        crawl, seo_score, aeo_score, overall_score, errors = await crawl_single_url(url)
        with db_session() as conn:
            conn.execute(
                """
                UPDATE audits
                SET status = 'completed',
                    seo_score = ?,
                    aeo_score = ?,
                    overall_score = ?,
                    crawl_result_json = ?,
                    critical_errors_json = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    seo_score,
                    aeo_score,
                    overall_score,
                    to_json(crawl),
                    json.dumps(errors),
                    audit_id,
                ),
            )
    except Exception as exc:
        with db_session() as conn:
            conn.execute(
                "UPDATE audits SET status = 'failed', error_message = ?, updated_at = datetime('now') WHERE id = ?",
                (str(exc), audit_id),
            )


async def _execute_optimization_job(optimization_id: int, audit_id: int, user_id: int) -> None:
    try:
        with db_session() as conn:
            conn.execute(
                "UPDATE optimizations SET status = 'running' WHERE id = ?",
                (optimization_id,),
            )
            audit_row = conn.execute(
                "SELECT crawl_result_json FROM audits WHERE id = ? AND user_id = ?",
                (audit_id, user_id),
            ).fetchone()
            brief_row = conn.execute(
                "SELECT * FROM client_briefs WHERE user_id = ?",
                (user_id,),
            ).fetchone()

        crawl = CrawlResult(**json.loads(audit_row["crawl_result_json"]))
        if brief_row:
            brief = ClientBriefPayload(
                target_keywords=json.loads(brief_row["target_keywords_json"]),
                icp=brief_row["icp"],
                tone=brief_row["tone"],
                conversion_goals=brief_row["conversion_goals"],
            )
        else:
            brief = ClientBriefPayload()

        onpage, offpage, _runtime_mode = await run_onpage_and_offpage_crews(crawl, brief)

        with db_session() as conn:
            conn.execute(
                """
                UPDATE optimizations
                SET status = 'completed',
                    onpage_output_json = ?,
                    offpage_output_json = ?,
                    completed_at = datetime('now')
                WHERE id = ?
                """,
                (to_json(onpage), to_json(offpage), optimization_id),
            )
    except Exception as exc:
        with db_session() as conn:
            conn.execute(
                "UPDATE optimizations SET status = 'failed', error_message = ? WHERE id = ?",
                (str(exc), optimization_id),
            )


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_audit(
    payload: AuditCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    url_str = str(payload.url)
    with db_session() as conn:
        cur = conn.execute(
            "INSERT INTO audits (user_id, url, status) VALUES (?, ?, 'queued')",
            (current_user["id"], url_str),
        )
        audit_id = cur.lastrowid

    background_tasks.add_task(_execute_audit_job, audit_id, url_str)
    return {
        "audit_id": audit_id,
        "url": url_str,
        "status": "queued",
        "message": "Single-URL audit queued for background execution.",
    }


@router.get("")
def list_audits(current_user: dict = Depends(get_current_user)):
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT id, url, status, seo_score, aeo_score, overall_score, created_at, updated_at
            FROM audits
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (current_user["id"],),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{audit_id}")
def get_audit(audit_id: int, current_user: dict = Depends(get_current_user)):
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM audits WHERE id = ? AND user_id = ?",
            (audit_id, current_user["id"]),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Audit not found")
        opt_rows = conn.execute(
            "SELECT * FROM optimizations WHERE audit_id = ? AND user_id = ? ORDER BY id DESC",
            (audit_id, current_user["id"]),
        ).fetchall()

    optimizations = []
    for o in opt_rows:
        optimizations.append(
            {
                "id": o["id"],
                "status": o["status"],
                "onpage_output": json.loads(o["onpage_output_json"] or "{}"),
                "offpage_output": json.loads(o["offpage_output_json"] or "{}"),
                "error_message": o["error_message"],
                "created_at": o["created_at"],
                "completed_at": o["completed_at"],
            }
        )

    return {
        "id": row["id"],
        "url": row["url"],
        "status": row["status"],
        "seo_score": row["seo_score"],
        "aeo_score": row["aeo_score"],
        "overall_score": row["overall_score"],
        "crawl_result": json.loads(row["crawl_result_json"] or "{}"),
        "critical_errors": json.loads(row["critical_errors_json"] or "[]"),
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "optimizations": optimizations,
    }


@router.post("/{audit_id}/optimize", status_code=status.HTTP_202_ACCEPTED)
def trigger_optimization(
    audit_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    with db_session() as conn:
        audit = conn.execute(
            "SELECT id, status FROM audits WHERE id = ? AND user_id = ?",
            (audit_id, current_user["id"]),
        ).fetchone()
        if not audit:
            raise HTTPException(status_code=404, detail="Audit not found")
        if audit["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Audit must be completed before optimization (current status: {audit['status']})",
            )
        cur = conn.execute(
            "INSERT INTO optimizations (audit_id, user_id, status) VALUES (?, ?, 'queued')",
            (audit_id, current_user["id"]),
        )
        opt_id = cur.lastrowid

    background_tasks.add_task(_execute_optimization_job, opt_id, audit_id, current_user["id"])
    return {
        "optimization_id": opt_id,
        "audit_id": audit_id,
        "status": "queued",
        "message": "On-demand optimization triggered from persisted CrawlResult snapshot.",
    }
