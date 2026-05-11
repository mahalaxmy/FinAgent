"""Structured financial metrics extraction using function calling."""
import os
import json
import logging
from typing import Optional, List
from pathlib import Path

from openai import OpenAI
from pydantic import ValidationError

from src.models import FinancialMetrics, CompanySummary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_openai_client():
    """Create OpenAI client, supporting both OpenAI and OpenRouter."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    
    # Detect OpenRouter key (starts with sk-or-v1-)
    if api_key.startswith("sk-or-v1-"):
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
    
    # Standard OpenAI
    return OpenAI(api_key=api_key)


class FinancialExtractor:
    """Extract structured financial data from annual reports."""
    
    def __init__(self):
        self.client = create_openai_client()
        # OpenRouter uses provider/model format, OpenAI uses just model name
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key.startswith("sk-or-v1-"):
            self.model = "openai/gpt-4o-mini"  # OpenRouter format
        else:
            self.model = "gpt-4o-mini"  # OpenAI format
        
    def extract_financial_metrics(self, text: str, company_name: str, fiscal_year: str) -> Optional[FinancialMetrics]:
        """Extract financial metrics from report text using function calling."""
        
        system_prompt = """You are a financial analyst extracting key metrics from annual reports.
        Extract the following metrics if available:
        - Revenue in crore INR
        - Net profit in crore INR  
        - EPS (Earnings Per Share)
        - Debt to equity ratio
        - Year-over-year revenue growth %
        - Operating margin %
        - Return on equity (ROE) %
        
        Only provide values you can verify from the text. Use null if not found.
        Be precise - verify numbers appear in the financial statements section."""

        user_prompt = f"""Company: {company_name}
Fiscal Year: {fiscal_year}

Extract financial metrics from this annual report text:

{text[:15000]}  # Limit context to manage token usage

Extract all available metrics. Return as structured data."""

        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=FinancialMetrics,
                temperature=0.1
            )
            
            metrics = response.choices[0].message.parsed
            metrics.company = company_name
            metrics.fiscal_year = fiscal_year
            
            logger.info(f"Extracted metrics for {company_name}: revenue={metrics.revenue_crore}")
            return metrics
            
        except Exception as e:
            logger.error(f"Error extracting metrics for {company_name}: {e}")
            return None
    
    def extract_from_index(self, query_engine, company_name: str, fiscal_year: str = "2024") -> Optional[FinancialMetrics]:
        """Extract metrics by querying the index for financial data."""
        
        # Query for key financial data sections
        queries = [
            "What is the total revenue and net profit for the year?",
            "What is the EPS earnings per share?",
            "What is the debt equity ratio?",
            "What is the year over year revenue growth percentage?",
            "What is the operating margin and return on equity ROE?"
        ]
        
        combined_text = ""
        for query in queries:
            try:
                response = query_engine.query(query)
                combined_text += f"\n{query}: {response.response}\n"
            except Exception as e:
                logger.warning(f"Query failed: {e}")
        
        if combined_text:
            return self.extract_financial_metrics(combined_text, company_name, fiscal_year)
        
        return None
    
    def extract_company_summary(self, text: str, company_name: str, fiscal_year: str) -> Optional[CompanySummary]:
        """Extract company summary from report text."""
        
        system_prompt = """You are a financial analyst summarizing annual reports.
        Extract key highlights, risk factors, and business segments.
        Focus on the most significant points. Be concise but comprehensive."""

        user_prompt = f"""Company: {company_name}
Fiscal Year: {fiscal_year}

Extract a company summary from this annual report:

{text[:12000]}

Provide key highlights, risk factors, and business segments."""

        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=CompanySummary,
                temperature=0.2
            )
            
            summary = response.choices[0].message.parsed
            summary.company = company_name
            summary.fiscal_year = fiscal_year
            
            return summary
            
        except Exception as e:
            logger.error(f"Error extracting summary for {company_name}: {e}")
            return None


def create_llm_for_extraction():
    """Create LLM for extraction supporting both OpenAI and OpenRouter."""
    import os
    from llama_index.llms.openai import OpenAI as LlamaOpenAI
    from llama_index.llms.openai_like import OpenAILike
    
    api_key = os.getenv("OPENAI_API_KEY", "")
    
    if api_key.startswith("sk-or-v1-"):
        # OpenRouter uses OpenAILike which doesn't validate model names
        return OpenAILike(
            model="openai/gpt-4o-mini",
            temperature=0.1,
            api_base="https://openrouter.ai/api/v1",
            api_key=api_key,
            is_chat_model=True,
            is_function_calling_model=True,
            context_window=128000
        )
    
    # Standard OpenAI
    return LlamaOpenAI(model="gpt-4o-mini", temperature=0.1)


def extract_metrics_for_all_companies(index_manager) -> List[FinancialMetrics]:
    """Extract financial metrics for all indexed companies."""
    extractor = FinancialExtractor()
    all_metrics = []
    
    from llama_index.core import Settings
    
    Settings.llm = create_llm_for_extraction()
    
    for company in index_manager.list_companies():
        index = index_manager.get_index(company)
        if index:
            query_engine = index.as_query_engine(llm=Settings.llm)
            metrics = extractor.extract_from_index(query_engine, company)
            if metrics:
                all_metrics.append(metrics)
    
    return all_metrics


if __name__ == "__main__":
    # Test extraction
    extractor = FinancialExtractor()
    # Would need actual text to test
    print("FinancialExtractor ready")
