# Polymarket Mispriced Ops Scanner (V2)

## Overview
A Streamlit dashboard that scans Polymarket prediction markets to identify high-confidence (85-99%) outcomes resolving in 1-30 days, verifies real deployable liquidity, and ranks opportunities by actual ROI.

## Strategy
Hunt for "Free Money" trades—markets where the outcome seems certain (85-99% odds) but the market hasn't fully priced it in yet.

## Key Features
- **Date Window Filter**: Markets must resolve between Today+1 and Today+30 days
- **High Confidence Band**: Finds outcomes trading between 85¢ and 99¢
- **Dynamic Tag Filter**: Exclude risky categories (Sports, Memecoins, etc.)
- **Spread Check**: Skips markets with >5¢ gap (low liquidity traps)
- **Liquidity Verification**: Checks if capital can be deployed with <3% slippage
- **ROI Ranking**: Sorted by potential return, then liquidity depth
- **Red Team Audit**: Optional GPT-4o risk analysis (requires OpenAI API key)

## Tech Stack
- **Frontend**: Streamlit (Dark Mode)
- **Backend**: Python with requests (robust retries)
- **AI**: OpenAI GPT-4o for risk audits

## Files
- `main.py` - Streamlit dashboard application
- `utils.py` - API fetchers, liquidity math, helpers
- `project.md` - Project documentation
- `tasks.md` - Implementation checklist

## Running
The app runs via: `streamlit run main.py --server.port 5000`

## Environment Variables
- `OPENAI_API_KEY` (optional) - For Red Team risk audits
