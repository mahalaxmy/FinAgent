"""Multi-company agent with RouterQueryEngine for cross-company reasoning."""
import os
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

from llama_index.core import Settings
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.query_engine import RouterQueryEngine
from llama_index.core.selectors import LLMSingleSelector
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.llms.openai import OpenAI as LlamaOpenAI
from llama_index.llms.openai_like import OpenAILike

from src.ingestion import IndexManager
from src.extraction import FinancialExtractor, extract_metrics_for_all_companies
from src.redflags import RedFlagDetector, scan_all_companies
from src.health_scorer import get_all_health_scores
from src.cache_manager import (
    save_metrics_cache, load_metrics_cache,
    save_redflags_cache, load_redflags_cache,
    save_health_scores_cache, load_health_scores_cache,
    get_cache_info, clear_all_cache
)
from src.models import FinancialMetrics, RedFlag, ReasonedResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_llm():
    """Create LLM supporting both OpenAI and OpenRouter."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    
    if api_key.startswith("sk-or-v1-"):
        # OpenRouter uses OpenAILike which doesn't validate model names
        return OpenAILike(
            model="openai/gpt-4o-mini",
            temperature=0.2,
            api_base="https://openrouter.ai/api/v1",
            api_key=api_key,
            is_chat_model=True,
            is_function_calling_model=True,
            context_window=128000
        )
    
    # Standard OpenAI
    return LlamaOpenAI(model="gpt-4o-mini", temperature=0.2)


def get_model_name():
    """Get the appropriate model name for the current provider."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key.startswith("sk-or-v1-"):
        return "openai/gpt-4o-mini"  # OpenRouter format
    return "gpt-4o-mini"  # OpenAI format


