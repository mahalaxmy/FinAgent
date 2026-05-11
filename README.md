# FinSight Complete Workflow

## System Architecture Overview

```

┌─────────────────────────────────────────────────────────────────────────┐

│                         DATA LAYER                                        │

├─────────────────────────────────────────────────────────────────────────┤

│  data/                indexes/              reports/                      │

│  ├── HDFC_AR.pdf      ├── HDFC_index/     ├── HDFC_analyst_report.pdf    │

│  ├── INFOSYS_AR.pdf   ├── INFOSYS_index/  ├── comparison_report.pdf      │

│  └── TCS_AR.pdf       └── TCS_index/                                     │

└─────────────────────────────────────────────────────────────────────────┘

                                    │

                                    ▼

┌─────────────────────────────────────────────────────────────────────────┐

│                      INGESTION PIPELINE                                 │

│                     (src/ingestion.py)                                    │

├─────────────────────────────────────────────────────────────────────────┤

│  1. PDFProcessor.extract_text()                                         │

│     • PyMuPDF extracts text + metadata from each page                    │

│     • Creates Document objects with company, page_number, source         │

│                                                                         │

│  2. IndexManager.create_index()                                         │

│     • SentenceSplitter chunks documents (512 tokens, 50 overlap)         │

│     • OpenAIEmbedding converts chunks to vectors                        │

│     • ChromaVectorStore persists to disk (one collection/company)        │

└─────────────────────────────────────────────────────────────────────────┘

                                    │

                                    ▼

┌─────────────────────────────────────────────────────────────────────────┐

│                    EXTRACTION LAYER                                     │

│                   (src/extraction.py)                                     │

├─────────────────────────────────────────────────────────────────────────┤

│  extract_metrics_for_all_companies()                                    │

│  └── For each company:                                                  │

│      • Query index: "What is the total revenue and net profit?"          │

│      • Query index: "What is the EPS?"                                   │

│      • Query index: "What is the debt equity ratio?"                     │

│      • Query index: "What is the YoY revenue growth?"                    │

│                                                                         │

│  OpenAI Function Calling (beta.chat.completions.parse)                   │

│  └── Response validated against FinancialMetrics Pydantic model          │

│      • revenue_crore, net_profit_crore, eps, debt_to_equity              │

│      • yoy_revenue_growth_pct, operating_margin_pct, roe                │

└─────────────────────────────────────────────────────────────────────────┘

                                    │

                                    ▼

┌─────────────────────────────────────────────────────────────────────────┐

│                   RED FLAG DETECTION                                      │

│                   (src/redflags.py)                                       │

├─────────────────────────────────────────────────────────────────────────┤

│  scan_all_companies()                                                   │

│  └── For each company index:                                            │

│      • Keyword search: litigation, impairment, going concern, etc.       │

│      • Severity scoring: high/medium/low based on keyword type           │

│      • Context extraction: full sentence + surrounding text               │

│                                                                         │

│  Keywords:                                                              │

│  • HIGH: fraud, bankruptcy, insolvency, material weakness                │

│  • MEDIUM: litigation, impairment, regulatory action, penalty              │

│  • LOW: risk, uncertainty, headwind, volatility                          │

└─────────────────────────────────────────────────────────────────────────┘

                                    │

                                    ▼

┌─────────────────────────────────────────────────────────────────────────┐

│              ⭐ NEW: HEALTH SCORING LAYER                                 │

│                (src/health_scorer.py)                                     │

├─────────────────────────────────────────────────────────────────────────┤

│  get_all_health_scores()                                                │

│  └── For each company:                                                  │

│                                                                         │

│      1. calculate_profitability_score()  [Weight: 35%]                  │

│         • Operating margin >25% = 30pts, >15% = 20pts, etc.               │

│         • ROE >20% = 20pts, >15% = 15pts, etc.                            │

│                                                                         │

│      2. calculate_growth_score()           [Weight: 30%]                  │

│         • YoY growth >50% = 100pts, >30% = 90pts, etc.                  │

│         • Negative growth = penalty                                       │

│                                                                         │

│      3. calculate_debt_safety_score()    [Weight: 20%]                  │

│         • D/E <0.5 = 100pts, <1.0 = 85pts, >3.0 = 25pts                  │

│                                                                         │

│      4. calculate_risk_score()           [Weight: 15%]                  │

│         • High red flag = -25pts, Medium = -10pts, Low = -3pts           │

│                                                                         │

│      5. generate_one_line_reason()                                        │

│         • LLM generates investment rationale                              │

│         • Example: "Strong growth momentum with improving margins"        │

│                                                                         │

│  OUTPUT: CompanyHealthScore object                                       │

│  • overall_score (0-100) + color_code (green/amber/red)                 │

│  • verdict: Strong Buy / Buy / Hold / Caution / Avoid                     │

└─────────────────────────────────────────────────────────────────────────┘

                                    │

                                    ▼

┌─────────────────────────────────────────────────────────────────────────┐

│                 ⭐ NEW: PDF REPORT GENERATION                             │

│                (src/report_generator.py)                                  │

├─────────────────────────────────────────────────────────────────────────┤

│  generate_analyst_report(health_score, metrics, redflags)                  │

│  └── Creates professional PDF with:                                      │

│      • Header: Company name + date                                        │

│      • Scorecard: Overall score + verdict + traffic light                 │

│      • Investment rationale: One-line reason                              │

│      • Dimension breakdown: 4 scores with weights                           │

│      • Metrics table: Revenue, Profit, EPS, Growth, ROE                   │

│      • Risk assessment: Red flag counts + top risks                       │

│      • Disclaimer footer                                                  │

│                                                                         │

│  generate_multi_company_report(health_scores)                             │

│  └── Comparison table with all companies ranked by score                  │

└─────────────────────────────────────────────────────────────────────────┘

                                    │

                                    ▼

┌─────────────────────────────────────────────────────────────────────────┐

│                    AGENT LAYER                                            │

│                    (src/agent.py)                                         │

├─────────────────────────────────────────────────────────────────────────┤

│  FinSightAgent.__init__()                                                │

│  ├── Load indexes from disk (IndexManager)                                │

│  ├── Create QueryEngineTool per company                                  │

│  ├── Build RouterQueryEngine (LLM-based tool selection)                  │

│  └── Set Settings.llm = OpenAILike (OpenRouter-compatible)               │

│                                                                         │

│  ASK FLOW:                                                               │

│  ask_with_reasoning(question)                                            │

│  ├── Step 1: Detect question type (comparison vs single)                  │

│  │                                                                         │

│  ├── SINGLE COMPANY:                                                     │

│  │   RouterQueryEngine.select() → picks best tool                         │

│  │   query_engine.query(question) → retrieves chunks                      │

│  │   LLM synthesizes response                                             │

│  │                                                                         │

│  └── COMPARISON:                                                         │

│      Query ALL company tools → collect responses                          │

│      LLM synthesizes comparison table                                     │

│      Returns ReasonedResponse with full transparency                        │

│                                                                         │

│  REASONEDRESPONSE:                                                       │

│  • reasoning_steps: ["Detected comparison", "Queried INFOSYS", ...]      │

│  • companies_queried: ["INFOSYS", "TCS", "HDFC"]                          │

│  • chunks_retrieved: 12                                                   │

│  • confidence: high/medium/low                                          │

│  • what_was_missing: "No debt data found for TCS"                        │

│  • sources: [{text, page, company}, ...]                                  │

└─────────────────────────────────────────────────────────────────────────┘

                                    │

                                    ▼

┌─────────────────────────────────────────────────────────────────────────┐

│                 STREAMLIT UI LAYER                                      │

│                    (app.py)                                               │

├─────────────────────────────────────────────────────────────────────────┤

│  init_agent()                                                            │

│  ├── Process PDFs → extract text → chunk → embed → index                  │

│  ├── Extract metrics for all companies                                   │

│  ├── Scan for red flags                                                  │

│  └── Calculate health scores                                             │

│                                                                         │

│  4 TABS:                                                                 │

│  ┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐  │

│  │ 🏥 Health        │ 💬 Chat         │ 📊 Metrics       │ 🚨 Red Flags    │  │

│  │   Scores         │                 │                  │                 │  │

│  ├─────────────────┼─────────────────┼─────────────────┼─────────────────┤  │

│  │ Scorecards      │ • Ask questions │ • Comparison    │ • By severity   │  │

│  │ Traffic lights  │ • "Show         │   table         │ • Expandable    │  │

│  │ Verdict badges  │   Reasoning"    │ • Styled        │   details       │  │

│  │ "Generate      │   expander      │   highlights    │ • Company       │  │

│  │  Report" btn    │                 │                 │   filters       │  │

│  │ Download PDFs   │                 │                 │                 │  │

│  └─────────────────┴─────────────────┴─────────────────┴─────────────────┘  │

└─────────────────────────────────────────────────────────────────────────┘

```

