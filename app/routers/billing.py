import json
from fastapi import APIRouter, Depends
from ..auth import get_current_user
from ..config import GST_RATE
from ..database import db_session
from ..models import SubscriptionRequest

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

PLANS = {
    "starter": {
        "tier": "starter",
        "name": "Starter",
        "base_inr": 4999,
        "outcome_cap_inr": 2500,
        "features": [
            "Up to 15 single-URL audits/mo",
            "On-Page & JSON-LD AEO Crew",
            "Monthly ROI Digest",
        ],
    },
    "growth": {
        "tier": "growth",
        "name": "Growth",
        "base_inr": 12999,
        "outcome_cap_inr": 7500,
        "features": [
            "Up to 60 single-URL audits/mo",
            "On-Page + Off-Page Digital PR Crew",
            "Backlink, Content Decay & SERP Monitors",
            "SMO + DraftPilot (LinkedIn, IG, FB, YT, Reddit, Quora)",
        ],
    },
    "agency_partner": {
        "tier": "agency_partner",
        "name": "Agency Partner",
        "base_inr": 29999,
        "outcome_cap_inr": 15000,
        "features": [
            "Unlimited single-URL audits",
            "Full Multi-Crew Orchestration + Priority Queue",
            "White-Label Monthly ROI Reports",
            "Dedicated Community & Link-Building Workflows",
        ],
    },
}


@router.get("/plans")
def get_plans():
    result = []
    for key, plan in PLANS.items():
        gst_inr = round(plan["base_inr"] * GST_RATE)
        result.append(
            {
                **plan,
                "gst_rate_pct": 18,
                "gst_inr": gst_inr,
                "total_inr": plan["base_inr"] + gst_inr,
                "outcome_rule": f"Capped outcome bonus up to ₹{plan['outcome_cap_inr']:,}/mo on verified rank or AI Overview citation milestones.",
            }
        )
    return result


@router.post("/subscribe")
def subscribe_plan(payload: SubscriptionRequest, current_user: dict = Depends(get_current_user)):
    plan = PLANS[payload.tier]
    base_inr = plan["base_inr"]
    gst_inr = round(base_inr * GST_RATE)
    total_inr = base_inr + gst_inr
    milestones = [
        {"milestone": "Top-3 SERP or AI Overview Citation", "bonus_inr": round(plan["outcome_cap_inr"] * 0.5), "achieved": False},
        {"milestone": "+25% Organic / Community Referral Traffic", "bonus_inr": round(plan["outcome_cap_inr"] * 0.5), "achieved": False},
    ]
    with db_session() as conn:
        conn.execute(
            "UPDATE users SET plan_tier = ?, gstin = ? WHERE id = ?",
            (payload.tier, payload.gstin.strip(), current_user["id"]),
        )
        conn.execute(
            """
            INSERT INTO subscriptions (user_id, tier, base_inr, gst_inr, total_inr, outcome_cap_inr, milestones_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                current_user["id"],
                payload.tier,
                base_inr,
                gst_inr,
                total_inr,
                plan["outcome_cap_inr"],
                json.dumps(milestones),
            ),
        )
    return {
        "tier": payload.tier,
        "base_inr": base_inr,
        "gst_inr": gst_inr,
        "total_inr": total_inr,
        "outcome_cap_inr": plan["outcome_cap_inr"],
        "milestones": milestones,
    }


@router.get("/roi-report")
def monthly_roi_report(current_user: dict = Depends(get_current_user)):
    with db_session() as conn:
        audit_count = conn.execute(
            "SELECT COUNT(*) AS c, COALESCE(AVG(overall_score), 0) AS avg_score FROM audits WHERE user_id = ?",
            (current_user["id"],),
        ).fetchone()
        opt_count = conn.execute(
            "SELECT COUNT(*) AS c FROM optimizations WHERE user_id = ? AND status = 'completed'",
            (current_user["id"],),
        ).fetchone()
        mon_count = conn.execute(
            "SELECT COUNT(*) AS c FROM monitors WHERE user_id = ?",
            (current_user["id"],),
        ).fetchone()
        smo_count = conn.execute(
            "SELECT COUNT(*) AS c FROM smo_campaigns WHERE user_id = ? AND status = 'completed'",
            (current_user["id"],),
        ).fetchone()

    plan = PLANS.get(current_user["plan_tier"], PLANS["starter"])
    gst_inr = round(plan["base_inr"] * GST_RATE)
    return {
        "client_name": current_user["full_name"],
        "plan_tier": plan["name"],
        "monthly_retainer_inr": plan["base_inr"],
        "gst_inr": gst_inr,
        "total_billed_inr": plan["base_inr"] + gst_inr,
        "outcome_cap_inr": plan["outcome_cap_inr"],
        "metrics": {
            "audits_completed": audit_count["c"],
            "average_health_score": round(audit_count["avg_score"], 1),
            "on_demand_optimizations": opt_count["c"],
            "active_monitors": mon_count["c"],
            "smo_campaigns_completed": smo_count["c"],
        },
    }
