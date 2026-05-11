"""Streamlit UI for FinSight - Annual Report Intelligence Agent."""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

from src.agent import FinSightAgent, ComparisonTool
from src.ingestion import process_pdf_directory
from src.models import FinancialMetrics, RedFlag, CompanyHealthScore, ReasonedResponse
from src.report_generator import generate_analyst_report, generate_multi_company_report
from pathlib import Path

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="FinSight - Annual Report Intelligence",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "agent" not in st.session_state:
    st.session_state.agent = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "companies_loaded" not in st.session_state:
    st.session_state.companies_loaded = []
if "metrics" not in st.session_state:
    st.session_state.metrics = []
if "redflags" not in st.session_state:
    st.session_state.redflags = []
if "health_scores" not in st.session_state:
    st.session_state.health_scores = []
if "last_reasoned_response" not in st.session_state:
    st.session_state.last_reasoned_response = None


def init_agent():
    """Initialize or reinitialize the agent."""
    with st.spinner("Processing PDFs and building indexes..."):
        # Check data directory
        data_dir = Path("./data")
        if not data_dir.exists():
            st.error("❌ data/ folder not found! Create it and add PDF files.")
            return
        
        pdf_files = list(data_dir.glob("*.pdf"))
        if not pdf_files:
            st.warning("⚠️ No PDF files found in data/ folder")
            return
        
        st.info(f"Found {len(pdf_files)} PDF files: {', '.join([p.name for p in pdf_files])}")
        
        # First, process any new PDFs in data/ folder
        try:
            processed = process_pdf_directory("./data", "./indexes")
            if processed:
                st.success(f"✅ Indexed {len(processed)} companies: {', '.join(processed)}")
            else:
                st.warning("No new companies were indexed")
        except Exception as e:
            st.error(f"❌ Error processing PDFs: {e}")
            import traceback
            st.code(traceback.format_exc())
        
        # Now initialize agent with the indexes
        st.session_state.agent = FinSightAgent()
        st.session_state.companies_loaded = st.session_state.agent.get_loaded_companies()
        
        if st.session_state.companies_loaded:
            st.success(f"✅ Loaded {len(st.session_state.companies_loaded)} companies: {', '.join(st.session_state.companies_loaded)}")
            
            # Check cache status first
            cache_status = st.session_state.agent.get_cache_status()
            has_cache = any(info.get("count", 0) > 0 for info in cache_status.values())
            
            if has_cache:
                st.info("💾 Using cached data (metrics, red flags, health scores). Click 'Clear Cache & Re-extract' to refresh.")
            
            # Load metrics, red flags, and health scores (uses cache if available)
            with st.spinner("Loading financial metrics..."):
                st.session_state.metrics = st.session_state.agent.get_all_metrics()
                if not has_cache:
                    st.caption(f"📊 Extracted {len(st.session_state.metrics)} metrics (API tokens used)")
            
            with st.spinner("Loading red flags..."):
                st.session_state.redflags = st.session_state.agent.get_all_redflags()
                if not has_cache:
                    st.caption(f"🚨 Found {len(st.session_state.redflags)} red flags (API tokens used)")
            
            with st.spinner("Loading health scores..."):
                st.session_state.health_scores = st.session_state.agent.get_health_scores()
                if not has_cache:
                    st.caption(f"🏥 Calculated {len(st.session_state.health_scores)} health scores (API tokens used)")
            
            if has_cache:
                st.success("✅ Loaded from cache! No API tokens spent.")
            else:
                st.success("✅ Fresh extraction complete! Data cached for next time.")
            
            st.caption("Ready! Check the Health Scores, Metrics, and Red Flags tabs.")


def display_metrics_table():
    """Display financial metrics comparison table."""
    if not st.session_state.metrics:
        st.info("No financial metrics extracted yet. Process reports first.")
        return
    
    # Convert to DataFrame
    data = []
    for m in st.session_state.metrics:
        data.append({
            "Company": m.company,
            "Fiscal Year": m.fiscal_year,
            "Revenue (Cr)": m.revenue_crore,
            "Net Profit (Cr)": m.net_profit_crore,
            "EPS": m.eps,
            "D/E Ratio": m.debt_to_equity,
            "YoY Growth %": m.yoy_revenue_growth_pct,
            "Op Margin %": m.operating_margin_pct,
            "ROE %": m.roe
        })
    
    df = pd.DataFrame(data)
    
    # Highlight best values
    st.subheader("📊 Financial Metrics Comparison")
    st.dataframe(df.style.highlight_max(subset=["Revenue (Cr)", "Net Profit (Cr)", "EPS", "YoY Growth %", "ROE %"], color="green")
                   .highlight_min(subset=["D/E Ratio"], color="green"), 
                 use_container_width=True)


