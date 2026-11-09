# DCF Model Generator 📊

**Type a company name → get a full DCF valuation model as an Excel file with live formulas. Free forever — no API key, no account, no paid data.**

Built for students, beginner analysts and anyone learning valuation: instead of a black-box "fair value" number, you get the actual model — Inputs, WACC, Forecast & FCFF, Valuation and Sensitivity sheets — so you can change any assumption and watch the value update, exactly like a real analyst's workbook.

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Data: Yahoo Finance](https://img.shields.io/badge/Data-Yahoo%20Finance%20(free)-purple.svg)

## ▶️ Try it live — no sign-up

**[dcf-model-generator.streamlit.app](https://dcf-model-generator.streamlit.app/)** — type a company name (try *ITC*, *TCS* or *DMart*), check the assumptions, download your Excel model.

## Two modes

### 1. 🔍 Automatic — type a company name
Search any listed company (NSE/BSE, NYSE, NASDAQ…), pick the match, and the app pulls its latest reported annual financials — revenue, EBIT, tax, depreciation, capex, debt, cash — plus share price, shares outstanding and beta, **free from Yahoo Finance** (which republishes the company's annual-report financials in structured form).

Smart defaults, all editable before you download:
- **Revenue growth** = historical revenue CAGR
- **EBIT margin** = latest actual margin
- **Tax rate** = latest effective tax rate
- **Capex / depreciation / working capital** = latest actuals as % of revenue
- **WACC** = CAPM (risk-free rate + beta × equity risk premium) blended with after-tax cost of debt
- **Terminal growth** = 4%

### 2. ✍️ Manual — type your own data
No company lookup. Type revenue, margins, debt, shares and your assumptions, and get the same Excel model. Perfect for unlisted companies, case studies and classroom exercises.

## The Excel file you get

| Sheet | What's in it |
|---|---|
| **About** | How to use the file, where the numbers came from, disclaimer |
| **Inputs** | Company data + every operating assumption (yellow cells — change these) |
| **WACC** | Cost of equity (CAPM), after-tax cost of debt, capital weights → WACC, all formulas |
| **Forecast & FCFF** | 5-year forecast: Revenue → EBIT → NOPAT → +Depreciation → −Capex → −Working capital → FCFF, discounted |
| **Valuation** | PV of FCFF + PV of Terminal Value → Enterprise Value → Equity Value → **Value per share** vs current price |
| **History** | The reported annual financials the model was built from |
| **Sensitivity** | Value per share across WACC × terminal-growth combinations |

Every number in the model sheets is a **live Excel formula** — this is a working model, not a screenshot of one.

## Run it yourself (2 minutes, free)

```bash
git clone https://github.com/ishant23s/DCF-Model-Generator.git
cd DCF-Model-Generator
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

**Hosting:** this app runs free on [Streamlit Community Cloud](https://streamlit.io/cloud) — the live version linked above is deployed from this repo (connect repo → pick `app.py` → Deploy).

## Project structure

```
app.py             Streamlit UI (search / manual inputs / download)
dcf_core.py        Company search, Yahoo Finance fetch, WACC + DCF maths
excel_builder.py   Builds the live-formula Excel workbook (openpyxl)
tests/             Hand-checked unit tests for the DCF maths
examples/          A sample generated model (ITC)
```

## Run the tests

```bash
pip install pytest
python -m pytest tests/ -q
```

## ⚠️ Please read

- **Banks, NBFCs and insurers:** an FCFF DCF is generally **not** the right way to value financial firms (debt is their raw material). The app warns you and still generates the file — treat that output as illustration only.
- **Not investment advice.** This is an educational tool. A DCF is only as good as its assumptions — verify them against the company's actual annual report before using the output for any decision.
- Yahoo Finance data can occasionally be incomplete for small companies; if a field is missing, the app falls back to a sensible default, and you can override every assumption before downloading.

## Why I built this

I'm an MBA Finance student doing a 21-day analyst challenge — building DCF models by hand in Excel for DMart, ITC and TCS. This tool automates the boring 80% (finding the data, laying out the workbook) so the interesting 20% — judging the assumptions — gets the time.

## License

[MIT](LICENSE) © Ishant Saugat
