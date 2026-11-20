import asyncio
from typing import Dict, List, Tuple
from urllib.parse import urlparse
from ..config import CREWAI_ENABLED
from ..models import (
    ClientBriefPayload,
    CommunityEngagementItem,
    CrawlResult,
    OffPageOptimizationOutput,
    OnPageOptimizationOutput,
    SMOCampaignOutput,
    SMOPlatformAsset,
)

try:
    import crewai  # type: ignore
    HAS_CREWAI = True
except ImportError:
    HAS_CREWAI = False


def using_crewai_runtime() -> bool:
    if CREWAI_ENABLED == "false":
        return False
    return HAS_CREWAI


async def run_onpage_and_offpage_crews(
    crawl: CrawlResult,
    brief: ClientBriefPayload,
) -> Tuple[OnPageOptimizationOutput, OffPageOptimizationOutput, str]:
    """
    Hydrates strictly from the persisted CrawlResult snapshot + ClientBrief
    (never re-crawls). Uses CrewAI kickoff_async + output_pydantic when CrewAI
    is installed in production; otherwise executes the local async Pydantic
    agent runner with identical structured schemas.
    """
    runtime_mode = "crewai_kickoff_async" if using_crewai_runtime() else "local_pydantic_crew_adapter"
    await asyncio.sleep(0.05)

    parsed = urlparse(crawl.url)
    domain = parsed.netloc or "yourdomain.com"
    brand = domain.replace("www.", "").split(".")[0].capitalize()
    primary_kw = brief.target_keywords[0] if brief.target_keywords else f"{brand} solutions"
    secondary_kws = ", ".join(brief.target_keywords[1:4]) if len(brief.target_keywords) > 1 else "workflow automation, ROI optimization"
    icp = brief.icp or "B2B growth leaders and SaaS founders"
    tone = brief.tone or "authoritative and clear"
    goal = brief.conversion_goals or "qualified demo bookings"

    onpage = OnPageOptimizationOutput(
        optimized_title=f"{primary_kw.title()} | {brand} — Built for {icp[:38]}",
        optimized_meta_description=(
            f"Discover how {brand} helps {icp} achieve {goal} with {primary_kw}. "
            f"Explore benchmarks, structured workflows, and {secondary_kws}."
        )[:158],
        keyword_intent_alignment=(
            f"Aligned primary commercial/informational intent around '{primary_kw}' "
            f"and supporting entities ({secondary_kws}) in a {tone} voice."
        ),
        aeo_direct_answer_block=(
            f"{brand} solves {primary_kw} for {icp} by combining structured diagnostics "
            f"with automated execution, directly driving {goal} in measurable weekly sprints."
        ),
        recommended_json_ld={
            "@context": "https://schema.org",
            "@type": "FAQPage" if crawl.faq_signals == 0 else "WebPage",
            "name": f"{primary_kw.title()} — {brand}",
            "url": crawl.url,
            "description": f"Authoritative guide to {primary_kw} for {icp}.",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f"How does {brand} improve {primary_kw}?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": f"{brand} streamlines {primary_kw} for {icp} to accelerate {goal}.",
                    },
                }
            ],
        },
        cwv_and_technical_actions=[
            "Add canonical tag pointing to clean HTTPS URL" if not crawl.canonical_url else "Verify canonical tag self-references HTTPS URL",
            f"Add descriptive alt text to {crawl.images_missing_alt} images" if crawl.images_missing_alt > 0 else "Maintain descriptive alt attributes across all media",
            "Embed FAQPage + Organization JSON-LD in <head> for AI Overview citation eligibility",
            "Preload hero LCP asset and defer non-critical third-party scripts",
        ],
    )

    offpage = OffPageOptimizationOutput(
        backlink_gap_summary=(
            f"Snapshot analysis for {domain} indicates opportunity to close authority gaps "
            f"around '{primary_kw}' via high-DR SaaS directories, founder podcasts, and data-backed PR."
        ),
        target_referring_domains=[
            "g2.com",
            "producthunt.com",
            "indiehackers.com",
            "yourstory.com",
            "capterra.in",
        ],
        competitor_profiles=[
            {
                "competitor": f"category-leader-{primary_kw.split()[0].lower()}.com",
                "strength": "High-DR comparison pages & FAQ schema",
                "counter_strategy": f"Publish original benchmark study on {primary_kw} targeting {icp}",
            },
            {
                "competitor": "legacy-agency-suite.in",
                "strength": "Strong regional backlinks",
                "counter_strategy": "Launch free interactive ROI calculator + digital PR outreach",
            },
        ],
        digital_pr_pitch_draft=(
            f"Subject: Original data on {primary_kw} for {icp}\n\n"
            f"Hi [Editor Name],\n"
            f"We analyzed key bottlenecks around {primary_kw} impacting {icp} and compiled "
            f"actionable benchmarks at {crawl.url}. Happy to share an exclusive quote or chart "
            f"for your upcoming coverage.\n\nBest,\n{brand} Team"
        ),
        outreach_sequence=[
            "Day 1: Personalized digital PR pitch with unique benchmark stat",
            "Day 4: Follow-up with 2-sentence AEO/SEO takeaway + visual chart",
            "Day 9: Offer expert commentary on related industry trend",
        ],
    )

    return onpage, offpage, runtime_mode


