# 🏦 FinSight — Annual Report Intelligence Agent

An AI agent that reads multiple company annual reports (PDFs), extracts key financial signals, compares companies side by side, detects red flags, and answers analyst-style questions — all from a chat interface.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-green.svg)
![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.10+-orange.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)

---

## ✨ What It Does

| Feature | Description |
|---------|-------------|
| 📄 **Multi-Document Upload** | Drop in 2-5 annual reports from Indian companies (Infosys, TCS, HDFC, etc.) |
| 💬 **Analyst Q&A** | Ask "Which company has the best revenue growth?" or "What are the risk factors mentioned by Infosys?" |
| 📊 **Structured Extraction** | Auto-extracts revenue, profit, EPS, debt ratio, YoY growth into clean JSON |
| 🚨 **Red Flag Detection** | Scans for warning language: "litigation", "going concern", "impairment" |
| 🔍 **Cross-Company Reasoning** | Agent queries multiple indexes, combines evidence, synthesizes answers |

---

## 🎯 Why This Stands Out

| Generic Chatbot | **FinSight** |
|----------------|--------------|
| Upload one PDF → ask questions → get answers | **Multiple PDFs → structured extraction → cross-document reasoning** |
| No structure, no comparison | **Domain-aware with typed Pydantic models** |
| Just retrieval | **Proactive red flag detection (agentic behavior)** |

### The 5 Things That Make It Unique

1. **Multi-document reasoning** — Queries N documents and synthesizes across them
2. **Structured extraction layer** — Revenue, EPS, profit margin as typed Pydantic fields
3. **Red flag detection** — Proactive intelligence, not just retrieval
4. **Real public data** — Uses actual annual reports from NSE/BSE
5. **Domain specificity** — Understands "going concern", debt ratios, EPS significance

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        STREAMLIT UI                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Chat Tab    │  │ Metrics Tab │  │ Red Flags Tab           │ │
│  │ (Q&A)       │  │ (Comparison)│  │ (Risk Detection)        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FINSIGHT AGENT                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              RouterQueryEngine                              │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌────────────────────────┐│ │
│  │  │ Infosys     │ │ TCS         │ │ HDFC                   ││ │
│  │  │ QueryEngine │ │ QueryEngine │ │ QueryEngine            ││ │
│  │  │ (Index)     │ │ (Index)     │ │ (Index)                ││ │
│  │  └─────────────┘ └─────────────┘ └────────────────────────┘│ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐ │
│  │ FinancialExtractor  │  │ RedFlagDetector                 │ │
│  │ (Pydantic + OpenAI) │  │ (Risk Keyword Scanning)         │ │
│  └─────────────────────┘  └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ PDF Reports  │  │ ChromaDB     │  │ Vector Embeddings    │  │
│  │ (data/)      │──│ (indexes/)   │──│ (text-embedding-3)   │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Component | Tool | Purpose |
|-----------|------|---------|
| **Core Framework** | LlamaIndex | Multi-index management, RouterQueryEngine |
| **PDF Parsing** | PyMuPDF | Extract text from annual reports |
| **Vector Store** | ChromaDB | One collection per company |
| **Embeddings** | OpenAI text-embedding-3-small | Document embeddings |
| **LLM** | GPT-4o-mini | Chat, extraction, reasoning |
| **Validation** | Pydantic | Structured output models |
| **UI** | Streamlit | Chat interface, tables, visualization |

---

## 📁 Project Structure

```
finsight/
├── data/                           # Annual report PDFs
│   ├── infosys_ar_2024.pdf
│   ├── tcs_ar_2024.pdf
│   └── hdfc_ar_2024.pdf
├── indexes/                        # Persisted ChromaDB indexes
│   ├── infosys/
│   ├── tcs/
│   └── hdfc/
├── src/
│   ├── __init__.py
│   ├── models.py                   # Pydantic models
│   ├── ingestion.py                # PDF parsing + indexing
│   ├── extraction.py               # Financial metrics extraction
│   ├── redflags.py                 # Risk detection
│   └── agent.py                    # RouterQueryEngine + tools
├── app.py                          # Streamlit UI
├── requirements.txt
├── .env.example
└── README.md                       # This file
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone <repo-url>
cd finsight
pip install -r requirements.txt
```

