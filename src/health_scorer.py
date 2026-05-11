"""Company health score calculation and generation."""
import os
import logging
from typing import List, Optional
from dataclasses import dataclass

from src.models import FinancialMetrics, RedFlag, CompanyHealthScore
from src.extraction import create_openai_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ScoreComponents:
    """Raw score components before weighting."""
    profitability: float
    growth: float
    debt_safety: float
    risk: float


def calculate_profitability_score(metrics: FinancialMetrics) -> float:
    """Calculate 0-100 profitability score based on margins and ROE."""
    score = 50.0  # Base score
    
    # Operating margin contribution (0-30 points)
    if metrics.operating_margin_pct is not None:
        if metrics.operating_margin_pct > 25:
            score += 30
        elif metrics.operating_margin_pct > 15:
            score += 20
        elif metrics.operating_margin_pct > 10:
            score += 10
        elif metrics.operating_margin_pct > 5:
            score += 5
    
    # ROE contribution (0-20 points)
    if metrics.roe is not None:
        if metrics.roe > 20:
            score += 20
        elif metrics.roe > 15:
            score += 15
        elif metrics.roe > 10:
            score += 10
        elif metrics.roe > 5:
            score += 5
    
    return min(100, max(0, score))


def calculate_growth_score(metrics: FinancialMetrics) -> float:
    """Calculate 0-100 growth score based on YoY revenue growth."""
    score = 50.0  # Base score
    
    if metrics.yoy_revenue_growth_pct is not None:
        growth = metrics.yoy_revenue_growth_pct
        if growth > 50:
            score = 100
        elif growth > 30:
            score = 90
        elif growth > 20:
            score = 80
        elif growth > 15:
            score = 70
        elif growth > 10:
            score = 60
        elif growth > 5:
            score = 55
        elif growth > 0:
            score = 50
        else:
            score = max(0, 50 + growth * 2)  # Penalty for negative growth
    
    return min(100, max(0, score))


def calculate_debt_safety_score(metrics: FinancialMetrics) -> float:
    """Calculate 0-100 debt safety score (inverse of debt-to-equity)."""
    score = 70.0  # Base assumption: moderate safety
    
    if metrics.debt_to_equity is not None:
        dte = metrics.debt_to_equity
        if dte < 0.5:
            score = 100
        elif dte < 1.0:
            score = 85
        elif dte < 1.5:
            score = 70
        elif dte < 2.0:
            score = 55
        elif dte < 3.0:
            score = 40
        else:
            score = 25
    
    return min(100, max(0, score))


def calculate_risk_score(redflags: List[RedFlag]) -> float:
    """Calculate 0-100 risk score (inverse of danger, higher = safer)."""
    if not redflags:
        return 90.0  # No red flags = very safe
    
    # Count by severity
    high_count = sum(1 for f in redflags if f.severity == "high")
    medium_count = sum(1 for f in redflags if f.severity == "medium")
    low_count = sum(1 for f in redflags if f.severity == "low")
    
    # Penalty calculation
    penalty = high_count * 25 + medium_count * 10 + low_count * 3
    score = 100 - penalty
    
    return min(100, max(0, score))


def get_color_code(overall_score: float) -> str:
    """Get traffic light color based on score."""
    if overall_score >= 70:
        return "green"
    elif overall_score >= 50:
        return "amber"
    else:
        return "red"


def get_verdict(overall_score: float, risk_score: float) -> str:
    """Generate investment verdict based on scores."""
    if overall_score >= 80 and risk_score >= 80:
        return "Strong Buy"
    elif overall_score >= 70 and risk_score >= 70:
        return "Buy"
    elif overall_score >= 50 and risk_score >= 50:
        return "Hold"
    elif overall_score >= 35:
        return "Caution"
    else:
        return "Avoid"


def generate_one_line_reason(
    metrics: FinancialMetrics,
    components: ScoreComponents,
    verdict: str
) -> str:
    """Use LLM to generate a one-line investment rationale."""
    client = create_openai_client()
    
    # Determine model based on API key
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = "openai/gpt-4o-mini" if api_key.startswith("sk-or-v1-") else "gpt-4o-mini"
    
    prompt = f"""Generate a one-line investment rationale for {metrics.company}.

Financial Metrics:
- Revenue: {metrics.revenue_crore} crore
- Net Profit: {metrics.net_profit_crore} crore
- YoY Growth: {metrics.yoy_revenue_growth_pct}%
- Operating Margin: {metrics.operating_margin_pct}%
- ROE: {metrics.roe}%
- Debt/Equity: {metrics.debt_to_equity}

Health Scores:
- Profitability: {components.profitability:.0f}/100
- Growth: {components.growth:.0f}/100
- Debt Safety: {components.debt_safety:.0f}/100
- Risk: {components.risk:.0f}/100

Verdict: {verdict}

Write ONE compelling sentence (max 15 words) explaining why an investor should {verdict.lower()} this stock. Be specific about the key strength or weakness."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise financial analyst. Write punchy, specific one-liners."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=50
        )
        reason = response.choices[0].message.content.strip()
        # Clean up - remove quotes if present
        reason = reason.strip('"').strip("'")
        return reason
    except Exception as e:
        logger.error(f"Error generating one-line reason: {e}")
        return f"{verdict} based on financial health analysis."


def calculate_health_score(
    metrics: FinancialMetrics,
    redflags: List[RedFlag]
) -> CompanyHealthScore:
    """Calculate comprehensive health score for a company."""
    
    # Calculate component scores
    components = ScoreComponents(
        profitability=calculate_profitability_score(metrics),
        growth=calculate_growth_score(metrics),
        debt_safety=calculate_debt_safety_score(metrics),
        risk=calculate_risk_score(redflags)
    )
    
    # Weighted overall score
    overall = (
        components.profitability * 0.35 +
        components.growth * 0.30 +
        components.debt_safety * 0.20 +
        components.risk * 0.15
    )
    
    # Get verdict and color
    verdict = get_verdict(overall, components.risk)
    color = get_color_code(overall)
    
    # Generate one-line reason using LLM
    reason = generate_one_line_reason(metrics, components, verdict)
    
    return CompanyHealthScore(
        company=metrics.company,
        overall_score=round(overall, 1),
        profitability_score=round(components.profitability, 1),
        growth_score=round(components.growth, 1),
        debt_safety_score=round(components.debt_safety, 1),
        risk_score=round(components.risk, 1),
        verdict=verdict,
        one_line_reason=reason,
        color_code=color
    )


def get_all_health_scores(
    metrics_list: List[FinancialMetrics],
    redflags_dict: dict
) -> List[CompanyHealthScore]:
    """Calculate health scores for all companies."""
    scores = []
    
    for metrics in metrics_list:
        company = metrics.company
        redflags = redflags_dict.get(company, [])
        
        try:
            score = calculate_health_score(metrics, redflags)
            scores.append(score)
            logger.info(f"Calculated health score for {company}: {score.overall_score}")
        except Exception as e:
            logger.error(f"Error calculating health score for {company}: {e}")
    
    # Sort by overall score descending
    scores.sort(key=lambda x: x.overall_score, reverse=True)
    return scores