class FinSightAgent:
    """Multi-company financial analyst agent."""
    
    def __init__(self, index_dir: str = "./indexes"):
        self.index_manager = IndexManager(index_dir)
        self.extractor = FinancialExtractor()
        self.redflag_detector = RedFlagDetector()
        
        # Set up LLM
        Settings.llm = create_llm()
        
        # Initialize components
        self.query_tools = []
        self.router_engine = None
        self.metrics_cache = {}
        self.redflags_cache = []
        self.health_scores_cache = []
        
        self._initialize_tools()
    
    def _initialize_tools(self):
        """Initialize query tools for each company."""
        companies = self.index_manager.list_companies()
        
        if not companies:
            logger.warning("No companies indexed yet")
            return
        
        tools = []
        for company in companies:
            index = self.index_manager.get_index(company)
            if index:
                # Create query engine for this company with explicit LLM
                from llama_index.core import Settings
                query_engine = index.as_query_engine(
                    similarity_top_k=5,
                    response_mode="compact",
                    llm=Settings.llm
                )
                
                tool = QueryEngineTool(
                    query_engine=query_engine,
                    metadata=ToolMetadata(
                        name=f"{company.lower()}_analyzer",
                        description=f"Analyzes {company} annual reports. Use for questions about {company}'s financial performance, risks, and business operations."
                    )
                )
                tools.append(tool)
                logger.info(f"Created tool for {company}")
        
        self.query_tools = tools
        
        # Create router engine if we have tools
        if tools:
            self.router_engine = RouterQueryEngine(
                selector=LLMSingleSelector.from_defaults(),
                query_engine_tools=tools,
                verbose=True
            )
            logger.info(f"Router engine initialized with {len(tools)} tools")
    
    def ask(self, question: str) -> Dict:
        """Ask a question - agent routes to appropriate company/companies."""
        return self.ask_with_reasoning(question)
    
    def ask_with_reasoning(self, question: str) -> ReasonedResponse:
        """Ask a question with full reasoning transparency."""
        
        if not self.query_tools:
            return ReasonedResponse(
                answer="No companies indexed yet. Please upload annual report PDFs first.",
                companies_queried=[],
                chunks_retrieved=0,
                confidence="low",
                what_was_missing="No company data available",
                reasoning_steps=["Checked for indexed companies", "Found no companies indexed"],
                sources=[]
            )
        
        reasoning_steps = []
        sources = []
        
        # Step 1: Detect question type
        is_comparison = any(word in question.lower() for word in 
                          ["compare", "comparison", "vs", "versus", "between", "best", "worst", "highest", "lowest"])
        
        reasoning_steps.append(f"Detected question type: {'comparison' if is_comparison else 'single company'}")
        
        if is_comparison and len(self.query_tools) > 1:
            reasoning_steps.append("Routing to comparison handler")
            return self._handle_comparison_question_with_reasoning(question, reasoning_steps)
        
        # Single company question - use router
        reasoning_steps.append("Using RouterQueryEngine to select appropriate company tool")
        
        try:
            if self.router_engine:
                response = self.router_engine.query(question)
                answer = str(response)
                source_nodes = getattr(response, 'source_nodes', [])
                sources = [{"text": str(n.text)[:200], "page": n.metadata.get("page_number", "unknown")} 
                          for n in source_nodes[:3]]
                company = self._detect_company_from_response(answer)
                
                reasoning_steps.append(f"Router selected: {company}_analyzer tool")
                reasoning_steps.append(f"Retrieved {len(source_nodes)} chunks from {company} index")
                
                # Determine confidence
                confidence = self._assess_confidence(answer, source_nodes)
                reasoning_steps.append(f"Confidence assessment: {confidence}")
                
                return ReasonedResponse(
                    answer=answer,
                    companies_queried=[company],
                    chunks_retrieved=len(source_nodes),
                    confidence=confidence,
                    what_was_missing=None if len(source_nodes) > 0 else "No relevant chunks found",
                    reasoning_steps=reasoning_steps,
                    sources=sources
                )
        except Exception as e:
            logger.error(f"Router query failed: {e}")
            reasoning_steps.append(f"Router failed: {str(e)}")
        
        # Fallback
        reasoning_steps.append("Falling back to querying all companies")
        return self._query_all_companies_with_reasoning(question, reasoning_steps)
    
    def _assess_confidence(self, answer: str, source_nodes: list) -> str:
        """Assess confidence level based on answer quality and sources."""
        if not source_nodes:
            return "low"
        
        # High confidence: specific numbers and multiple sources
        has_numbers = any(char.isdigit() for char in answer)
        has_multiple_sources = len(source_nodes) >= 2
        
        if has_numbers and has_multiple_sources and len(answer) > 100:
            return "high"
        elif has_numbers or has_multiple_sources:
            return "medium"
        else:
            return "low"
    
    def _handle_comparison_question(self, question: str) -> Dict:
        """Handle cross-company comparison questions."""
        result = self._handle_comparison_question_with_reasoning(question, [])
        return {
            "answer": result.answer,
            "sources": result.sources,
            "companies_queried": result.companies_queried
        }
    
    def _handle_comparison_question_with_reasoning(self, question: str, reasoning_steps: list) -> ReasonedResponse:
        """Handle comparison with full reasoning transparency."""
        responses = {}
        total_chunks = 0
        all_sources = []
        
        reasoning_steps.append(f"Querying {len(self.query_tools)} companies for comparison data")
        
        for tool in self.query_tools:
            try:
                company = tool.metadata.name.replace("_analyzer", "").upper()
                response = tool.query_engine.query(question)
                responses[company] = str(response)
                source_nodes = getattr(response, 'source_nodes', [])
                total_chunks += len(source_nodes)
                sources = [{"text": str(n.text)[:200], "page": n.metadata.get("page_number", "unknown"), "company": company} 
                          for n in source_nodes[:2]]
                all_sources.extend(sources)
                reasoning_steps.append(f"Queried {company}: got {len(source_nodes)} chunks")
            except Exception as e:
                logger.warning(f"Query failed for {tool.metadata.name}: {e}")
                reasoning_steps.append(f"Query failed for {company}: {str(e)}")
        
        # Synthesize comparison
        if responses:
            combined = "\n\n".join([f"**{company}:**\n{response}" for company, response in responses.items()])
            
            # Use LLM to create a proper comparison
            comparison_prompt = f"""Based on the following company information, provide a clear comparison answering: {question}

{combined}

Provide a structured comparison with specific numbers where available. Highlight key differences and which company performs better on each metric."""

            reasoning_steps.append("Synthesizing comparison using LLM")
            llm = create_llm()
            comparison_response = llm.complete(comparison_prompt)
            
            return ReasonedResponse(
                answer=str(comparison_response),
                companies_queried=list(responses.keys()),
                chunks_retrieved=total_chunks,
                confidence="high" if len(responses) >= 2 else "medium",
                what_was_missing=None if len(responses) > 0 else "No company data available",
                reasoning_steps=reasoning_steps,
                sources=all_sources[:5]
            )
        
        return ReasonedResponse(
            answer="Unable to gather information for comparison.",
            companies_queried=[],
            chunks_retrieved=0,
            confidence="low",
            what_was_missing="No company responses received",
            reasoning_steps=reasoning_steps,
            sources=[]
        )
    
    def _query_all_companies(self, question: str) -> Dict:
        """Fallback: Query all companies and combine responses."""
        result = self._query_all_companies_with_reasoning(question, [])
        return {
            "answer": result.answer,
            "sources": result.sources,
            "companies_queried": result.companies_queried
        }
    
    def _query_all_companies_with_reasoning(self, question: str, reasoning_steps: list) -> ReasonedResponse:
        """Fallback query with reasoning transparency."""
        responses = {}
        total_chunks = 0
        all_sources = []
        
        reasoning_steps.append(f"Fallback: Querying all {len(self.query_tools)} companies")
        
        for tool in self.query_tools:
            try:
                company = tool.metadata.name.replace("_analyzer", "").upper()
                response = tool.query_engine.query(question)
                responses[company] = str(response)
                source_nodes = getattr(response, 'source_nodes', [])
                total_chunks += len(source_nodes)
                sources = [{"text": str(n.text)[:200], "page": n.metadata.get("page_number", "unknown"), "company": company} 
                          for n in source_nodes[:2]]
                all_sources.extend(sources)
                reasoning_steps.append(f"{company}: Retrieved {len(source_nodes)} chunks")
            except Exception as e:
                logger.warning(f"Query failed: {e}")
                reasoning_steps.append(f"Query failed for {company}: {str(e)[:50]}")
        
        # Combine responses
        if responses:
            combined_answer = "\n\n".join([f"**{company}:** {response}" for company, response in responses.items()])
            confidence = "high" if len(responses) >= 2 else "medium"
            reasoning_steps.append(f"Combined responses from {len(responses)} companies")
            
            return ReasonedResponse(
                answer=combined_answer,
                companies_queried=list(responses.keys()),
                chunks_retrieved=total_chunks,
                confidence=confidence,
                what_was_missing=None,
                reasoning_steps=reasoning_steps,
                sources=all_sources[:5]
            )
        
        return ReasonedResponse(
            answer="I couldn't find information to answer this question.",
            companies_queried=[],
            chunks_retrieved=0,
            confidence="low",
            what_was_missing="No responses from any company",
            reasoning_steps=reasoning_steps,
            sources=[]
        )
    
    def _detect_company_from_response(self, response: str) -> str:
        """Detect which company was queried from response."""
        companies = self.index_manager.list_companies()
        for company in companies:
            if company.upper() in response.upper():
                return company.upper()
        return "Unknown"
    
    def get_all_metrics(self) -> List[FinancialMetrics]:
        """Get financial metrics for all companies. Uses cache if available."""
        # Try memory cache first
        if self.metrics_cache:
            return self.metrics_cache
        
        # Try disk cache
        cached = load_metrics_cache()
        if cached:
            logger.info(f"Loaded {len(cached)} metrics from cache")
            self.metrics_cache = cached
            return cached
        
        # Extract fresh
        logger.info("Extracting metrics from documents (cache miss)...")
        self.metrics_cache = extract_metrics_for_all_companies(self.index_manager)
        save_metrics_cache(self.metrics_cache)
        return self.metrics_cache
    
    def get_all_redflags(self) -> List[RedFlag]:
        """Get red flags for all companies. Uses cache if available."""
        # Try memory cache first
        if self.redflags_cache:
            return self.redflags_cache
        
        # Try disk cache
        cached = load_redflags_cache()
        if cached:
            logger.info(f"Loaded {len(cached)} red flags from cache")
            self.redflags_cache = cached
            return cached
        
        # Scan fresh
        logger.info("Scanning for red flags (cache miss)...")
        self.redflags_cache = scan_all_companies(self.index_manager)
        save_redflags_cache(self.redflags_cache)
        return self.redflags_cache
    
    def get_health_scores(self):
        """Get health scores for all companies. Uses cache if available."""
        # Try memory cache first
        if self.health_scores_cache:
            return self.health_scores_cache
        
        # Try disk cache
        cached = load_health_scores_cache()
        if cached:
            logger.info(f"Loaded {len(cached)} health scores from cache")
            self.health_scores_cache = cached
            return cached
        
        # Calculate fresh
        logger.info("Calculating health scores (cache miss)...")
        metrics = self.get_all_metrics()
        redflags_dict = {}
        for rf in self.get_all_redflags():
            if rf.company not in redflags_dict:
                redflags_dict[rf.company] = []
            redflags_dict[rf.company].append(rf)
        self.health_scores_cache = get_all_health_scores(metrics, redflags_dict)
        save_health_scores_cache(self.health_scores_cache)
        return self.health_scores_cache
    
    def refresh_data(self, clear_cache: bool = False):
        """Refresh metrics, red flags, and health scores.
        
        Args:
            clear_cache: If True, clear disk cache and re-extract everything.
        """
        self._initialize_tools()
        
        if clear_cache:
            logger.info("Clearing cache and re-extracting all data...")
            clear_all_cache()
            self.metrics_cache = []
            self.redflags_cache = []
            self.health_scores_cache = []
        
        # Force refresh by clearing memory cache
        self.metrics_cache = []
        self.redflags_cache = []
        self.health_scores_cache = []
    
    def get_cache_status(self) -> dict:
        """Get cache status for display in UI."""
        return get_cache_info()
    
    def get_loaded_companies(self) -> List[str]:
        """Get list of loaded companies."""
        return self.index_manager.list_companies()