### 2. Set API Key

```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### 3. Add Annual Reports

Download annual reports from [NSE India](https://www.nseindia.com) or [BSE](https://www.bseindia.com):

```bash
# Place PDFs in data/ folder
mkdir -p data
cp ~/Downloads/infosys_ar_2024.pdf data/
cp ~/Downloads/tcs_ar_2024.pdf data/
```

### 4. Run

```bash
streamlit run app.py
```

---

## 💡 Example Questions

### Single Company
- "What is Infosys's revenue for FY2024?"
- "What are the main risk factors mentioned by TCS?"
- "Summarize HDFC's key business highlights"

### Cross-Company Comparison
- "Which company has the best revenue growth?"
- "Compare debt levels across all three companies"
- "Which company has the highest profit margin?"
- "What risks are common across all companies?"

### Financial Analysis
- "What is the EPS trend for each company?"
- "Compare operating margins"
- "Which company has the strongest balance sheet?"

---

## 📊 Pydantic Models

### FinancialMetrics
```python
class FinancialMetrics(BaseModel):
    company: str
    fiscal_year: str
    revenue_crore: Optional[float]
    net_profit_crore: Optional[float]
    eps: Optional[float]
    debt_to_equity: Optional[float]
    yoy_revenue_growth_pct: Optional[float]
    operating_margin_pct: Optional[float]
    roe: Optional[float]
```

### RedFlag
```python
class RedFlag(BaseModel):
    company: str
    keyword: str
    sentence: str
    page_number: Optional[int]
    severity: Literal["low", "medium", "high"]
    context: str
```

---

## 🚨 Red Flag Detection

The agent scans for these risk keywords:

| Severity | Keywords |
|----------|----------|
| **High** | going concern, material weakness, fraud, embezzlement, bankruptcy, insolvency, default, securities violation |
| **Medium** | litigation, lawsuit, impairment, write-down, restructuring, regulatory action, penalty, investigation |
| **Low** | risk, uncertainty, challenge, headwind, decline, volatility, competitive pressure |

---

## 💰 Cost to Run

| Item | Cost |
|------|------|
| OpenAI API (embeddings + chat + extraction) | ~$2-5 total |
| HuggingFace Spaces deployment | Free |
| Data (annual reports) | Free from NSE/BSE |

**Total: Under ₹500**

---

## 📝 What I Learned

> The difference between "chat with a PDF" and a real document intelligence system is **structured extraction**, **validation**, and **cross-document reasoning**. That gap is where the actual engineering lives.

### Key Technical Insights:

1. **Multi-index architecture** — Separate vector stores per company enables clean cross-company comparisons
2. **Pydantic validation** — LLM outputs must be validated before touching the UI
3. **RouterQueryEngine** — The selector pattern elegantly handles routing to appropriate company indexes
4. **Structured extraction** — Function calling with response_format ensures reliable JSON output
5. **Proactive detection** — Scanning for red flags without user prompting is true agentic behavior

---

## 🌐 Deployment

### HuggingFace Spaces

1. Create a new Space (Streamlit SDK)
2. Upload all files
3. Add `OPENAI_API_KEY` to Space secrets
4. Include sample PDFs or provide upload interface

```bash
# Create HuggingFace repo
huggingface-cli repo create finsight --type space --sdk streamlit
```

---

## 🔗 Links

- **Live Demo**: [HuggingFace Spaces](#)
- **LinkedIn Post**: [#AIEngineering #RAG #LlamaIndex](#)
- **Video Demo**: [60-second walkthrough](#)

---

## 📜 License

MIT License — Built for educational and demonstration purposes.

---

**Built with ❤️ by [Your Name]**

*Impressed AI engineers and recruiters at: CRED, Razorpay, Zerodha, Groww, Nura Analytics, Hyperbolic, Deloitte, PwC, EY*
