"""Pydantic models for structured financial data extraction."""
from typing import Optional, Literal, List
from pydantic import BaseModel, Field


class CompanyHealthScore(BaseModel):
    """Health score for a company based on financial metrics and risk factors."""
    
    company: str = Field(description="Company name")
    overall_score: float = Field(ge=0, le=100, description="Overall health score 0-100")
    profitability_score: float = Field(ge=0, le=100, description="Profitability score (weight: 35%)")
    growth_score: float = Field(ge=0, le=100, description="Growth score (weight: 30%)")
    debt_safety_score: float = Field(ge=0, le=100, description="Debt safety score (weight: 20%)")
    risk_score: float = Field(ge=0, le=100, description="Risk score (weight: 15%, inverted red flags)")
    verdict: Literal["Strong Buy", "Buy", "Hold", "Caution", "Avoid"] = Field(description="Investment verdict")
    one_line_reason: str = Field(description="One-line investment rationale")
    color_code: Literal["green", "amber", "red"] = Field(description="Traffic light color for overall score")


class ReasonedResponse(BaseModel):
    """Response with reasoning transparency for explainability."""
    
    answer: str = Field(description="The final answer to the user's question")
    companies_queried: List[str] = Field(description="List of company indexes that were queried")
    chunks_retrieved: int = Field(description="Number of document chunks retrieved")
    confidence: Literal["high", "medium", "low"] = Field(description="Confidence level of the response")
    what_was_missing: Optional[str] = Field(None, description="Information that couldn't be found")
    reasoning_steps: List[str] = Field(description="Step-by-step reasoning process")
    sources: List[dict] = Field(default_factory=list, description="Source citations with page numbers")


class FinancialMetrics(BaseModel):
    """Key financial metrics extracted from annual reports."""
    
    company: str = Field(description="Company name")
    fiscal_year: str = Field(description="Fiscal year of the report")
    revenue_crore: Optional[float] = Field(None, description="Total revenue in crore INR")
    net_profit_crore: Optional[float] = Field(None, description="Net profit in crore INR")
    eps: Optional[float] = Field(None, description="Earnings per share")
    debt_to_equity: Optional[float] = Field(None, description="Debt to equity ratio")
    yoy_revenue_growth_pct: Optional[float] = Field(None, description="Year-over-year revenue growth percentage")
    operating_margin_pct: Optional[float] = Field(None, description="Operating margin percentage")
    roe: Optional[float] = Field(None, description="Return on equity percentage")
    
    
class RedFlag(BaseModel):
    """Risk indicators found in annual reports."""
    
    company: str = Field(description="Company name where flag was found")
    keyword: str = Field(description="Risk keyword detected")
    sentence: str = Field(description="Full sentence containing the risk language")
    page_number: Optional[int] = Field(None, description="Page number where found")
    severity: Literal["low", "medium", "high"] = Field(description="Severity assessment")
    context: str = Field(description="Additional surrounding context")
    

class CompanySummary(BaseModel):
    """Summary of a company's annual report."""
    
    company: str = Field(description="Company name")
    fiscal_year: str = Field(description="Fiscal year")
    key_highlights: List[str] = Field(description="Key business highlights")
    risk_factors: List[str] = Field(description="Major risk factors mentioned")
    business_segments: List[str] = Field(description="Primary business segments")
