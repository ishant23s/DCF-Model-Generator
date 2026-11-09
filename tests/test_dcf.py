"""Hand-checked tests for the DCF maths. Run: python -m pytest tests/ -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dcf_core import Assumptions, compute_dcf, compute_wacc


def base_assumptions():
    return Assumptions(
        revenue_growth=0.10, ebit_margin=0.20, tax_rate=0.25,
        da_pct_revenue=0.03, capex_pct_revenue=0.04, wc_pct_revenue=0.10,
        risk_free_rate=0.07, equity_risk_premium=0.06, beta=1.0,
        pretax_cost_of_debt=0.08, terminal_growth=0.04,
    )


def test_year1_fcff_hand_checked():
    # Base revenue 1000 -> Y1 revenue 1100, EBIT 220, NOPAT 165,
    # D&A 33, capex 44, WC increase = 10% x (1100-1000) = 10
    # FCFF = 165 + 33 - 44 - 10 = 144
    r = compute_dcf(1000, base_assumptions(), wacc=0.10,
                    net_debt=100, shares=100, current_price=15)
    assert abs(r["rows"][0]["revenue"] - 1100) < 1e-9
    assert abs(r["rows"][0]["fcff"] - 144) < 1e-9


def test_terminal_and_per_share():
    r = compute_dcf(1000, base_assumptions(), wacc=0.10,
                    net_debt=100, shares=100, current_price=15)
    fcff5 = r["rows"][-1]["fcff"]
    expected_tv = fcff5 * 1.04 / (0.10 - 0.04)
    assert abs(r["terminal_value"] - expected_tv) < 1e-6
    assert abs(r["enterprise_value"] - (r["pv_fcff_total"] + r["pv_terminal"])) < 1e-9
    assert abs(r["value_per_share"] - (r["equity_value"] / 100)) < 1e-9


def test_wacc_capm():
    a = base_assumptions()
    w = compute_wacc(a, market_value_equity=900, debt=100, tax_rate=0.25)
    ke = 0.07 + 1.0 * 0.06            # 0.13
    kd_at = 0.08 * 0.75               # 0.06
    assert abs(w["cost_of_equity"] - ke) < 1e-12
    assert abs(w["wacc"] - (ke * 0.9 + kd_at * 0.1)) < 1e-12


def test_wacc_must_exceed_terminal_growth():
    try:
        compute_dcf(1000, base_assumptions(), wacc=0.03,
                    net_debt=0, shares=100, current_price=10)
        raise AssertionError("should have raised")
    except ValueError:
        pass