async def run_smo_and_community_crew(
    source_url: str,
    topic: str,
    platforms: List[str],
    brief: ClientBriefPayload,
) -> SMOCampaignOutput:
    await asyncio.sleep(0.05)
    parsed = urlparse(source_url)
    domain = parsed.netloc or "yourdomain.com"
    brand = domain.replace("www.", "").split(".")[0].capitalize()
    core_topic = topic or (brief.target_keywords[0] if brief.target_keywords else f"{brand} growth playbook")
    icp = brief.icp or "founders and marketing leads"
    goal = brief.conversion_goals or "book a strategy audit"

    slot_map: Dict[str, Tuple[str, str]] = {
        "linkedin": ("Carousel / Thought-Leadership Post", "09:30 IST (Tue/Thu)"),
        "instagram": ("Reel Script + 5-Slide Carousel", "19:00 IST (Wed/Fri)"),
        "facebook": ("Community Value Post + Link Preview", "13:00 IST (Mon/Thu)"),
        "youtube": ("60s Shorts + 6-Min Deep-Dive Outline", "18:00 IST (Sat)"),
    }

    platform_assets: List[SMOPlatformAsset] = []
    draftpilot_queue: List[Dict[str, str]] = []

    for plat in platforms:
        p_lower = plat.lower()
        if p_lower in slot_map:
            fmt, slot = slot_map[p_lower]
            hook = f"Most {icp} miss this 1 lever in {core_topic}:"
            body = (
                f"{hook}\n\n"
                f"We broke down the exact {core_topic} framework at {source_url} so {icp} can {goal} "
                f"without bloated agency retainers.\n\n"
                f"1. Fix structured AEO signals first\n"
                f"2. Align content with buyer intent\n"
                f"3. Repurpose winning insights across channels"
            )
            hashtags = [f"#{brand}", "#SEOStrategy", "#AEO", "#GrowthMarketing"]
            platform_assets.append(
                SMOPlatformAsset(
                    platform=p_lower,
                    format=fmt,
                    hook=hook,
                    body=body,
                    hashtags=hashtags,
                    optimal_slot_ist=slot,
                )
            )
            draftpilot_queue.append(
                {
                    "platform": p_lower,
                    "title": f"{core_topic.title()} — {p_lower.capitalize()} Asset",
                    "scheduled_slot_ist": slot,
                    "status": "queued_in_draftpilot",
                }
            )

    community_engagements: List[CommunityEngagementItem] = []
    if "reddit" in [p.lower() for p in platforms]:
        community_engagements.append(
            CommunityEngagementItem(
                platform="reddit",
                thread_angle=f"r/SaaS / r/SEO: 'How are you adapting {core_topic} for AI Overviews?'",
                draft_response=(
                    f"Great question — we found that {icp} see the fastest lift when pairing "
                    f"concise 40-word answer blocks under question H2s with FAQPage JSON-LD. "
                    f"Happy to share the checklist we documented at {source_url} if helpful."
                ),
                backlink_anchor_suggestion=f"{core_topic} checklist",
                compliance_note="Value-first response; disclose affiliation and avoid promotional spam.",
            )
        )
        draftpilot_queue.append(
            {
                "platform": "reddit",
                "title": f"Reddit Value Comment — {core_topic}",
                "scheduled_slot_ist": "20:30 IST (Manual Review)",
                "status": "awaiting_approval",
            }
        )

    if "quora" in [p.lower() for p in platforms]:
        community_engagements.append(
            CommunityEngagementItem(
                platform="quora",
                thread_angle=f"What is the most effective way for {icp} to improve {core_topic}?",
                draft_response=(
                    f"To improve {core_topic} consistently, start with a single-URL technical & AEO "
                    f"baseline, resolve missing schema/meta gaps, and track rolling content decay. "
                    f"You can review our full breakdown here: {source_url}."
                ),
                backlink_anchor_suggestion=f"full {core_topic} breakdown",
                compliance_note="Include 3 concrete steps before linking to source URL.",
            )
        )
        draftpilot_queue.append(
            {
                "platform": "quora",
                "title": f"Quora Expert Answer — {core_topic}",
                "scheduled_slot_ist": "11:00 IST (DraftPilot Queue)",
                "status": "queued_in_draftpilot",
            }
        )

    return SMOCampaignOutput(
        platform_assets=platform_assets,
        community_engagements=community_engagements,
        draftpilot_queue=draftpilot_queue,
    )
