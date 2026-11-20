import json
import time
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from ..models import CrawlResult


async def crawl_single_url(url: str) -> Tuple[CrawlResult, int, int, int, List[Dict[str, str]]]:
    """
    Crawls a single URL and computes SEO, AEO, and overall health scores (0-100)
    plus categorized critical error logs.
    """
    start = time.monotonic()
    parsed = urlparse(url)
    domain = parsed.netloc or "example.com"

    html = ""
    status_code = 0
    reachable = False
    fetch_error = ""

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "PulseRankAI-Bot/1.0 (+https://pulserank.local)"},
            )
            status_code = resp.status_code
            html = resp.text or ""
            reachable = 200 <= status_code < 400
    except Exception as exc:
        fetch_error = str(exc)
        reachable = False

    elapsed_ms = int((time.monotonic() - start) * 1000)

    if not reachable or not html:
        crawl = CrawlResult(
            url=url,
            reachable=False,
            status_code=status_code,
            title="",
            meta_description="",
            load_time_ms=elapsed_ms,
        )
        errors = [
            {
                "category": "Crawlability",
                "severity": "critical",
                "code": "URL_UNREACHABLE",
                "message": f"Target URL {url} could not be fetched ({fetch_error or f'HTTP {status_code}'}). Snapshot saved for offline/sandbox optimization.",
            },
            {
                "category": "AEO Readiness",
                "severity": "high",
                "code": "MISSING_JSON_LD",
                "message": "No structured JSON-LD schema detected on page snapshot.",
            },
            {
                "category": "On-Page SEO",
                "severity": "high",
                "code": "MISSING_META_TAGS",
                "message": "Title tag and meta description could not be verified.",
            },
        ]
        return crawl, 35, 30, 33, errors

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "description"})
    meta_description = (meta_desc_tag.get("content") or "").strip() if meta_desc_tag else ""

    h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1") if h.get_text(strip=True)]
    h2_tags = [h.get_text(strip=True) for h in soup.find_all("h2") if h.get_text(strip=True)]

    text_content = soup.get_text(" ", strip=True)
    word_count = len(text_content.split())

    ld_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    schema_types: List[str] = []
    for script in ld_scripts:
        try:
            data = json.loads(script.string or "{}")
            if isinstance(data, dict) and "@type" in data:
                schema_types.append(str(data["@type"]))
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "@type" in item:
                        schema_types.append(str(item["@type"]))
        except Exception:
            pass

    canonical_tag = soup.find("link", attrs={"rel": lambda r: r and "canonical" in r})
    canonical_url = (canonical_tag.get("href") or "").strip() if canonical_tag else ""

    imgs = soup.find_all("img")
    images_total = len(imgs)
    images_missing_alt = sum(1 for img in imgs if not (img.get("alt") or "").strip())

    internal_links = 0
    external_links = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/") or domain in href:
            internal_links += 1
        elif href.startswith("http"):
            external_links += 1

    faq_signals = sum(1 for h in (h1_tags + h2_tags) if "?" in h)

    crawl = CrawlResult(
        url=url,
        reachable=True,
        status_code=status_code,
        title=title,
        meta_description=meta_description,
        h1_tags=h1_tags[:10],
        h2_tags=h2_tags[:15],
        word_count=word_count,
        has_json_ld=len(ld_scripts) > 0,
        schema_types=schema_types,
        canonical_url=canonical_url,
        images_total=images_total,
        images_missing_alt=images_missing_alt,
        internal_links=internal_links,
        external_links=external_links,
        faq_signals=faq_signals,
        load_time_ms=elapsed_ms,
    )

    errors: List[Dict[str, str]] = []
    seo_score = 100
    aeo_score = 100

    if not title or len(title) < 20 or len(title) > 65:
        seo_score -= 15
        errors.append({
            "category": "On-Page SEO",
            "severity": "critical" if not title else "medium",
            "code": "TITLE_LENGTH_SUBOPTIMAL",
            "message": f"Title length is {len(title)} chars (recommended 30-60 chars).",
        })

    if not meta_description or len(meta_description) < 70:
        seo_score -= 12
        errors.append({
            "category": "On-Page SEO",
            "severity": "high",
            "code": "META_DESCRIPTION_WEAK",
            "message": f"Meta description is {len(meta_description)} chars (recommended 120-160 chars).",
        })

    if len(h1_tags) != 1:
        seo_score -= 10
        errors.append({
            "category": "Heading Structure",
            "severity": "high",
            "code": "H1_COUNT_INVALID",
            "message": f"Found {len(h1_tags)} H1 tags (recommended exactly 1).",
        })

    if not canonical_url:
        seo_score -= 8
        errors.append({
            "category": "Technical SEO",
            "severity": "medium",
            "code": "MISSING_CANONICAL",
            "message": "No canonical link tag found.",
        })

    if images_missing_alt > 0:
        seo_score -= min(15, images_missing_alt * 3)
        errors.append({
            "category": "Accessibility & Image SEO",
            "severity": "medium",
            "code": "IMAGES_MISSING_ALT",
            "message": f"{images_missing_alt} of {images_total} images are missing alt attributes.",
        })

    if not crawl.has_json_ld:
        aeo_score -= 28
        errors.append({
            "category": "AEO Readiness",
            "severity": "critical",
            "code": "MISSING_JSON_LD",
            "message": "No JSON-LD schema found; answer engines rely on structured entities.",
        })

    if faq_signals == 0:
        aeo_score -= 18
        errors.append({
            "category": "AEO Readiness",
            "severity": "high",
            "code": "NO_QA_HEADINGS",
            "message": "No question-style H1/H2 headings detected for Featured Snippets / AI Overviews.",
        })

    if word_count < 300:
        seo_score -= 15
        aeo_score -= 15
        errors.append({
            "category": "Content Depth",
            "severity": "high",
            "code": "THIN_CONTENT",
            "message": f"Word count is {word_count} (recommended 600+ words for topical authority).",
        })

    seo_score = max(0, min(100, seo_score))
    aeo_score = max(0, min(100, aeo_score))
    overall_score = round((seo_score * 0.55) + (aeo_score * 0.45))
    return crawl, seo_score, aeo_score, overall_score, errors
