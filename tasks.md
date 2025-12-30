# Implementation Plan

- [x] **Setup:** Dependencies & Environment.
- [x] **Date Logic (`utils.py`):**
    * Implement strict date parsing.
    * Filter: `Now + 1d <= Resolution <= Now + 30d`.
- [x] **API & Safety Logic (`utils.py`):**
    * **Robustness:** Add retries and error logging.
    * **Liquidity:** Fetch order books and calculate weighted average entry.
    * **Spread Check:** Detect if the market is too thin/gappy.
- [x] **Scanner Core (`main.py`):**
    * **Tags:** Implement Sidebar Multi-select for excluding tags.
    * **ROI:** Calculate `(1.00 - RealEntry) / RealEntry`.
    * **Sort:** Rank final list by ROI descending.
- [x] **UI/UX:**
    * **Card Design:** Show ROI, Depth Label, and Tags.
    * **Audit:** Add "Red Team" button for GPT-4o risk analysis.
