import streamlit as st
import pandas as pd
from src.core.fetcher import fetch_ads
from src.core.extractor import build_offer_matrix
from src.core.classifier import analyze_hooks
from src.core.ai_engine import generate_tactical_brief
from src.core.kaggle_enricher import get_demand_context
from src.db.repository import save_ads, get_all_ads, get_trend_data

st.set_page_config(page_title="AdLens PK", layout="wide")

# Custom UI Design & CSS Styling
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* 4 & 6. Global Typography & Emoji Fallback */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol" !important;
    }

    /* 1. Remove default Streamlit top padding and header padding */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
        padding-top: 0 !important;
    }

    /* 2. Sidebar Dark Theme */
    section[data-testid="stSidebar"] {
        background-color: #0f1117 !important;
    }
    section[data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    section[data-testid="stSidebar"] .stTextInput input {
        background-color: #1e222d !important;
        color: #ffffff !important;
        border: 1px solid #30363d !important;
    }
    section[data-testid="stSidebar"] [data-testid="stMetric"] {
        background-color: #1e222d !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
        padding: 1rem !important;
    }
    section[data-testid="stSidebar"] [data-testid="stMetricLabel"] * {
        color: #9ca3af !important;
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    section[data-testid="stSidebar"] [data-testid="stMetricValue"] * {
        color: #ffffff !important;
        font-size: 1.5rem !important;
        font-weight: 700 !important;
    }

    /* 3. Metric Card Styling (Main Area) */
    .main [data-testid="stMetric"],
    .main [data-testid="metric-container"] {
        background-color: #ffffff !important;
        border-radius: 8px !important;
        padding: 1rem !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.08), 0 1px 2px -1px rgba(0, 0, 0, 0.08) !important;
        border: 1px solid #e5e7eb !important;
    }
    .main [data-testid="stMetricLabel"] *,
    .main [data-testid="metric-container"] label {
        font-size: 0.75rem !important;
        color: #6b7280 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        font-weight: 600 !important;
    }
    .main [data-testid="stMetricValue"] *,
    .main [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        color: #111827 !important;
    }

    /* 5. Tab Labels (Uppercase, letter-spaced, smaller font size, no bold) */
    button[data-baseweb="tab"],
    .stTabs [data-baseweb="tab"],
    [data-testid="stTab"] {
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        font-size: 0.8rem !important;
        font-weight: 400 !important;
    }
    button[data-baseweb="tab"] p,
    .stTabs [data-baseweb="tab"] p,
    [data-testid="stTab"] p {
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        font-size: 0.8rem !important;
        font-weight: 400 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("AdLens PK — Pakistani Digital Ad Intelligence")
st.markdown("Automated market intelligence and creative strategy for local SMEs.")

st.sidebar.header("Analysis Parameters")
niche = st.sidebar.text_input("Industry / Niche", value="E-commerce")
use_mock = st.sidebar.checkbox("Use Local Dataset (Demo Mode)", value=True)

stored_ads = get_all_ads()
st.sidebar.metric("Total Ads in Database", len(stored_ads))

if st.sidebar.button("Generate Intelligence Report", type="primary"):
    with st.spinner("Ingesting Pakistani ad data..."):
        ads = fetch_ads(industry=None, use_mock=use_mock)
        if not use_mock and ads:
            save_ads(ads)
        
    if not ads:
        st.error("No active ads found for this criteria.")
        st.stop()
        
    with st.spinner("Extracting commercial mechanics & classifying hooks..."):
        offer_matrix = build_offer_matrix(ads)
        hook_report = analyze_hooks(ads)
        
    st.success(f"Successfully processed {len(ads)} active campaigns!")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Market Overview", 
        "Pakistan Offer Matrix", 
        "Hook Psychology", 
        "Strategy Playbook",
        "Trend Tracker"
    ])
    
    with tab1:
        st.subheader("High-Level Campaign Metrics")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Ads Evaluated", offer_matrix.total_ads_evaluated)
        col2.metric("COD Adoption Rate", f"{offer_matrix.cod_prevalence_pct}%")
        col3.metric("Dominant Copy Language", hook_report.dominant_language)
        
    with tab2:
        st.subheader("Commercial & Offer Mechanics")
        st.write(f"**Most Common Call-to-Action:** {offer_matrix.most_common_cta}")
        st.write(f"**Free Delivery Prevalence:** {offer_matrix.free_shipping_prevalence_pct}%")
        
        df_offers = pd.DataFrame([r.model_dump() for r in offer_matrix.records])
        st.dataframe(
            df_offers[["page_name", "price_mentioned", "has_cash_on_delivery", "primary_cta"]],
            use_container_width=True
        )
        
    with tab3:
        st.subheader("Creative Hook Breakdown")
        st.write(f"**Dominant Psychological Angle:** {hook_report.dominant_hook_type}")
        
        df_hooks = pd.DataFrame([h.model_dump() for h in hook_report.items])
        st.dataframe(
            df_hooks[["page_name", "raw_hook", "hook_type", "language"]],
            use_container_width=True
        )
        
    with tab4:
        st.subheader("AI-Generated Tactical Brief")
        with st.spinner("Synthesizing creative whitespace..."):
            brief = generate_tactical_brief(niche, hook_report, offer_matrix)
            
        st.markdown(f"**Target Niche:** {brief.target_niche}")
        st.info(f"**Market Whitespace:** {brief.market_whitespace}")
        st.success(f"**Recommended Angle:** {brief.recommended_angle}")
        
        st.markdown("**Suggested Copy Hooks (Ready to Test):**")
        for h in brief.suggested_hooks:
            st.markdown(f"- {h}")
            
        st.markdown(f"**Recommended Offer Structure:** {brief.recommended_offer_structure}")

        st.divider()

        # Format Tactical Creative Brief text file export
        hooks_formatted = "\n".join([f"  - {h}" for h in brief.suggested_hooks])
        brief_text_export = (
            "================================================================================\n"
            "ADLENS PK — TACTICAL CAMPAIGN STRATEGY BRIEF\n"
            "================================================================================\n\n"
            f"TARGET NICHE:\n{brief.target_niche}\n\n"
            f"MARKET WHITESPACE:\n{brief.market_whitespace}\n\n"
            f"RECOMMENDED CREATIVE ANGLE:\n{brief.recommended_angle}\n\n"
            f"SUGGESTED COPY HOOKS:\n{hooks_formatted}\n\n"
            f"RECOMMENDED OFFER STRUCTURE:\n{brief.recommended_offer_structure}\n\n"
            "--------------------------------------------------------------------------------\n"
            "Strategic Campaign Playbook — Generated by AdLens PK\n"
            "================================================================================\n"
        )

        st.download_button(
            label="Download Strategy Playbook (.txt)",
            data=brief_text_export,
            file_name=f"adlens_playbook_{niche.lower().replace(' ', '_')}.txt",
            mime="text/plain",
            use_container_width=True,
        )

    with tab5:
        st.subheader("Longitudinal Ad Intelligence & Market Trends")

        # 3. Market Demand Signal from Kaggle
        demand_signal = get_demand_context(niche if niche else "general")
        st.info(f"**Pakistan Market Demand Signal**\n\n{demand_signal}")

        # Fetch DB data for analysis
        all_db_ads = get_all_ads()
        trend_data = get_trend_data()

        # 4. Metrics Row
        if all_db_ads:
            df_all = pd.DataFrame(all_db_ads)
            total_tracked = len(df_all)
            unique_pages = int(df_all["page_name"].nunique()) if "page_name" in df_all.columns else 0
            if "industry" in df_all.columns and not df_all["industry"].empty:
                most_active_ind = str(df_all["industry"].value_counts().index[0]).title()
            else:
                most_active_ind = "N/A"
        else:
            df_all = pd.DataFrame()
            total_tracked = 0
            unique_pages = 0
            most_active_ind = "N/A"

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Ads Tracked (all time)", total_tracked)
        m2.metric("Unique Pages Seen", unique_pages)
        m3.metric("Most Active Industry", most_active_ind)

        # 5. Warning if only 1 day of data
        distinct_days = len(trend_data) if trend_data else 0
        if distinct_days <= 1:
            st.warning("Trend data builds over time. Run the app daily to see patterns emerge.")

        # 1. Number of ads pulled per day line chart
        st.subheader("Ads Pulled Per Day")
        if trend_data:
            df_trends = pd.DataFrame(trend_data)
            df_trends["date"] = pd.to_datetime(df_trends["date"])
            df_trends = df_trends.sort_values("date")
            df_trends = df_trends.rename(columns={"count": "Ads Pulled"})
            st.line_chart(df_trends.set_index("date")["Ads Pulled"])
        else:
            st.caption("No historical ingestion data available yet.")

        # 2. COD Adoption Percentage Per Day line chart
        st.subheader("COD Adoption Over Time (%)")
        if not df_all.empty and "pulled_at" in df_all.columns and "has_cod" in df_all.columns:
            df_all["date"] = pd.to_datetime(df_all["pulled_at"]).dt.date
            cod_trend = (
                df_all.groupby("date")["has_cod"]
                .agg(lambda x: round((x.sum() / len(x)) * 100, 1))
                .reset_index(name="COD Adoption (%)")
                .sort_values("date")
            )
            st.line_chart(cod_trend.set_index("date")["COD Adoption (%)"])
        else:
            st.caption("No COD trend data available yet.")

