"""FinSight - Annual Report Intelligence Agent."""

from src.models import FinancialMetrics, RedFlag, CompanySummary
from src.agent import FinSightAgent
from src.ingestion import process_pdf_directory, IndexManager
from src.extraction import FinancialExtractor
from src.redflags import RedFlagDetector

__all__ = [
    "FinancialMetrics",
    "RedFlag", 
    "CompanySummary",
    "FinSightAgent",
    "process_pdf_directory",
    "IndexManager",
    "FinancialExtractor",
    "RedFlagDetector"
]