---

## Complete Data Flow

### Phase 1: Ingestion (One-time per PDF)

```

PDF → PyMuPDF → Text + Metadata → Chunking → Embeddings → ChromaDB

  ↓         ↓           ↓            ↓           ↓            ↓

HDCF.pdf  Page 1-2  HDFC 2024  512-tokens  768-dims   Collection

          Extracted  Company    Chunks      Vectors    "HDFC_index"

```

### Phase 2: Background Processing

```

Index Loaded

     │

     ├── Extraction ──► Query Engine ──► LLM ──► FinancialMetrics

     │                    │              │

     │                    └── Q1-Q5 ────┘

     │

     ├── Red Flags ───► Keyword Scan ──► RedFlag objects

     │                    │              │

     │                    └── "fraud" ─► High severity

     │

     └── Health Score ──► Calculation ──► CompanyHealthScore

                          │

                          ├── Profitability: 85/100

                          ├── Growth: 60/100

                          ├── Debt: 90/100

                          ├── Risk: 70/100

                          │

                          Overall: (85×0.35 + 60×0.30 + 90×0.20 + 70×0.15) = 75.3

                          Verdict: BUY

                          Color: 🟢 GREEN

```

### Phase 3: User Interaction

```

User: "Compare revenue growth"

      Router

         │

         ├── Tool: INFOSYS_analyzer ──► Query: "revenue growth"

         ├── Tool: TCS_analyzer ──────► Query: "revenue growth"

         └── Tool: HDFC_analyzer ─────► Query: "revenue growth"

                                       │

         LLM Synthesis ◄───────────────┘

         │

         Response: "Infosys: 12% | TCS: 8% | HDFC: 15%

                    Winner: HDFC with 15% YoY growth"

         Reasoning Transparency:

         ├─ Companies Queried: INFOSYS, TCS, HDFC

         ├─ Chunks Retrieved: 8

         ├─ Confidence: HIGH

         ├─ Reasoning Steps:

         │   • Detected comparison question

         │   • Routed to all 3 company tools

         │   • Queried INFOSYS: got 3 chunks

         │   • Queried TCS: got 2 chunks

         │   • Queried HDFC: got 3 chunks

         │   • Synthesized comparison using LLM

         └─ Sources:

             • INFOSYS (p.12): "Revenue grew by 12% to ₹1,45,000 crore..."

             • HDFC (p.8): "Total revenue increased by 15% year-over-year..."

```

