"""
DCF Model Generator - core data + valuation logic.

Free data only: Yahoo Finance via yfinance (no API key, no paid service).
All money values are normalised to one unit per company:
  INR companies  -> Rs crore  (raw / 1e7)
  other currency -> millions  (raw / 1e6)
Prices are always per-share in the listing currency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import requests

YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (DCF-Model-Generator)"}


# ----------------------------------------------------------------------------
# Company search: type a name, get ticker matches
# ----------------------------------------------------------------------------

def search_company(query: str, limit: int = 10) -> list[dict]:
    """Return Yahoo Finance search matches for a company name or ticker."""
    resp = requests.get(
        YAHOO_SEARCH_URL,
        params={"q": query, "quotesCount": limit, "newsCount": 0},
        headers=HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    out = []
    for q in resp.json().get("quotes", []):
        if q.get("quoteType") not in ("EQUITY", "ETF"):
            continue
        out.append(
            {
                "symbol": q.get("symbol", ""),
                "name": q.get("longname") or q.get("shortname") or q.get("symbol", ""),
                "exchange": q.get("exchange", ""),
                "type": q.get("quoteType", ""),
            }
        )
    return out


# ----------------------------------------------------------------------------
# Data containers
# ----------------------------------------------------------------------------

@dataclass
class CompanyData:
    name: str
    ticker: str
    currency: str = "INR"
    unit_label: str = "Rs crore"
    unit_divisor: float = 1e7
    sector: str = ""
    is_financial: bool = False
    current_price: float = 0.0
    shares: float = 0.0            # in unit terms (e.g. crore shares)
    total_debt: float = 0.0        # in unit money terms
    cash: float = 0.0              # in unit money terms
    beta: float = 1.0
    history_years: list = field(default_factory=list)     # e.g. ["FY2023", ...] oldest -> newest
    history_revenue: list = field(default_factory=list)
    history_ebit: list = field(default_factory=list)
    history_net_income: list = field(default_factory=list)
    # defaults derived from history (fractions, not %)
    revenue_cagr: float = 0.05
    ebit_margin: float = 0.15
    tax_rate: float = 0.25
    da_pct_revenue: float = 0.03
    capex_pct_revenue: float = 0.04
    wc_pct_revenue: float = 0.10
    interest_pct_debt: float = 0.08   # pre-tax cost of debt proxy

    @property
    def base_revenue(self) -> float:
        vals = [v for v in self.history_revenue if v and v > 0]
        return vals[-1] if vals else 0.0

    @property
    def net_debt(self) -> float:
        return self.total_debt - self.cash


@dataclass
class Assumptions:
    revenue_growth: float = 0.05
    ebit_margin: float = 0.15
    tax_rate: float = 0.25
    da_pct_revenue: float = 0.03
    capex_pct_revenue: float = 0.04
    wc_pct_revenue: float = 0.10
    forecast_years: int = 5
    risk_free_rate: float = 0.071
    equity_risk_premium: float = 0.065
    beta: float = 1.0
    pretax_cost_of_debt: float = 0.08
    terminal_growth: float = 0.04


def default_rates(currency: str) -> tuple[float, float]:
    """(risk-free rate, equity risk premium) defaults by currency."""
    if currency == "INR":
        return 0.071, 0.065
    return 0.043, 0.050


def compute_wacc(a: Assumptions, market_value_equity: float, debt: float, tax_rate: float) -> dict:
    ke = a.risk_free_rate + a.beta * a.equity_risk_premium
    kd_after_tax = a.pretax_cost_of_debt * (1 - tax_rate)
    total = (market_value_equity or 0) + (debt or 0)
    we = (market_value_equity / total) if total > 0 else 1.0
    wd = 1 - we
    wacc = ke * we + kd_after_tax * wd
    return {
        "cost_of_equity": ke,
        "cost_of_debt_after_tax": kd_after_tax,
        "weight_equity": we,
        "weight_debt": wd,
        "wacc": wacc,
    }


def compute_dcf(base_revenue: float, a: Assumptions, wacc: float,
                net_debt: float, shares: float, current_price: float) -> dict:
    """Pure-python FCFF DCF. Mirrors the Excel model formula-for-formula."""
    if wacc <= a.terminal_growth:
        raise ValueError("WACC must be higher than terminal growth, otherwise the "
                         "terminal value is meaningless. Raise WACC or lower terminal growth.")
    rows = []
    prev_rev = base_revenue
    pv_fcff_total = 0.0
    for t in range(1, a.forecast_years + 1):
        rev = prev_rev * (1 + a.revenue_growth)
        ebit = rev * a.ebit_margin
        nopat = ebit * (1 - a.tax_rate)
        da = rev * a.da_pct_revenue
        capex = rev * a.capex_pct_revenue
        delta_wc = a.wc_pct_revenue * (rev - prev_rev)
        fcff = nopat + da - capex - delta_wc
        df = 1 / (1 + wacc) ** t
        pv = fcff * df
        pv_fcff_total += pv
        rows.append({
            "year": t, "revenue": rev, "ebit": ebit, "nopat": nopat,
            "da": da, "capex": capex, "delta_wc": delta_wc,
            "fcff": fcff, "discount_factor": df, "pv_fcff": pv,
        })
        prev_rev = rev
    last = rows[-1]
    terminal_value = last["fcff"] * (1 + a.terminal_growth) / (wacc - a.terminal_growth)
    pv_terminal = terminal_value * last["discount_factor"]
    enterprise_value = pv_fcff_total + pv_terminal
    equity_value = enterprise_value - net_debt
    value_per_share = (equity_value / shares) if shares else 0.0
    upside = ((value_per_share / current_price) - 1) if current_price else 0.0
    return {
        "rows": rows,
        "pv_fcff_total": pv_fcff_total,
        "terminal_value": terminal_value,
        "pv_terminal": pv_terminal,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "value_per_share": value_per_share,
        "upside_pct": upside,
        "wacc": wacc,
    }


def sensitivity_grid(base_revenue: float, a: Assumptions, wacc: float,
                     net_debt: float, shares: float, current_price: float,
                     wacc_steps=(-0.02, -0.01, 0.0, 0.01, 0.02),
                     g_steps=(0.02, 0.03, 0.04, 0.05, 0.06)) -> dict:
    """Value-per-share for WACC x terminal-growth combinations (static snapshot)."""
    grid = {}
    for dw in wacc_steps:
        w = wacc + dw
        row = {}
        for g in g_steps:
            if w <= g:
                row[g] = None
                continue
            a2 = Assumptions(**{**a.__dict__, "terminal_growth": g})
            row[g] = compute_dcf(base_revenue, a2, w, net_debt, shares, current_price)["value_per_share"]
        grid[w] = row
    return {"wacc_values": [wacc + d for d in wacc_steps], "g_values": list(g_steps), "grid": grid}


# ----------------------------------------------------------------------------
# Yahoo Finance fetch (auto mode)
# ----------------------------------------------------------------------------

def _row(df, names):
    """First matching row of a yfinance statement, as a list oldest -> newest."""
    if df is None or getattr(df, "empty", True):
        return []
    for n in names:
        if n in df.index:
            vals = df.loc[n].tolist()
            out = []
            for v in reversed(vals):  # yfinance gives newest first
                try:
                    out.append(float(v) if v is not None and not (isinstance(v, float) and math.isnan(v)) else None)
                except (TypeError, ValueError):
                    out.append(None)
            return out
    return []


def _latest(vals):
    clean = [v for v in vals if v is not None]
    return clean[-1] if clean else 0.0


def fetch_company(ticker: str) -> CompanyData:
    """Fetch statements + quote info for a ticker, e.g. 'ITC.NS' or 'AAPL'."""
    import yfinance as yf

    t = yf.Ticker(ticker)
    info = {}
    try:
        info = t.info or {}
    except Exception:
        info = {}

    currency = info.get("currency") or ("INR" if ticker.upper().endswith((".NS", ".BO")) else "USD")
    divisor, unit_label = (1e7, "Rs crore") if currency == "INR" else (1e6, "$ million")

    fin = t.financials
    cf = t.cashflow
    bs = t.balance_sheet

    years = []
    if fin is not None and not fin.empty:
        years = [f"FY{c.year}" for c in reversed(list(fin.columns))]

    def money(vals):
        return [None if v is None else v / divisor for v in vals]

    revenue = money(_row(fin, ["Total Revenue"]))
    ebit = money(_row(fin, ["EBIT", "Operating Income"]))
    net_income = money(_row(fin, ["Net Income"]))
    tax_prov = _row(fin, ["Tax Provision"])
    pretax = _row(fin, ["Pretax Income"])
    interest = _row(fin, ["Interest Expense"])
    da = money(_row(cf, ["Depreciation And Amortization", "Depreciation", "Depreciation Amortization Depletion"]))
    capex_raw = _row(cf, ["Capital Expenditure"])
    capex = [None if v is None else abs(v) / divisor for v in capex_raw]
    total_debt = _latest(money(_row(bs, ["Total Debt", "Total Non Current Liabilities Net Minority Interest"])))
    cash = _latest(money(_row(bs, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])))

    price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
    if not price:
        try:
            hist = t.history(period="5d")
            if len(hist):
                price = float(hist["Close"].iloc[-1])
        except Exception:
            price = 0.0
    shares_raw = info.get("sharesOutstanding") or 0
    shares = shares_raw / divisor if shares_raw else 0.0
    if not shares:
        bs_shares = _latest(_row(bs, ["Ordinary Shares Number", "Share Issued"]))
        shares = bs_shares / divisor if bs_shares else 0.0

    sector = info.get("sector") or ""
    raw_beta = info.get("beta")
    try:
        raw_beta = float(raw_beta) if raw_beta is not None else None
    except (TypeError, ValueError):
        raw_beta = None
    # Yahoo's beta is a known glitch for some stocks (e.g. negative for ITC).
    # Sanity rule: outside 0.2-2.0, fall back to a plain default the user can edit.
    if raw_beta is None or not (0.2 <= raw_beta <= 2.0):
        beta = 0.7 if currency == "INR" else 1.0
    else:
        beta = raw_beta
    data = CompanyData(
        name=info.get("longName") or info.get("shortName") or ticker,
        ticker=ticker.upper(),
        currency=currency,
        unit_label=unit_label,
        unit_divisor=divisor,
        sector=sector,
        is_financial=("financ" in sector.lower()),
        current_price=float(price or 0),
        shares=float(shares or 0),
        total_debt=float(total_debt or 0),
        cash=float(cash or 0),
        beta=beta,
        history_years=years,
        history_revenue=revenue,
        history_ebit=ebit,
        history_net_income=net_income,
    )

    # ---- derived defaults -------------------------------------------------
    rev_clean = [v for v in revenue if v]
    if len(rev_clean) >= 2 and rev_clean[0] > 0:
        n = len(rev_clean) - 1
        data.revenue_cagr = max(min((rev_clean[-1] / rev_clean[0]) ** (1 / n) - 1, 0.40), -0.10)
    if data.base_revenue and _latest(ebit):
        data.ebit_margin = max(min(_latest(ebit) / data.base_revenue, 0.60), -0.20)
    tp, pt = _latest(tax_prov), _latest(pretax)
    if tp and pt and pt > 0:
        data.tax_rate = max(min(tp / pt, 0.40), 0.0)
    if data.base_revenue:
        # Capex and D&A defaults = average of each year's ratio to that
        # year's revenue (one spike year should not drive the whole model).
        def _avg_ratio(series):
            ratios = [v / r for v, r in zip(series, revenue)
                      if v is not None and r]
            return sum(ratios) / len(ratios) if ratios else 0.0
        if any(v is not None for v in da):
            data.da_pct_revenue = max(_avg_ratio(da), 0.0)
        if any(v is not None for v in capex):
            data.capex_pct_revenue = max(_avg_ratio(capex), 0.0)
    # working capital level as % of revenue, from the latest balance sheet
    ca = _latest(money(_row(bs, ["Current Assets", "Total Current Assets"])))
    cl = _latest(money(_row(bs, ["Current Liabilities", "Total Current Liabilities"])))
    if data.base_revenue and ca and cl:
        wc = (ca - cash) - cl
        data.wc_pct_revenue = max(min(wc / data.base_revenue, 0.60), -0.30)
    ie = _latest(interest)
    if ie and total_debt:
        # interest (converted to unit money) / total debt (unit money)
        data.interest_pct_debt = max(min(abs(ie) / divisor / total_debt, 0.20), 0.01)
    return data


def assumptions_from_company(data: CompanyData) -> Assumptions:
    rf, erp = default_rates(data.currency)
    return Assumptions(
        revenue_growth=round(data.revenue_cagr, 4),
        ebit_margin=round(data.ebit_margin, 4),
        tax_rate=round(data.tax_rate, 4),
        da_pct_revenue=round(data.da_pct_revenue, 4),
        capex_pct_revenue=round(data.capex_pct_revenue, 4),
        wc_pct_revenue=round(data.wc_pct_revenue, 4),
        risk_free_rate=rf,
        equity_risk_premium=erp,
        beta=data.beta,
        pretax_cost_of_debt=round(data.interest_pct_debt, 4),
        terminal_growth=0.04,
    )