def display_redflags():
    """Display red flags table."""
    if not st.session_state.redflags:
        st.success("✅ No significant red flags detected!")
        return
    
    st.subheader("🚨 Risk Indicators")
    
    # Group by severity
    high_flags = [f for f in st.session_state.redflags if f.severity == "high"]
    medium_flags = [f for f in st.session_state.redflags if f.severity == "medium"]
    low_flags = [f for f in st.session_state.redflags if f.severity == "low"]
    
    # Summary stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("High Severity", len(high_flags), delta_color="inverse")
    with col2:
        st.metric("Medium Severity", len(medium_flags))
    with col3:
        st.metric("Low Severity", len(low_flags))
    
    # Display flags by severity
    for severity, flags, color in [("high", high_flags, "red"), ("medium", medium_flags, "orange"), ("low", low_flags, "yellow")]:
        if flags:
            with st.expander(f"{severity.upper()} Severity ({len(flags)} items)", expanded=(severity == "high")):
                for flag in flags[:10]:  # Limit to 10 per severity
                    st.markdown(f"""
                    <div style="border-left: 4px solid {color}; padding-left: 10px; margin: 10px 0;">
                        <b>{flag.company}</b> | Page {flag.page_number or 'N/A'}<br>
                        <span style="color: {color};">🔍 {flag.keyword}</span><br>
                        <i>"{flag.sentence[:200]}..."</i>
                    </div>
                    """, unsafe_allow_html=True)


def display_health_scores():
    """Display Company Health Score cards with traffic lights."""
    if not st.session_state.health_scores:
        st.info("No health scores calculated yet. Process reports first.")
        return
    
    st.subheader("🏥 Company Health Scorecards")
    st.caption("0-100 score across 4 dimensions. Click a card to see details.")
    
    # Color mapping
    color_map = {
        "green": "#22c55e",
        "amber": "#f59e0b",
        "red": "#ef4444"
    }
    
    # Display scorecards in a grid
    cols = st.columns(min(3, len(st.session_state.health_scores)))
    
    for i, score in enumerate(st.session_state.health_scores):
        col = cols[i % 3]
        
        with col:
            # Traffic light indicator
            traffic_light = "🟢" if score.color_code == "green" else "🟡" if score.color_code == "amber" else "🔴"
            
            with st.expander(f"{traffic_light} {score.company} - {score.overall_score:.0f}/100", expanded=True):
                # Overall score with color
                score_color = color_map.get(score.color_code, "#666")
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, {score_color}20, {score_color}05);
                    border-left: 5px solid {score_color};
                    padding: 15px;
                    border-radius: 8px;
                    margin: 10px 0;
                ">
                    <h3 style="margin: 0; color: {score_color};">{score.verdict}</h3>
                    <p style="margin: 5px 0; font-style: italic; color: #444;">{score.one_line_reason}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Dimension scores
                st.markdown("**Dimension Breakdown:**")
                dim_data = {
                    "📈 Profitability (35%)": f"{score.profitability_score:.0f}/100",
                    "📊 Growth (30%)": f"{score.growth_score:.0f}/100",
                    "🏛️ Debt Safety (20%)": f"{score.debt_safety_score:.0f}/100",
                    "⚠️ Risk Profile (15%)": f"{score.risk_score:.0f}/100",
                }
                
                for dim, val in dim_data.items():
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{dim}: **{val}**")
                
                # Generate report button
                if st.button(f"📄 Generate Report", key=f"report_{score.company}"):
                    with st.spinner(f"Generating report for {score.company}..."):
                        # Find metrics for this company
                        metrics = next((m for m in st.session_state.metrics if m.company == score.company), None)
                        redflags = [rf for rf in st.session_state.redflags if rf.company == score.company]
                        
                        if metrics:
                            try:
                                report_path = generate_analyst_report(score, metrics, redflags)
                                st.success(f"✅ Report saved: `{report_path}`")
                                
                                # Provide download link
                                with open(report_path, "rb") as f:
                                    st.download_button(
                                        label="📥 Download PDF",
                                        data=f,
                                        file_name=f"{score.company}_analyst_report.pdf",
                                        mime="application/pdf",
                                        key=f"download_{score.company}"
                                    )
                            except Exception as e:
                                st.error(f"❌ Error generating report: {e}")
                        else:
                            st.error(f"No metrics found for {score.company}")
    
    # Multi-company comparison report
    if len(st.session_state.health_scores) > 1:
        st.divider()
        if st.button("📊 Generate Comparison Report (All Companies)", use_container_width=True):
            with st.spinner("Generating comparison report..."):
                try:
                    report_path = generate_multi_company_report(st.session_state.health_scores)
                    st.success(f"✅ Comparison report saved: `{report_path}`")
                    
                    with open(report_path, "rb") as f:
                        st.download_button(
                            label="📥 Download Comparison PDF",
                            data=f,
                            file_name="comparison_report.pdf",
                            mime="application/pdf"
                        )
                except Exception as e:
                    st.error(f"❌ Error generating comparison report: {e}")


