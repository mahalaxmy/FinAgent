"""Simple JSON cache for extracted metrics, red flags, and health scores.

This avoids re-extracting data and wasting API tokens on subsequent runs.
"""
import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.models import FinancialMetrics, RedFlag, CompanyHealthScore


CACHE_DIR = Path("./cache")
METRICS_FILE = CACHE_DIR / "metrics_cache.json"
REDFLAGS_FILE = CACHE_DIR / "redflags_cache.json"
HEALTH_SCORES_FILE = CACHE_DIR / "health_scores_cache.json"


def _ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _metrics_to_dict(metrics: FinancialMetrics) -> dict:
    """Convert FinancialMetrics to dict."""
    return {
        "company": metrics.company,
        "fiscal_year": metrics.fiscal_year,
        "revenue_crore": metrics.revenue_crore,
        "net_profit_crore": metrics.net_profit_crore,
        "eps": metrics.eps,
        "debt_to_equity": metrics.debt_to_equity,
        "yoy_revenue_growth_pct": metrics.yoy_revenue_growth_pct,
        "operating_margin_pct": metrics.operating_margin_pct,
        "roe": metrics.roe,
        "cached_at": datetime.now().isoformat()
    }


def _dict_to_metrics(data: dict) -> FinancialMetrics:
    """Convert dict to FinancialMetrics."""
    return FinancialMetrics(
        company=data["company"],
        fiscal_year=data.get("fiscal_year", "2024"),
        revenue_crore=data.get("revenue_crore"),
        net_profit_crore=data.get("net_profit_crore"),
        eps=data.get("eps"),
        debt_to_equity=data.get("debt_to_equity"),
        yoy_revenue_growth_pct=data.get("yoy_revenue_growth_pct"),
        operating_margin_pct=data.get("operating_margin_pct"),
        roe=data.get("roe")
    )


def _redflag_to_dict(rf: RedFlag) -> dict:
    """Convert RedFlag to dict."""
    return {
        "company": rf.company,
        "keyword": rf.keyword,
        "sentence": rf.sentence,
        "page_number": rf.page_number,
        "severity": rf.severity,
        "context": rf.context,
        "cached_at": datetime.now().isoformat()
    }


def _dict_to_redflag(data: dict) -> RedFlag:
    """Convert dict to RedFlag."""
    return RedFlag(
        company=data["company"],
        keyword=data["keyword"],
        sentence=data["sentence"],
        page_number=data.get("page_number"),
        severity=data["severity"],
        context=data.get("context", "")
    )


def _health_score_to_dict(hs: CompanyHealthScore) -> dict:
    """Convert CompanyHealthScore to dict."""
    return {
        "company": hs.company,
        "overall_score": hs.overall_score,
        "profitability_score": hs.profitability_score,
        "growth_score": hs.growth_score,
        "debt_safety_score": hs.debt_safety_score,
        "risk_score": hs.risk_score,
        "verdict": hs.verdict,
        "one_line_reason": hs.one_line_reason,
        "color_code": hs.color_code,
        "cached_at": datetime.now().isoformat()
    }


def _dict_to_health_score(data: dict) -> CompanyHealthScore:
    """Convert dict to CompanyHealthScore."""
    return CompanyHealthScore(
        company=data["company"],
        overall_score=data["overall_score"],
        profitability_score=data["profitability_score"],
        growth_score=data["growth_score"],
        debt_safety_score=data["debt_safety_score"],
        risk_score=data["risk_score"],
        verdict=data["verdict"],
        one_line_reason=data["one_line_reason"],
        color_code=data["color_code"]
    )


def save_metrics_cache(metrics: List[FinancialMetrics]):
    """Save metrics to cache file."""
    _ensure_cache_dir()
    data = [_metrics_to_dict(m) for m in metrics]
    with open(METRICS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_metrics_cache() -> Optional[List[FinancialMetrics]]:
    """Load metrics from cache if exists."""
    if not METRICS_FILE.exists():
        return None
    try:
        with open(METRICS_FILE, "r") as f:
            data = json.load(f)
        return [_dict_to_dict(d) for d in data]
    except Exception:
        return None


def save_redflags_cache(redflags: List[RedFlag]):
    """Save red flags to cache file."""
    _ensure_cache_dir()
    data = [_redflag_to_dict(rf) for rf in redflags]
    with open(REDFLAGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_redflags_cache() -> Optional[List[RedFlag]]:
    """Load red flags from cache if exists."""
    if not REDFLAGS_FILE.exists():
        return None
    try:
        with open(REDFLAGS_FILE, "r") as f:
            data = json.load(f)
        return [_dict_to_redflag(d) for d in data]
    except Exception:
        return None


def save_health_scores_cache(scores: List[CompanyHealthScore]):
    """Save health scores to cache file."""
    _ensure_cache_dir()
    data = [_health_score_to_dict(hs) for hs in scores]
    with open(HEALTH_SCORES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_health_scores_cache() -> Optional[List[CompanyHealthScore]]:
    """Load health scores from cache if exists."""
    if not HEALTH_SCORES_FILE.exists():
        return None
    try:
        with open(HEALTH_SCORES_FILE, "r") as f:
            data = json.load(f)
        return [_dict_to_health_score(d) for d in data]
    except Exception:
        return None


def clear_all_cache():
    """Clear all cached data."""
    for f in [METRICS_FILE, REDFLAGS_FILE, HEALTH_SCORES_FILE]:
        if f.exists():
            f.unlink()


def get_cache_info() -> Dict[str, Any]:
    """Get information about cached data."""
    info = {}
    for name, file_path in [
        ("metrics", METRICS_FILE),
        ("redflags", REDFLAGS_FILE),
        ("health_scores", HEALTH_SCORES_FILE)
    ]:
        if file_path.exists():
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                info[name] = {
                    "count": len(data),
                    "cached_at": data[0].get("cached_at", "unknown") if data else None
                }
            except Exception:
                info[name] = {"count": 0, "error": True}
        else:
            info[name] = {"count": 0, "cached_at": None}
    return info
