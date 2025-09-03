# AIFunder – Portfolio Tracker

Desktop portfolio tracker built with Python/Tkinter. It helps you manage a stock list, track profit/loss over time, and visualize performance. It also includes an optional per‑stock AI assistant that can summarize how a ticker relates to your portfolio strategy.

## Key Features
- Portfolio table: rows for ticker, allocation %, shares, purchase/current price, P/L, dates.
- Live updates: fetches current prices and computes totals; hourly auto‑update plus manual Update button.
- Smooth spinner: animated indicator while updates are running.
- P/L plots: overall portfolio P/L over time, and per‑stock P/L plots.
- Per‑stock AI: “?” button in each per‑stock plot opens an AI window with a saved prompt and last answer; “Ask AI” refreshes the analysis.
- Strategy notes: “?” button next to Total Investment opens a description editor for your portfolio strategy; saved to JSON.
- Persistent data: saves configuration to JSON and logs to CSV; creates a `.bak` backup of the JSON on every save.

## Files & Data
- `portfolio_config.json`: saved configuration (investment, tickers, allocations, purchase data, optional `company_names`, `description`, optional AI data: `openai_api_key`, `ai_prompts`, `ai_answers`).
  - Backup: `portfolio_config.json.bak` is written before any change.
- `portfolio_log.csv`: per‑stock snapshots used by per‑stock plots.
- `portfolio_totals_log.csv`: total portfolio P/L and value over time for the overall plot.

## Getting Started
Prerequisites
- Python 3.10+
- Packages: `pip install requests matplotlib schedule`

Run
- `python aifunder.py`

Price Data
- The app fetches quotes using providers in `data_fetcher.py` (Finnhub, Alpha Vantage by default). You may need API keys:
  - Finnhub: https://finnhub.io/register
  - Alpha Vantage: https://www.alphavantage.co/support/#api-key
  - Set keys in `data_fetcher.py` (look for `finnhub_key` and `alpha_vantage_key`).

AI Assistant (optional)
- In any per‑stock plot, click “?” to open the AI window.
- Add your OpenAI API key to `portfolio_config.json` under `"openai_api_key"` (the key is stored locally and not committed).
- Enter a prompt and click “Ask AI”. The last answer is saved in the same JSON.

## Basic Workflow
1) Launch the app and set Total Investment.
2) Add stock rows with allocation %, ticker, shares and purchase price/date (as needed).
3) Click Update to fetch prices; totals are logged and displayed. Hourly updates run automatically.
4) Use Plot P/L for an overall trend; click a ticker button to open its per‑stock plot.
5) In the per‑stock plot, use “?” to open the AI window (optional), and “Ask AI”.
6) Use the “?” next to Total Investment to save a portfolio strategy description.

## Notes
- JSON backups (`.bak`) are created automatically before saving.
- `.gitignore` excludes `*.csv`, `*.json`, and `*.bak` to keep local data private.
- Company names are cached and saved to reduce API calls.

## License
MIT License — see the LICENSE file for full text.