def main():
    """Main application."""
    
    # Sidebar
    with st.sidebar:
        st.title("🏦 FinSight")
        st.caption("Annual Report Intelligence Agent")
        
        # API Key input and provider detection
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            api_key_input = st.text_input("API Key (OpenAI or OpenRouter)", type="password")
            if api_key_input:
                os.environ["OPENAI_API_KEY"] = api_key_input
                api_key = api_key_input
                st.success("API Key set!")
        
        # Show which provider is being used
        if api_key:
            if api_key.startswith("sk-or-v1-"):
                st.info("🔌 Using OpenRouter")
            else:
                st.info("🔌 Using OpenAI")
        
        st.divider()
        
        # Data management
        st.subheader("📁 Data Management")
        
        if st.button("🔄 Refresh Indexes", use_container_width=True):
            init_agent()
            st.rerun()
        
        # Show loaded companies
        if st.session_state.companies_loaded:
            st.success(f"✅ {len(st.session_state.companies_loaded)} companies loaded")
            for company in st.session_state.companies_loaded:
                st.caption(f"• {company}")
            
            # Show cache status
            if st.session_state.agent:
                cache_status = st.session_state.agent.get_cache_status()
                with st.expander("💾 Cache Status"):
                    for key, info in cache_status.items():
                        count = info.get("count", 0)
                        cached_at = info.get("cached_at", "Never")
                        if count > 0:
                            st.caption(f"✅ {key}: {count} items")
                        else:
                            st.caption(f"❌ {key}: No cache")
            
            # Clear cache option
            if st.button("🗑️ Clear Cache & Re-extract", use_container_width=True, type="secondary"):
                if st.session_state.agent:
                    st.session_state.agent.refresh_data(clear_cache=True)
                    st.session_state.metrics = []
                    st.session_state.redflags = []
                    st.session_state.health_scores = []
                    st.rerun()
        else:
            st.warning("⚠️ No companies indexed")
            st.info("Add PDFs to the data/ folder and click Refresh")
        
        st.divider()
        
        # Navigation
        st.subheader("🧭 Navigation")
        tab = st.radio("Select View", ["🏥 Health Scores", "💬 Chat", "📊 Metrics", "🚨 Red Flags"], label_visibility="collapsed")
    
    # Main content
    st.title("FinSight - Annual Report Intelligence")
    st.caption("AI-powered analysis of company annual reports")
    
    # Initialize agent on first load
    if st.session_state.agent is None:
        init_agent()
    
    # Render selected tab
    if tab == "🏥 Health Scores":
        display_health_scores()
    elif tab == "💬 Chat":
        render_chat_tab()
    elif tab == "📊 Metrics":
        display_metrics_table()
    elif tab == "🚨 Red Flags":
        display_redflags()


def render_chat_tab():
    """Render the chat interface."""
    
    # Example questions
    with st.expander("💡 Example Questions"):
        examples = [
            "What is the revenue growth trend?",
            "Compare debt levels across all companies",
            "What are the main risk factors?",
            "Which company has the best profit margin?",
            "Summarize key business highlights"
        ]
        cols = st.columns(2)
        for i, ex in enumerate(examples):
            with cols[i % 2]:
                if st.button(ex, key=f"ex_{i}", use_container_width=True):
                    st.session_state.pending_question = ex
                    st.rerun()
    
    # Chat interface
    st.subheader("💬 Ask Financial Questions")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "reasoned_response" in message:
                rr = message["reasoned_response"]
                with st.expander("🧠 Show Reasoning"):
                    st.markdown(f"**Confidence:** {rr.confidence.upper()}")
                    st.markdown(f"**Companies Queried:** {', '.join(rr.companies_queried) if rr.companies_queried else 'None'}")
                    st.markdown(f"**Chunks Retrieved:** {rr.chunks_retrieved}")
                    if rr.what_was_missing:
                        st.markdown(f"**⚠️ Missing:** {rr.what_was_missing}")
                    st.markdown("**Reasoning Steps:**")
                    for step in rr.reasoning_steps:
                        st.markdown(f"&nbsp;&nbsp;• {step}")
                    if rr.sources:
                        st.markdown("**Sources:**")
                        for src in rr.sources[:3]:
                            page = src.get('page', 'unknown')
                            company = src.get('company', 'unknown')
                            text = src.get('text', '')[:100]
                            st.caption(f"📄 {company} (p.{page}): {text}...")
    
    # Chat input
    if prompt := st.chat_input("Ask about revenue, risks, comparisons..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            if st.session_state.agent and st.session_state.companies_loaded:
                with st.spinner("Analyzing..."):
                    try:
                        # Use ask_with_reasoning for transparency
                        reasoned_response = st.session_state.agent.ask_with_reasoning(prompt)
                        answer = reasoned_response.answer
                        companies = reasoned_response.companies_queried
                        
                        # Add company badges
                        if companies:
                            badges = " ".join([f"`{c}`" for c in companies])
                            answer = f"*Querying: {badges}*\n\n{answer}"
                        
                        st.markdown(answer)
                        
                        # Save to history with reasoning
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": answer,
                            "reasoned_response": reasoned_response
                        })
                        st.session_state.last_reasoned_response = reasoned_response
                    except Exception as e:
                        error_msg = f"❌ Error: {str(e)}"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
            else:
                msg = "⚠️ Please add annual report PDFs to the data/ folder and click Refresh Indexes"
                st.warning(msg)
                st.session_state.messages.append({"role": "assistant", "content": msg})


if __name__ == "__main__":
    main()
