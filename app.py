"""
DCF Model Generator - free Streamlit app with a dark, card-based UI.

Two modes:
  1. Automatic - type a company name, we fetch its reported annual
     financials free from Yahoo Finance and build the DCF.
  2. Manual - type your own numbers, same DCF Excel out.

Run locally:  streamlit run app.py
Everything is free: no API key, no account, no paid data.
"""

import pandas as pd
import streamlit as st

from dcf_core import (
    Assumptions,
    CompanyData,
    assumptions_from_company,
    compute_dcf,
    compute_wacc,
    fetch_company,
    search_company,
    sensitivity_grid,
)
from excel_builder import build_workbook

st.set_page_config(page_title="DCF Model Generator", page_icon="📊", layout="wide")

# ----------------------------------------------------------------------------
# Aesthetic layer: dark gradient theme, hero banner, cards, gradient buttons
# ----------------------------------------------------------------------------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Sora:wght@600;800&display=swap');

.stApp { background: radial-gradient(1200px 600px at 15% -10%, #123524 0%, transparent 55%),
                 radial-gradient(1000px 500px at 90% -10%, #14284b 0%, transparent 50%),
                 #0b1117; color: #e8eef4; font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-family: 'Sora', sans-serif; }

.hero { background: linear-gradient(120deg, rgba(16,185,129,.18), rgba(59,130,246,.18));
        border: 1px solid rgba(255,255,255,.10); border-radius: 22px;
        padding: 34px 38px 26px 38px; margin-bottom: 10px;
        box-shadow: 0 18px 50px rgba(0,0,0,.45); }
.hero h1 { font-size: 2.7rem; font-weight: 800; margin: 0 0 6px 0; letter-spacing: -0.5px; }
.hero h1 .grad { background: linear-gradient(90deg, #34d399, #60a5fa);
        -webkit-background-clip: text; background-clip: text; color: transparent; }
.hero p { color: #b9c7d4; font-size: 1.05rem; margin: 0; max-width: 760px; }
.badges { margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
.badge { background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.13);
        padding: 5px 12px; border-radius: 999px; font-size: .82rem; color: #dce7f0; }

.card { background: rgba(255,255,255,.045); border: 1px solid rgba(255,255,255,.09);
        border-radius: 18px; padding: 20px 22px; box-shadow: 0 10px 30px rgba(0,0,0,.35); }
.metric-card { background: linear-gradient(160deg, rgba(255,255,255,.07), rgba(255,255,255,.02));
        border: 1px solid rgba(255,255,255,.10); border-radius: 16px; padding: 16px 18px; text-align: left; }
.metric-label { color: #93a5b5; font-size: .78rem; text-transform: uppercase; letter-spacing: .09em; }
.metric-value { font-family: 'Sora', sans-serif; font-size: 1.65rem; font-weight: 800; margin-top: 2px; }
.verdict-up { background: rgba(16,185,129,.16); border: 1px solid rgba(16,185,129,.45); color: #6ee7b7; }
.verdict-down { background: rgba(244,63,94,.14); border: 1px solid rgba(244,63,94,.45); color: #fda4af; }
.verdict { border-radius: 999px; padding: 6px 14px; font-weight: 600; display: inline-block; margin-top: 8px; }

.stButton > button, .stDownloadButton > button {
        background: linear-gradient(90deg, #10b981, #3b82f6); color: white; border: none;
        border-radius: 12px; font-weight: 700; padding: .55rem 1.1rem;
        box-shadow: 0 8px 22px rgba(16,185,129,.28); transition: transform .08s ease, box-shadow .2s ease; }
.stButton > button:hover, .stDownloadButton > button:hover { transform: translateY(-1px); box-shadow: 0 12px 28px rgba(59,130,246,.35); color: white; }
.stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        background: rgba(255,255,255,.05) !important; border-radius: 12px !important; }
div[data-testid="stTabs"] button { font-weight: 600; }
section[data-testid="stSidebar"] { background: #0d151d; }
</style>

<div class="hero">
  <h1>📊 DCF Model <span class="grad">Generator</span></h1>
  <p>Type a company name and download a full discounted-cash-flow model in Excel — with
     <b>live formulas</b>, a WACC build-up and a sensitivity grid. Or switch to Manual and type your own numbers.</p>
  <div class="badges">
    <span class="badge">✨ 100% Free</span>
    <span class="badge">🔑 No API key</span>
    <span class="badge">📈 Live Excel formulas</span>
    <span class="badge">🌍 NSE · BSE · NYSE · NASDAQ</span>
    <span class="badge">🧮 FCFF DCF · 5-year forecast</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)


def metric_card(label: str, value: str) -> str:
    return f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>'


def assumption_editor(a: Assumptions, prefix: str) -> Assumptions:
    """Editable assumption fields (shown in %, stored as fractions)."""
    c1, c2 = st.columns(2)
    with c1:
        growth = st.number_input("Revenue growth (% / year)", value=a.revenue_growth * 100, step=0.5, key=f"{prefix}_g") / 100
        margin = st.number_input("EBIT margin (%)", value=a.ebit_margin * 100, step=0.5, key=f"{prefix}_m") / 100
        tax = st.number_input("Tax rate (%)", value=a.tax_rate * 100, step=0.5, key=f"{prefix}_t") / 100
        da = st.number_input("Depreciation (% of revenue)", value=a.da_pct_revenue * 100, step=0.25, key=f"{prefix}_da") / 100
        capex = st.number_input("Capex (% of revenue)", value=a.capex_pct_revenue * 100, step=0.25, key=f"{prefix}_cx") / 100
        wc = st.number_input("Working capital (% of revenue)", value=a.wc_pct_revenue * 100, step=0.5, key=f"{prefix}_wc") / 100
    with c2:
        rf = st.number_input("Risk-free rate (%)", value=a.risk_free_rate * 100, step=0.1, key=f"{prefix}_rf") / 100
        erp = st.number_input("Equity risk premium (%)", value=a.equity_risk_premium * 100, step=0.25, key=f"{prefix}_erp") / 100
        beta = st.number_input("Beta", value=float(a.beta), step=0.05, key=f"{prefix}_b")
        kd = st.number_input("Pre-tax cost of debt (%)", value=a.pretax_cost_of_debt * 100, step=0.25, key=f"{prefix}_kd") / 100
        tg = st.number_input("Terminal growth (%)", value=a.terminal_growth * 100, step=0.25, key=f"{prefix}_tg") / 100
    return Assumptions(
        revenue_growth=growth, ebit_margin=margin, tax_rate=tax,
        da_pct_revenue=da, capex_pct_revenue=capex, wc_pct_revenue=wc,
        risk_free_rate=rf, equity_risk_premium=erp, beta=beta,
        pretax_cost_of_debt=kd, terminal_growth=tg,
    )


def generate_and_offer_download(data: CompanyData, a: Assumptions):
    mve = data.current_price * data.shares
    w = compute_wacc(a, mve, data.total_debt, a.tax_rate)
    try:
        result = compute_dcf(data.base_revenue, a, w["wacc"], data.net_debt, data.shares, data.current_price)
    except ValueError as e:
        st.error(str(e))
        return
    sens = sensitivity_grid(data.base_revenue, a, w["wacc"], data.net_debt, data.shares, data.current_price)

    upside = result["upside_pct"]
    verdict_cls = "verdict-up" if upside >= 0 else "verdict-down"
    verdict_txt = (f"▲ Model value is {upside*100:+.1f}% vs market price — the market prices this company "
                   f"{'below' if upside >= 0 else 'above'} this model's estimate") if data.current_price else ""

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(metric_card("WACC", f"{w['wacc']*100:.1f}%"), unsafe_allow_html=True)
    c2.markdown(metric_card("Value per share", f"{result['value_per_share']:,.0f}"), unsafe_allow_html=True)
    c3.markdown(metric_card("Current price", f"{data.current_price:,.0f}" if data.current_price else "—"), unsafe_allow_html=True)
    c4.markdown(metric_card("Enterprise value", f"{result['enterprise_value']:,.0f}"), unsafe_allow_html=True)
    if verdict_txt:
        st.markdown(f'<span class="verdict {verdict_cls}">{verdict_txt}</span>', unsafe_allow_html=True)

    fcff_df = pd.DataFrame(
        {"Year": [f"Year {r['year']}" for r in result["rows"]],
         "FCFF": [round(r["fcff"], 1) for r in result["rows"]]}
    ).set_index("Year")
    st.markdown("##### Projected Free Cash Flow to Firm")
    st.bar_chart(fcff_df, color="#34d399")

    buf = build_workbook(data, a, result, w, sens)
    st.download_button(
        "⬇️  Download DCF Excel — live formulas",
        data=buf.getvalue(),
        file_name=f"{data.ticker or 'Manual'}_DCF_Model.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    st.caption("Sheets: About · Inputs · WACC · Forecast & FCFF · Valuation · History · Sensitivity. "
               "Change any yellow input cell in Excel and the valuation updates. "
               "Sensitivity sheet is a snapshot from the moment you generated the file.")


tab_auto, tab_manual = st.tabs(["🔍  Automatic — type a company name", "✍️  Manual — type your own data"])

with tab_auto:
    query = st.text_input("Company name or ticker (try: ITC, DMart, Reliance, TCS, AAPL)", value="")
    if st.button("🔎 Search companies") and query.strip():
        try:
            with st.spinner("Searching…"):
                st.session_state["matches"] = search_company(query.strip())
        except Exception as e:
            st.error(f"Search failed: {e}")
    matches = st.session_state.get("matches", [])
    if matches:
        labels = [f"{m['name']}  ·  {m['symbol']}  ({m['exchange']})" for m in matches]
        pick = st.selectbox("Pick the company", labels)
        symbol = matches[labels.index(pick)]["symbol"]
        if st.button("⚡ Fetch financials & build my model"):
            with st.spinner(f"Fetching {symbol} annual financials from Yahoo Finance…"):
                try:
                    st.session_state["company"] = fetch_company(symbol)
                except Exception as e:
                    st.error(f"Could not fetch {symbol}: {e}")
    data = st.session_state.get("company")
    if data:
        st.markdown(f"### {data.name} · {data.ticker}")
        if data.is_financial:
            st.warning("⚠️ Financial-sector company: an FCFF DCF is generally NOT the right valuation "
                       "method for banks / NBFCs / insurers. The model will still be generated — treat it as illustration only.")
        st.caption(f"Sector: {data.sector or '—'}  ·  Price: {data.current_price:,.2f} {data.currency}  ·  "
                   f"Latest revenue: {data.base_revenue:,.0f} {data.unit_label}  ·  Beta used: {data.beta:.2f}")
        if data.history_years and data.history_revenue:
            hist_df = pd.DataFrame(
                {"Revenue": data.history_revenue}, index=[str(y) for y in data.history_years]
            )
            st.markdown("##### Reported revenue history")
            st.bar_chart(hist_df, color="#60a5fa")
        st.markdown("#### 🎛️ Check / change the assumptions")
        a = assumption_editor(assumptions_from_company(data), "auto")
        generate_and_offer_download(data, a)

with tab_manual:
    st.markdown("#### Company & market inputs")
    name = st.text_input("Company name", value="My Company")
    c1, c2 = st.columns(2)
    with c1:
        base_rev = st.number_input("Latest annual revenue", value=10000.0, step=100.0,
                                   help="Any unit — just use the SAME unit for revenue, debt, cash and share count below.")
        price = st.number_input("Current share price", value=250.0, step=1.0)
        shares = st.number_input("Shares outstanding (same unit count as revenue — e.g. crore if revenue is in ₹ crore)", value=100.0, step=1.0)
    with c2:
        debt = st.number_input("Total debt", value=2000.0, step=100.0)
        cash = st.number_input("Cash & equivalents", value=500.0, step=100.0)
        unit = st.text_input("Unit label (shown in the Excel file)", value="Rs crore")
    manual = CompanyData(
        name=name, ticker="MANUAL", currency="", unit_label=unit,
        current_price=price, shares=shares, total_debt=debt, cash=cash,
        history_years=["Latest"], history_revenue=[base_rev],
        history_ebit=[], history_net_income=[],
    )
    st.markdown("#### 🎛️ Assumptions")
    a = assumption_editor(Assumptions(), "man")
    generate_and_offer_download(manual, a)

st.divider()
st.caption("🎓 Educational tool only — not investment advice. Verify assumptions against the company's actual annual report. "
           "Data: Yahoo Finance (free) · Code: github.com/ishant23s/DCF-Model-Generator · Made by Ishant Saugat")
