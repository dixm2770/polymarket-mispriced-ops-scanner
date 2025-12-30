# Project: Polymarket Mispriced Ops Scanner (V2)

## 🎯 The Strategy
We are hunting for **"Free Money"** trades—markets where the outcome seems certain (85-99% odds) but the market hasn't fully priced it in yet.

## 🛡 Filtering & Ranking Logic
1.  **The Date Window:**
    * Market must resolve between **[Today + 1 Day]** and **[Today + 30 Days]**.
    * *Why?* We want near-term liquidity, not funds locked for years.
2.  **The "High Confidence" Band:**
    * We look for ANY outcome trading between **85¢ and 99¢**.
    * *Crucial:* We check BOTH sides. A "No" at 92¢ is just as good as a "Yes".
3.  **Safety Gates (V2 Upgrade):**
    * **Dynamic Tag Filter:** User can toggle exclusion of risky categories (Sports, Memecoins, Tweets).
    * **Spread Check:** If the gap between the cheapest shares is too wide (>5¢), we skip. This avoids low-liquidity traps.
4.  **Liquidity & Ranking:**
    * **Filter:** Check if the user's capital (e.g., $2000) can be filled with < 3% slippage.
    * **Rank:** Sort results by **Potential ROI** (Highest Return) first, then by Liquidity Depth.

## 🛠 Tech Stack
* **Frontend:** Streamlit (Dark Mode, "Trader" aesthetic).
* **Backend:** Python `requests` (Robust error handling & Retries).
* **AI:** OpenAI GPT-4o (Red Team Risk Audit).
