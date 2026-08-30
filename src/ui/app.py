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

    /* Global Typography & Dark Theme */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol" !important;
        background-color: #0f1117 !important;
        color: #ffffff !important;
    }

    /* Remove default Streamlit top padding and header */
    .block-container {
        padding-top: 1.25rem !important;
        padding-bottom: 3rem !important;
        max-width: 100% !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
        padding-top: 0 !important;
    }

    /* Sidebar Dark Theme (#1a1d27) */
    section[data-testid="stSidebar"] {
        background-color: #1a1d27 !important;
        border-right: 1px solid #2d3148 !important;
    }
    section[data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] {
        background-color: #1e2130 !important;
        border: 1px solid #2d3148 !important;
        border-radius: 8px !important;
        color: #ffffff !important;
    }
    section[data-testid="stSidebar"] .stTextInput input {
        background-color: #1e2130 !important;
        color: #ffffff !important;
        border: 1px solid #2d3148 !important;
        border-radius: 8px !important;
    }
    section[data-testid="stSidebar"] .stCheckbox span {
        color: #ffffff !important;
    }

    /* Primary Action Button (#e63946) */
    button[kind="primary"] {
        background-color: #e63946 !important;
        border: none !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.2rem !important;
        transition: all 0.2s ease !important;
    }
    button[kind="primary"]:hover {
        background-color: #d62828 !important;
        box-shadow: 0 4px 12px rgba(230, 57, 70, 0.35) !important;
    }

    /* Tab Labels Styling */
    button[data-baseweb="tab"],
    .stTabs [data-baseweb="tab"],
    [data-testid="stTab"] {
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        color: #9ca3af !important;
        background-color: transparent !important;
        border: none !important;
        padding: 0.75rem 1.25rem !important;
    }
    button[data-baseweb="tab"][aria-selected="true"],
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #ffffff !important;
        border-bottom: 2px solid #e63946 !important;
        font-weight: 700 !important;
    }
    button[data-baseweb="tab"] p,
    .stTabs [data-baseweb="tab"] p,
    [data-testid="stTab"] p {
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        font-size: 0.82rem !important;
    }

    /* Dataframe Container */
    [data-testid="stDataFrame"] {
        border: 1px solid #2d3148 !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_metric_card(label: str, value: str | int | float) -> str:
    """Renders a styled HTML metric card with left accent border."""
    return f"""
    <div style="
        background-color: #1e2130;
        border-radius: 10px;
        padding: 1.5rem;
        border-left: 3px solid #e63946;
        border-top: 1px solid #2d3148;
        border-right: 1px solid #2d3148;
        border-bottom: 1px solid #2d3148;
        margin-bottom: 1rem;
    ">
        <div style="font-size: 0.75rem; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.35rem;">
            {label}
        </div>
        <div style="font-size: 1.75rem; font-weight: 700; color: #ffffff; line-height: 1.2;">
            {value}
        </div>
    </div>
    """


# Header Banner
st.markdown(
    """
    <div style="
        background-color: #1e2130;
        border-bottom: 3px solid #e63946;
        border-radius: 10px 10px 0 0;
        padding: 1.5rem 2rem;
        margin-bottom: 2rem;
        border-top: 1px solid #2d3148;
        border-left: 1px solid #2d3148;
        border-right: 1px solid #2d3148;
    ">
        <div style="display: flex; align-items: baseline; gap: 0.85rem; flex-wrap: wrap;">
            <span style="font-size: 1.85rem; font-weight: 800; color: #ffffff; letter-spacing: -0.02em;">
                AdLens PK
            </span>
            <span style="font-size: 1.05rem; font-weight: 500; color: #9ca3af;">
                Pakistani Digital Ad Intelligence Engine
            </span>
        </div>
        <div style="font-size: 0.85rem; color: #9ca3af; margin-top: 0.35rem;">
            Automated market intelligence and creative strategy for local SMEs & brands.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Sidebar Configuration
st.sidebar.markdown(
    """
    <div style="font-size: 1.1rem; font-weight: 700; color: #ffffff; margin-bottom: 1rem; border-left: 3px solid #e63946; padding-left: 0.6rem;">
        Analysis Parameters
    </div>
    """,
    unsafe_allow_html=True,
)

industry_options = [
    "Fashion",
    "Electronics",
    "Food & Grocery",
    "Health & Beauty",
    "Real Estate",
    "Education",
    "Home & Living",
    "Kids & Baby",
    "General",
]
selected_industry = st.sidebar.selectbox("Industry / Niche", options=industry_options)

if selected_industry == "General":
    custom_niche = st.sidebar.text_input("Custom Niche", placeholder="Type a custom niche...")
    niche = custom_niche.strip() if custom_niche and custom_niche.strip() else "General"
else:
    niche = selected_industry

use_mock = st.sidebar.checkbox("Use Local Dataset (Demo Mode)", value=True)

# Thin red horizontal divider
st.sidebar.markdown(
    "<hr style='border: 0; height: 1px; background-color: #e63946; margin: 1.5rem 0;'>",
    unsafe_allow_html=True,
)

stored_ads = get_all_ads()
st.sidebar.markdown(
    render_metric_card("Total Ads in Database", len(stored_ads)),
    unsafe_allow_html=True,
)

if st.sidebar.button("Generate Intelligence Report", type="primary"):
    with st.spinner("Ingesting Pakistani ad data..."):
        ads = fetch_ads(industry=niche, use_mock=use_mock)
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
        st.markdown("<div style='font-size: 1.25rem; font-weight: 700; color: #ffffff; margin-bottom: 1.2rem;'>High-Level Campaign Metrics</div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(render_metric_card("Total Ads Evaluated", offer_matrix.total_ads_evaluated), unsafe_allow_html=True)
        with col2:
            st.markdown(render_metric_card("COD Adoption Rate", f"{offer_matrix.cod_prevalence_pct}%"), unsafe_allow_html=True)
        with col3:
            st.markdown(render_metric_card("Dominant Copy Language", hook_report.dominant_language), unsafe_allow_html=True)
        
    with tab2:
        st.markdown("<div style='font-size: 1.25rem; font-weight: 700; color: #ffffff; margin-bottom: 1.2rem;'>Commercial & Offer Mechanics</div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(render_metric_card("Most Common Call-to-Action", offer_matrix.most_common_cta), unsafe_allow_html=True)
        with col2:
            st.markdown(render_metric_card("Free Delivery Prevalence", f"{offer_matrix.free_shipping_prevalence_pct}%"), unsafe_allow_html=True)
        
        df_offers = pd.DataFrame([r.model_dump() for r in offer_matrix.records])
        st.dataframe(
            df_offers[["page_name", "price_mentioned", "has_cash_on_delivery", "primary_cta"]],
            use_container_width=True
        )
        
    with tab3:
        st.markdown("<div style='font-size: 1.25rem; font-weight: 700; color: #ffffff; margin-bottom: 1.2rem;'>Creative Hook Breakdown</div>", unsafe_allow_html=True)
        
        st.markdown(render_metric_card("Dominant Psychological Angle", hook_report.dominant_hook_type), unsafe_allow_html=True)
        
        df_hooks = pd.DataFrame([h.model_dump() for h in hook_report.items])
        st.dataframe(
            df_hooks[["page_name", "raw_hook", "hook_type", "language"]],
            use_container_width=True
        )
        
    with tab4:
        st.markdown("<div style='font-size: 1.25rem; font-weight: 700; color: #ffffff; margin-bottom: 1.2rem;'>AI-Generated Tactical Brief</div>", unsafe_allow_html=True)
        with st.spinner("Synthesizing creative whitespace..."):
            brief = generate_tactical_brief(niche, hook_report, offer_matrix)
            
        st.markdown(
            f"""
            <div style="background-color: #1e2130; border: 1px solid #2d3148; border-left: 3px solid #e63946; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem;">
                <div style="margin-bottom: 0.85rem;"><strong style="color: #ffffff;">🎯 Target Niche:</strong> <span style="color: #9ca3af;">{brief.target_niche}</span></div>
                <div style="margin-bottom: 0.85rem;"><strong style="color: #ffffff;">🔍 Market Whitespace:</strong> <span style="color: #9ca3af;">{brief.market_whitespace}</span></div>
                <div style="margin-bottom: 0.85rem;"><strong style="color: #ffffff;">🧠 Recommended Angle:</strong> <span style="color: #ffffff; font-weight: 600;">{brief.recommended_angle}</span></div>
                <div style="margin-bottom: 0.85rem;"><strong style="color: #ffffff;">📦 Recommended Offer Structure:</strong> <span style="color: #9ca3af;">{brief.recommended_offer_structure}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        st.markdown("<div style='font-size: 1.05rem; font-weight: 600; color: #ffffff; margin: 1rem 0 0.5rem 0;'>✍️ Suggested Copy Hooks (Ready to Test):</div>", unsafe_allow_html=True)
        for h in brief.suggested_hooks:
            st.markdown(f"- {h}")
            
        st.markdown("<hr style='border: 0; height: 1px; background-color: #2d3148; margin: 1.5rem 0;'>", unsafe_allow_html=True)

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
        st.markdown("<div style='font-size: 1.25rem; font-weight: 700; color: #ffffff; margin-bottom: 1.2rem;'>Longitudinal Ad Intelligence & Market Trends</div>", unsafe_allow_html=True)

        # Market Demand Signal from Kaggle
        demand_signal = get_demand_context(niche if niche else "general")
        st.info(f"**Pakistan Market Demand Signal**\n\n{demand_signal}")

        # Fetch DB data for analysis
        all_db_ads = get_all_ads()
        trend_data = get_trend_data()

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
        with m1:
            st.markdown(render_metric_card("Total Ads Tracked (all time)", total_tracked), unsafe_allow_html=True)
        with m2:
            st.markdown(render_metric_card("Unique Pages Seen", unique_pages), unsafe_allow_html=True)
        with m3:
            st.markdown(render_metric_card("Most Active Industry", most_active_ind), unsafe_allow_html=True)

        distinct_days = len(trend_data) if trend_data else 0
        if distinct_days <= 1:
            st.warning("Trend data builds over time. Run the app daily to see patterns emerge.")

        # Line Chart 1: Number of ads pulled per day
        st.markdown("<div style='font-size: 1.1rem; font-weight: 600; color: #ffffff; margin: 1.5rem 0 0.8rem 0;'>Ads Pulled Per Day</div>", unsafe_allow_html=True)
        if trend_data:
            df_trends = pd.DataFrame(trend_data)
            df_trends["date"] = pd.to_datetime(df_trends["date"])
            df_trends = df_trends.sort_values("date")
            df_trends = df_trends.rename(columns={"count": "Ads Pulled"})
            st.line_chart(df_trends.set_index("date")["Ads Pulled"])
        else:
            st.caption("No historical ingestion data available yet.")

        # Line Chart 2: COD Adoption Percentage Per Day
        st.markdown("<div style='font-size: 1.1rem; font-weight: 600; color: #ffffff; margin: 1.5rem 0 0.8rem 0;'>COD Adoption Over Time (%)</div>", unsafe_allow_html=True)
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
