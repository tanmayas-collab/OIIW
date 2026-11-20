import json
from fastapi import APIRouter, Depends
from ..auth import get_current_user
from ..database import db_session
from ..models import ClientBriefPayload, OnboardingChatRequest

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


def _load_or_create_brief(user_id: int) -> dict:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM client_briefs WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            conn.execute("INSERT INTO client_briefs (user_id) VALUES (?)", (user_id,))
            row = conn.execute("SELECT * FROM client_briefs WHERE user_id = ?", (user_id,)).fetchone()
    return {
        "target_keywords": json.loads(row["target_keywords_json"]),
        "icp": row["icp"],
        "tone": row["tone"],
        "conversion_goals": row["conversion_goals"],
        "chat_history": json.loads(row["chat_history_json"]),
        "completed": bool(row["completed"]),
    }


@router.get("/brief")
def get_brief(current_user: dict = Depends(get_current_user)):
    return _load_or_create_brief(current_user["id"])


@router.put("/brief")
def update_brief(payload: ClientBriefPayload, current_user: dict = Depends(get_current_user)):
    _load_or_create_brief(current_user["id"])
    completed = int(bool(payload.target_keywords and payload.icp and payload.conversion_goals))
    with db_session() as conn:
        conn.execute(
            """
            UPDATE client_briefs
            SET target_keywords_json = ?, icp = ?, tone = ?, conversion_goals = ?,
                completed = ?, updated_at = datetime('now')
            WHERE user_id = ?
            """,
            (
                json.dumps(payload.target_keywords),
                payload.icp.strip(),
                payload.tone.strip(),
                payload.conversion_goals.strip(),
                completed,
                current_user["id"],
            ),
        )
    return _load_or_create_brief(current_user["id"])


@router.post("/chat")
def onboarding_chat(payload: OnboardingChatRequest, current_user: dict = Depends(get_current_user)):
    brief = _load_or_create_brief(current_user["id"])
    msg = payload.message.strip()
    history = brief["chat_history"]
    history.append({"role": "user", "content": msg})

    if not brief["target_keywords"]:
        kws = [k.strip() for k in msg.replace(";", ",").split(",") if k.strip()]
        brief["target_keywords"] = kws[:8]
        reply = (
            f"Captured target keywords: {', '.join(brief['target_keywords'])}. "
            "Next, who is your Ideal Customer Profile (ICP) — e.g., Indian SaaS founders, D2C clinics, or B2B procurement teams?"
        )
    elif not brief["icp"]:
        brief["icp"] = msg
        reply = (
            f"Got it — ICP set to '{brief['icp']}'. "
            "What brand tone should our agents use (e.g., authoritative & data-driven, warm & consultative)?"
        )
    elif brief["tone"] == "authoritative and clear" and "goal" not in msg.lower() and not brief["conversion_goals"]:
        # Capture tone on turn 3
        brief["tone"] = msg
        reply = (
            f"Tone saved as '{brief['tone']}'. "
            "Finally, what is your primary conversion goal (e.g., booked demos, free trial signups, WhatsApp inquiries)?"
        )
    elif not brief["conversion_goals"]:
        brief["conversion_goals"] = msg
        reply = (
            "Your ClientBrief is complete and locked in! You can now run any single-URL audit "
            "and trigger on-demand SEO, AEO, Off-Page, and SMO optimization."
        )
    else:
        reply = (
            "Your ClientBrief is already complete. You can update specific fields anytime or "
            "launch an on-demand optimization from your latest audit."
        )

    completed = int(bool(brief["target_keywords"] and brief["icp"] and brief["conversion_goals"]))
    history.append({"role": "assistant", "content": reply})

    with db_session() as conn:
        conn.execute(
            """
            UPDATE client_briefs
            SET target_keywords_json = ?, icp = ?, tone = ?, conversion_goals = ?,
                chat_history_json = ?, completed = ?, updated_at = datetime('now')
            WHERE user_id = ?
            """,
            (
                json.dumps(brief["target_keywords"]),
                brief["icp"],
                brief["tone"],
                brief["conversion_goals"],
                json.dumps(history[-20:]),
                completed,
                current_user["id"],
            ),
        )

    return {
        "reply": reply,
        "completed": bool(completed),
        "brief": {
            "target_keywords": brief["target_keywords"],
            "icp": brief["icp"],
            "tone": brief["tone"],
            "conversion_goals": brief["conversion_goals"],
        },
    }