class ComparisonTool:
    """Tool for generating comparison tables and analysis."""
    
    def __init__(self, agent: FinSightAgent):
        self.agent = agent
    
    def compare_metric(self, metric_name: str) -> Dict:
        """Compare a specific metric across all companies."""
        metrics = self.agent.get_all_metrics()
        
        comparison = {}
        for m in metrics:
            value = getattr(m, metric_name, None)
            if value is not None:
                comparison[m.company] = value
        
        # Rank companies
        if comparison:
            ranked = sorted(comparison.items(), key=lambda x: x[1], reverse=True)
            return {
                "metric": metric_name,
                "values": comparison,
                "ranking": ranked,
                "best": ranked[0] if ranked else None
            }
        
        return {"metric": metric_name, "values": {}, "ranking": [], "best": None}
    
    def compare_all_metrics(self) -> List[Dict]:
        """Compare all available metrics across companies."""
        metrics_to_compare = [
            "revenue_crore",
            "net_profit_crore", 
            "eps",
            "debt_to_equity",
            "yoy_revenue_growth_pct",
            "operating_margin_pct",
            "roe"
        ]
        
        return [self.compare_metric(m) for m in metrics_to_compare]


if __name__ == "__main__":
    # Test the agent
    agent = FinSightAgent()
    print(f"Loaded companies: {agent.get_loaded_companies()}")