---

## Key Technical Decisions

| Decision | Why It Matters |

|----------|---------------|

| **Separate index per company** | Enables clean cross-company comparisons without index pollution |

| **RouterQueryEngine** | LLM selects the right tool automatically - no hardcoded routing |

| **Weighted health scoring** | Standardized methodology (35/30/20/15) mimics real analyst frameworks |

| **OpenAILike for OpenRouter** | Bypasses model validation while maintaining LlamaIndex compatibility |

| **ReportLab PDFs** | Professional output suitable for client presentations |

---

## Cost & Performance

| Operation | API Calls | Est. Time | Est. Cost |

|-----------|-----------|-----------|-----------|

| Index 3 reports (6 pages) | ~12 embeddings | 5 sec | $0.01 |

| Extract all metrics | ~15 LLM calls | 15 sec | $0.05 |

| Calculate health scores | 3 LLM calls (reasons) | 3 sec | $0.01 |

| Generate 3 PDF reports | Local processing | 2 sec | $0.00 |

| **Total First Run** | | **25 sec** | **~$0.07** |

| Subsequent queries | 1-3 LLM calls | 2-5 sec | $0.01/query |

---

## What Makes This Production-Ready

1. **Explainability** — Every answer shows its reasoning

2. **Structured Outputs** — Pydantic validation ensures consistency

3. **Visual Impact** — Traffic light scorecards, professional PDFs

4. **Cost Efficiency** — OpenRouter support, local vector storage

5. **Extensibility** — Modular architecture, easy to add new scoring dimensions
