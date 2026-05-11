"""PDF parsing and vector indexing pipeline."""
import os
import logging
from pathlib import Path
from typing import List, Optional
import fitz  # PyMuPDF

from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.node_parser import SentenceSplitter
import chromadb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFProcessor:
    """Process PDF annual reports and extract text with metadata."""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        self.company_name = self._extract_company_name()
        
    def _extract_company_name(self) -> str:
        """Extract company name from filename."""
        filename = self.pdf_path.stem.lower()
        # Common patterns: infosys_ar_2024, tcs-annual-report-2024
        for company in ["infosys", "tcs", "wipro", "hdfc", "reliance", "icici", "axis", "kotak"]:
            if company in filename:
                return company.upper()
        return self.pdf_path.stem.split("_")[0].upper()
    
    def extract_text_with_page_numbers(self) -> List[dict]:
        """Extract text from PDF with page numbers and metadata."""
        documents = []
        
        try:
            doc = fitz.open(self.pdf_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                
                # Clean up text
                text = text.strip()
                if len(text) > 50:  # Skip nearly empty pages
                    documents.append({
                        "text": text,
                        "page_number": page_num + 1,
                        "company": self.company_name,
                        "source": str(self.pdf_path.name)
                    })
            doc.close()
            logger.info(f"Extracted {len(documents)} pages from {self.pdf_path.name}")
        except Exception as e:
            logger.error(f"Error processing {self.pdf_path}: {e}")
            
        return documents
    
    def create_documents(self) -> List[Document]:
        """Create LlamaIndex Document objects."""
        pages = self.extract_text_with_page_numbers()
        documents = []
        
        for page in pages:
            doc = Document(
                text=page["text"],
                metadata={
                    "page_number": page["page_number"],
                    "company": page["company"],
                    "source": page["source"]
                }
            )
            documents.append(doc)
            
        return documents


def create_embedding_model():
    """Create embedding model supporting both OpenAI and OpenRouter."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    
    if api_key.startswith("sk-or-v1-"):
        # OpenRouter - use standard embedding model name
        # OpenRouter routes to the correct provider based on the API key
        return OpenAIEmbedding(
            model="text-embedding-3-small",
            api_base="https://openrouter.ai/api/v1",
            api_key=api_key,
            embed_batch_size=10
        )
    
    # Standard OpenAI
    return OpenAIEmbedding(model="text-embedding-3-small")


class IndexManager:
    """Manage vector indexes for multiple companies."""
    
    def __init__(self, persist_dir: str = "./indexes"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize embedding model
        Settings.embed_model = create_embedding_model()
        
    def create_or_load_index(self, company_name: str, documents: List[Document]) -> VectorStoreIndex:
        """Create a new index or load existing one for a company."""
        company_index_dir = self.persist_dir / company_name.lower()
        chroma_path = str(company_index_dir)
        
        # Check if index already exists
        if company_index_dir.exists():
            logger.info(f"Loading existing index for {company_name}")
            db = chromadb.PersistentClient(path=chroma_path)
            chroma_collection = db.get_collection(company_name.lower())
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            return VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
        
        # Create new index
        logger.info(f"Creating new index for {company_name}")
        company_index_dir.mkdir(parents=True, exist_ok=True)
        
        db = chromadb.PersistentClient(path=chroma_path)
        chroma_collection = db.get_or_create_collection(company_name.lower())
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        # Parse documents into nodes
        parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)
        nodes = parser.get_nodes_from_documents(documents)
        
        # Create index
        index = VectorStoreIndex(nodes, storage_context=storage_context)
        
        logger.info(f"Created index with {len(nodes)} nodes for {company_name}")
        return index
    
    def get_index(self, company_name: str) -> Optional[VectorStoreIndex]:
        """Load an existing index by company name."""
        company_index_dir = self.persist_dir / company_name.lower()
        
        if not company_index_dir.exists():
            return None
            
        chroma_path = str(company_index_dir)
        db = chromadb.PersistentClient(path=chroma_path)
        
        try:
            chroma_collection = db.get_collection(company_name.lower())
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            return VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
        except Exception as e:
            logger.error(f"Error loading index for {company_name}: {e}")
            return None
    
    def list_companies(self) -> List[str]:
        """List all companies with indexes."""
        if not self.persist_dir.exists():
            return []
        return [d.name for d in self.persist_dir.iterdir() if d.is_dir()]


def process_pdf_directory(data_dir: str = "./data", index_dir: str = "./indexes") -> List[str]:
    """Process all PDFs in data directory and create indexes.
    
    Skips PDFs that already have indexes to save API tokens.
    """
    data_path = Path(data_dir)
    index_manager = IndexManager(index_dir)
    
    if not data_path.exists():
        logger.warning(f"Data directory {data_dir} does not exist")
        return []
    
    pdf_files = list(data_path.glob("*.pdf"))
    logger.info(f"Found {len(pdf_files)} PDF files")
    
    processed_companies = []
    skipped_companies = []
    
    for pdf_file in pdf_files:
        processor = PDFProcessor(str(pdf_file))
        company_name = processor.company_name
        
        # Check if index already exists - skip if it does
        if index_manager.get_index(company_name) is not None:
            logger.info(f"Index already exists for {company_name}, skipping PDF extraction")
            skipped_companies.append(company_name)
            continue
        
        # Only extract and index if no existing index
        documents = processor.create_documents()
        
        if documents:
            index = index_manager.create_or_load_index(company_name, documents)
            processed_companies.append(company_name)
            logger.info(f"Indexed {company_name}: {len(documents)} pages")
    
    if skipped_companies:
        logger.info(f"Skipped {len(skipped_companies)} already-indexed companies: {skipped_companies}")
    
    # Return all companies (both newly processed and already existing)
    return processed_companies + skipped_companies


if __name__ == "__main__":
    # Example usage
    companies = process_pdf_directory()
    print(f"Processed companies: {companies}")
