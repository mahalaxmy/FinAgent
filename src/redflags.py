"""Red flag detection system for annual reports."""
import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

from llama_index.core import VectorStoreIndex

from src.models import RedFlag

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Risk keywords organized by severity
RISK_KEYWORDS = {
    "high": [
        "going concern",
        "material weakness",
        "fraud",
        "embezzlement",
        "bankruptcy",
        "insolvency",
        "default",
        "breach of contract",
        "securities violation",
        "regulatory enforcement",
        "criminal investigation"
    ],
    "medium": [
        "litigation",
        "lawsuit",
        "impairment",
        "write-down",
        "restructuring",
        "layoff",
        "significant doubt",
        "regulatory action",
        "penalty",
        "fine",
        "investigation",
        "subpoena",
        "whistleblower"
    ],
    "low": [
        "risk",
        "uncertainty",
        "challenge",
        "headwind",
        "decline",
        "decrease",
        "volatility",
        "competitive pressure",
        "market shift",
        "regulatory change"
    ]
}


class RedFlagDetector:
    """Detect risk indicators in annual reports."""
    
    def __init__(self):
        self.keywords = RISK_KEYWORDS
        
    def detect_in_text(self, text: str, company: str, page_number: Optional[int] = None) -> List[RedFlag]:
        """Detect red flags in a text segment."""
        red_flags = []
        text_lower = text.lower()
        
        for severity, keywords in self.keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    # Find the sentence containing the keyword
                    sentences = re.split(r'(?<=[.!?])\s+', text)
                    for sentence in sentences:
                        if keyword in sentence.lower():
                            # Get context (surrounding sentences)
                            idx = sentences.index(sentence)
                            context_sentences = sentences[max(0, idx-1):min(len(sentences), idx+2)]
                            context = " ".join(context_sentences)
                            
                            flag = RedFlag(
                                company=company,
                                keyword=keyword,
                                sentence=sentence.strip(),
                                page_number=page_number,
                                severity=severity,
                                context=context.strip()
                            )
                            red_flags.append(flag)
                            break  # Only one flag per keyword per text segment
        
        return red_flags
    
    def scan_index(self, index: VectorStoreIndex, company: str) -> List[RedFlag]:
        """Scan an entire company index for red flags."""
        all_flags = []
        
        # Get all nodes from the index
        try:
            # Use retriever to get all documents
            retriever = index.as_retriever(similarity_top_k=1000)
            
            # Search for each high-risk keyword
            for severity, keywords in self.keywords.items():
                for keyword in keywords:
                    try:
                        nodes = retriever.retrieve(keyword)
                        for node in nodes:
                            text = node.text
                            page_num = node.metadata.get("page_number")
                            
                            # Check if keyword actually appears in the text
                            if keyword in text.lower():
                                # Find exact sentence
                                sentences = re.split(r'(?<=[.!?])\s+', text)
                                for sentence in sentences:
                                    if keyword in sentence.lower() and len(sentence) > 20:
                                        flag = RedFlag(
                                            company=company,
                                            keyword=keyword,
                                            sentence=sentence.strip(),
                                            page_number=page_num,
                                            severity=severity,
                                            context=text[:500]
                                        )
                                        # Avoid duplicates
                                        if not any(f.sentence == flag.sentence for f in all_flags):
                                            all_flags.append(flag)
                                        break
                    except Exception as e:
                        logger.warning(f"Error retrieving for keyword {keyword}: {e}")
                        
        except Exception as e:
            logger.error(f"Error scanning index for {company}: {e}")
        
        # Sort by severity
        severity_order = {"high": 0, "medium": 1, "low": 2}
        all_flags.sort(key=lambda x: severity_order.get(x.severity, 3))
        
        logger.info(f"Found {len(all_flags)} red flags for {company}")
        return all_flags
    
    def get_summary(self, flags: List[RedFlag]) -> Dict:
        """Get summary statistics of red flags."""
        if not flags:
            return {"total": 0, "high": 0, "medium": 0, "low": 0, "by_company": {}}
        
        by_company = {}
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        
        for flag in flags:
            severity_counts[flag.severity] += 1
            if flag.company not in by_company:
                by_company[flag.company] = []
            by_company[flag.company].append(flag)
        
        return {
            "total": len(flags),
            "high": severity_counts["high"],
            "medium": severity_counts["medium"],
            "low": severity_counts["low"],
            "by_company": by_company
        }


def scan_all_companies(index_manager) -> List[RedFlag]:
    """Scan all company indexes for red flags."""
    detector = RedFlagDetector()
    all_flags = []
    
    for company in index_manager.list_companies():
        index = index_manager.get_index(company)
        if index:
            flags = detector.scan_index(index, company)
            all_flags.extend(flags)
    
    return all_flags


if __name__ == "__main__":
    detector = RedFlagDetector()
    print("RedFlagDetector ready")
