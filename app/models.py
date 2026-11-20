from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl


class UserRegister(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2)
    gstin: str = ""


class UserLogin(BaseModel):
    email: str
    password: str


class OnboardingChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ClientBriefPayload(BaseModel):
    target_keywords: List[str] = Field(default_factory=list)
    icp: str = ""
    tone: str = "authoritative and clear"
    conversion_goals: str = ""


class AuditCreateRequest(BaseModel):
    url: HttpUrl


class CrawlResult(BaseModel):
    url: str
    reachable: bool
    status_code: int = 0
    title: str = ""
    meta_description: str = ""
    h1_tags: List[str] = Field(default_factory=list)
    h2_tags: List[str] = Field(default_factory=list)
    word_count: int = 0
    has_json_ld: bool = False
    schema_types: List[str] = Field(default_factory=list)
    canonical_url: str = ""
    images_total: int = 0
    images_missing_alt: int = 0
    internal_links: int = 0
    external_links: int = 0
    faq_signals: int = 0
    load_time_ms: int = 0


class OnPageOptimizationOutput(BaseModel):
    optimized_title: str
    optimized_meta_description: str
    keyword_intent_alignment: str
    aeo_direct_answer_block: str
    recommended_json_ld: Dict[str, Any]
    cwv_and_technical_actions: List[str]


class OffPageOptimizationOutput(BaseModel):
    backlink_gap_summary: str
    target_referring_domains: List[str]
    competitor_profiles: List[Dict[str, str]]
    digital_pr_pitch_draft: str
    outreach_sequence: List[str]


class MonitorCreateRequest(BaseModel):
    url: HttpUrl
    monitor_type: str = Field(..., pattern="^(backlink|content_decay|serp_feature)$")


class SMOCampaignRequest(BaseModel):
    source_url: HttpUrl
    audit_id: Optional[int] = None
    topic: str = ""
    platforms: List[str] = Field(
        default_factory=lambda: ["linkedin", "instagram", "facebook", "youtube", "reddit", "quora"]
    )


class SMOPlatformAsset(BaseModel):
    platform: str
    format: str
    hook: str
    body: str
    hashtags: List[str] = Field(default_factory=list)
    optimal_slot_ist: str


class CommunityEngagementItem(BaseModel):
    platform: str
    thread_angle: str
    draft_response: str
    backlink_anchor_suggestion: str
    compliance_note: str


class SMOCampaignOutput(BaseModel):
    platform_assets: List[SMOPlatformAsset]
    community_engagements: List[CommunityEngagementItem]
    draftpilot_queue: List[Dict[str, str]]


class SubscriptionRequest(BaseModel):
    tier: str = Field(..., pattern="^(starter|growth|agency_partner)$")
    gstin: str = ""
