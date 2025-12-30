# Polymarket Mispriced Ops Scanner (V2)

A Streamlit dashboard that scans Polymarket prediction markets to identify high-confidence (85-99%) outcomes resolving in 1-30 days, verifies real deployable liquidity, and ranks opportunities by actual ROI.

## Features

- **Date Window Filter**: Markets must resolve between Today+1 and Today+30 days
- **High Confidence Band**: Finds outcomes trading between 85¢ and 99¢
- **Dynamic Tag Filter**: Exclude risky categories (Sports, Memecoins, Tweet Markets, etc.)
- **Spread Check**: Skips markets with >5¢ gap (low liquidity traps)
- **Liquidity Verification**: Checks if capital can be deployed with <3% slippage
- **ROI Ranking**: Sorted by potential return, then liquidity depth
- **Red Team Audit**: Optional GPT-4o forensic risk analysis

## Tech Stack

- **Frontend**: Streamlit (Dark Mode)
- **Backend**: Python with requests (robust retries)
- **AI**: OpenAI GPT-4o for risk audits

## Installation

```bash
pip install streamlit requests pandas openai
```

## Usage

```bash
streamlit run main.py --server.port 5000
```

## Environment Variables

- `OPENAI_API_KEY` (optional) - For Red Team risk audits
