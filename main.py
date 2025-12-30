import streamlit as st
import pandas as pd
import openai
import os
import json
import logging
from datetime import timedelta, datetime
from utils import (
    fetch_events_paginated,
    fetch_liquidity,
    safe_float,
    utc_now,
    parse_iso_date,
    calculate_slippage
)

# --- PAGE CONFIG ---
st.set_page_config(
    layout="wide",
    page_title="Mispriced Ops Scanner",
    page_icon="🎯"
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    .card {
        border: 1px solid #30363d;
        background-color: #161b22;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 15px;
    }
    .big-stat {
        font-size: 1.6rem;
        font-weight: 700;
        color: #58a6ff;
    }
    .roi-stat {
        font-size: 1.6rem;
        font-weight: 700;
        color: #2ea043;
    }
    .sub-stat {
        font-size: 0.85rem;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .win-tag {
        background-color: #238636;
        color: white;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.9rem;
    }
    .tag-bubble {
        background-color: #1f6feb;
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.75rem;
        margin-right: 5px;
    }
    .title-text {
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 5px;
    }
    a {
        text-decoration: none;
        color: #58a6ff;
    }
    a:hover {
        text-decoration: underline;
    }
</style>
""", unsafe_allow_html=True)

# --- STATE ---
if "data" not in st.session_state:
    st.session_state.data = []
if "view" not in st.session_state:
    st.session_state.view = "DASHBOARD"
if "selected_op" not in st.session_state:
    st.session_state.selected_op = None
if "audit_log" not in st.session_state:
    st.session_state.audit_log = {}
if "all_tags" not in st.session_state:
    st.session_state.all_tags = set([
        "Sports", "Memecoin", "Twitter", "Tweets", "Tweet Markets", "Gaming", 
        "Pop Culture", "Crypto", "Music", "NFTs", "Social", "Politics"
    ])

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎯 Mispriced Ops")
    capital = st.number_input(
        "Your Bet Size ($)",
        min_value=500,
        max_value=50000,
        value=2000,
        step=500
    )

    st.divider()
    st.subheader("🛡 Filter Settings")

    # Dynamic Tag List (Sorted)
    sorted_tags = sorted(list(st.session_state.all_tags))
    
    # Default Excludes
    DEFAULT_EXCLUDES = [
        "Sports",
        "Memecoin",
        "Twitter",
        "Tweets",
        "Tweet Markets",
        "Pop Culture",
        "Gaming",
        "Social"
    ]

    # Pre-select defaults only if they exist in the list
    default_selections = [t for t in DEFAULT_EXCLUDES if t in sorted_tags]

    excluded_tags = st.multiselect(
        "Exclude Categories:",
        options=sorted_tags,
        default=default_selections
    )

    st.divider()

    default_key = os.environ.get("OPENAI_API_KEY", "")
    api_key = st.text_input(
        "OpenAI Key (For Audits)",
        value=default_key,
        type="password"
    )

    st.info("""
**Ranking Logic**
1. Can capital be deployed?
2. Highest ROI first
3. Liquidity depth as tiebreaker
""")

# --- CORE SCANNER ---
@st.cache_data(ttl=60, show_spinner=False)
def run_scanner(capital_usd, forbidden_tags):
    raw_events = fetch_events_paginated(limit=400)
    now = utc_now()
    min_date = now + timedelta(days=1)
    max_date = now + timedelta(days=30)

    candidates = []
    token_ids = []
    found_tags = set()

    # Convert forbidden tags to lowercase for case-insensitive matching
    forbidden_lower = [f.lower() for f in forbidden_tags]

    for e in raw_events:
        # Collect all tags found
        tags = [t.get("label") for t in e.get("tags", [])]
        for t in tags:
            found_tags.add(t)

        # Filter Logic (Case Insensitive)
        # Check if any forbidden tag appears inside the event tags
        is_forbidden = False
        for t in tags:
            t_lower = t.lower()
            for bad in forbidden_lower:
                if bad in t_lower:
                    is_forbidden = True
                    break
            if is_forbidden:
                break
        
        if is_forbidden:
            continue

        end_date = parse_iso_date(e.get("endDate"))
        if not end_date or not (min_date <= end_date <= max_date):
            continue

        days_left = (end_date - now).days
        
        # Format Date (e.g., "Jan 12")
        date_str = end_date.strftime("%b %d")

        markets = e.get("markets", [])
        if not markets:
            continue

        for m in markets:
            try:
                outcomes = m.get("outcomes")
                prices = m.get("outcomePrices")
                token_ids_raw = m.get("clobTokenIds")
                volume_str = m.get("volume", "0") 

                if isinstance(outcomes, str): outcomes = json.loads(outcomes)
                if isinstance(prices, str): prices = json.loads(prices)
                if isinstance(token_ids_raw, str): token_ids_raw = json.loads(token_ids_raw)

                if not outcomes or not prices or not token_ids_raw:
                    continue
                if len(outcomes) != len(prices) or len(prices) != len(token_ids_raw):
                    continue

                best_idx = -1
                for i, p in enumerate(prices):
                    p_val = safe_float(p)
                    if 0.85 <= p_val <= 0.99:
                        best_idx = i
                        break

                if best_idx == -1:
                    continue

                candidates.append({
                    "id": token_ids_raw[best_idx],
                    "title": e["title"],
                    "desc": e.get("description", ""),
                    "tags": tags[:3],
                    "target_outcome": outcomes[best_idx],
                    "price_raw": safe_float(prices[best_idx]),
                    "days": days_left,
                    "date_str": date_str, # New formatted date
                    "slug": e.get("slug"),
                    "volume": safe_float(volume_str), 
                    "end_date_iso": e.get("endDate")
                })
                token_ids.append(token_ids_raw[best_idx])

            except Exception as err:
                logging.error(f"Market parse error: {err}")

    books = fetch_liquidity(token_ids)
    results = []

    for c in candidates:
        book = books.get(str(c["id"]))
        if not book:
            continue

        asks = book.get("asks", [])
        fill_pct, avg_entry, slippage, max_liq, spread_warn = calculate_slippage(
            asks, capital_usd
        )

        if spread_warn:
            continue
        if fill_pct < 0.95:
            continue
        if slippage > 0.03:
            continue
        if not (0.85 <= avg_entry <= 0.99):
            continue

        roi_pct = ((1.0 - avg_entry) / avg_entry) * 100
        profit = (capital_usd / avg_entry) - capital_usd

        c.update({
            "real_entry": avg_entry,
            "slippage": slippage,
            "roi": roi_pct,
            "profit": profit,
            "max_liq": max_liq
        })
        results.append(c)

    results.sort(key=lambda x: (x["roi"], x["max_liq"]), reverse=True)
    return results, found_tags

# --- VIEWS ---
def view_dashboard():
    st.title("🎯 Mispriced Ops Scanner")
    st.caption(f"Scanning for ${capital} bets | Resolving in 1–30 days")

    if st.button("🔎 Scan & Rank Markets", type="primary"):
        with st.spinner("Scanning markets..."):
            data, new_tags = run_scanner(capital, excluded_tags)
            st.session_state.data = data
            # Update dynamic tags for next run
            st.session_state.all_tags.update(new_tags)
            st.rerun()

    if st.session_state.data:
        st.success(f"Found {len(st.session_state.data)} opportunities")

        for i, item in enumerate(st.session_state.data):
            depth_ratio = item["max_liq"] / capital
            depth_label = "Deep" if depth_ratio > 3 else "Moderate"
            tags_html = "".join(
                f"<span class='tag-bubble'>{t}</span>" for t in item["tags"]
            )
            market_url = f"https://polymarket.com/event/{item['slug']}"

            # Format volume
            vol_display = f"${item['volume']:,.0f}" if item['volume'] > 1000 else f"${item['volume']:.0f}"

            st.markdown(f"""
            <div class="card">
                <div style="display:flex; justify-content:space-between;">
                    <div>
                        <div style="color:#8b949e;">#{i+1}</div>
                        <div class="title-text">
                            <a href="{market_url}" target="_blank">{item["title"]} ↗</a>
                        </div>
                        {tags_html}
                    </div>
                    <span class="win-tag">{item["target_outcome"].upper()}</span>
                </div>
                <hr>
                <div style="display:flex; justify-content:space-between;">
                    <div><div class="sub-stat">Entry</div><div class="big-stat">{item["real_entry"]*100:.1f}¢</div></div>
                    <div><div class="sub-stat">ROI</div><div class="roi-stat">+{item["roi"]:.2f}%</div></div>
                    <div><div class="sub-stat">Profit</div><div class="roi-stat">${item["profit"]:.0f}</div></div>
                    <div><div class="sub-stat">Volume</div><div class="big-stat">{vol_display}</div></div>
                    <div><div class="sub-stat">Ends</div><div class="big-stat">{item["date_str"]}</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("Red Team Audit 🛡", key=f"audit_{item['id']}"):
                st.session_state.selected_op = item
                st.session_state.view = "DETAIL"
                st.rerun()

def view_detail():
    op = st.session_state.selected_op
    if st.button("← Back"):
        st.session_state.view = "DASHBOARD"
        st.rerun()

    st.header(op["title"])
    st.markdown(f"**Market Link:** [View on Polymarket](https://polymarket.com/event/{op['slug']})")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Outcome", op['target_outcome'])
    col2.metric("Entry Price", f"{op['real_entry']*100:.2f}¢")
    col3.metric("Est. ROI", f"+{op['roi']:.2f}%")
    col4.metric("Ends On", op['date_str'])

    if op["id"] in st.session_state.audit_log:
        st.markdown("### 🛡 Red Team Report")
        st.markdown(st.session_state.audit_log[op["id"]])
        return

    st.divider()
    st.write("Click below to send this market to the Forensic Auditor AI agent.")
    
    if st.button("Run Forensic Audit (GPT-4o)"):
        if not api_key:
            st.error("OpenAI key required.")
            return

        client = openai.OpenAI(api_key=api_key)
        
        # Prepare Data Block
        market_info = f"""
        MARKET: {op['title']}
        DESCRIPTION: {op['desc']}
        OUTCOME: {op['target_outcome']}
        CURRENT PRICE: {op['real_entry']} (Implied Probability: {op['real_entry']*100:.1f}%)
        RESOLUTION DATE: {op['end_date_iso']} (approx {op['days']} days)
        LIQUIDITY DEPTH: ${op['max_liq']:.2f}
        TOTAL VOLUME: ${op['volume']:.2f}
        POTENTIAL ROI: {op['roi']:.2f}%
        SLIPPAGE ESTIMATE: {op['slippage']*100:.2f}%
        """

        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # THE PROMPT
        system_prompt = f"""
# ROLE
You are a Forensic Auditor and Adversarial Risk Manager specializing in Markets, Politics, and Conflict.
Your job is NOT to find a good bet. Your job is to disqualify bad bets.
You treat every market as a potential "Trap" until the data proves otherwise.

# CONTEXT
- Current Date: {current_date}
- Risk-Free Rate: You must approximate the current "3-Month US Treasury Bill" yield for calculations (e.g., if T-Bills are 4%, use 0.04).

# INPUT DATA
{market_info}

# MISSION
Perform a "Red Team" investigation on the candidates above.
First, determine the Market Type for each candidate:
1. TYPE A (Polling/Elections): Approval Ratings, Special Election Margins.
2. TYPE B (Procedural/Legal): Legislative Votes, Court Rulings, SEC Decisions.
3. TYPE C (Corporate/Data): M&A, Earnings, Central Bank Rates.
4. TYPE D (Geopolitics/War): Ceasefires, Treaties, Territorial Control.

---

# PHASE 1: THE "SOURCE OF TRUTH" AUDIT

### IF TYPE A (POLLING MARKET):
Apply the "Recent-Cycle Accuracy" Standard:
Judge pollsters based on their performance in the LAST General Election cycle.
- TIER 1 (TRUST): Top-rated firms with <2pt error in the last cycle (e.g., AtlasIntel/Verasight in recent eras).
- TIER 2 (VERIFY): Traditional high-volume pollsters (e.g., NYT/Siena, Emerson).
- TIER 3 (REJECT): Any firm that had a >4pt "Historic Miss" in the last major cycle.
- CRITICAL CHECK: If the race is Local/State, REJECT National-only pollsters (they often lack local weighting models).

### IF TYPE B (PROCEDURAL MARKET):
Apply the "Whip Count" Standard:
- REJECT: News articles, op-eds, or "Insider" tweets.
- ACCEPT: Official Government Domains (congress.gov, supremecourt.gov, etc.) or Court Dockets (PACER).
- TRAP CHECK: Ensure "Passed Senate" is not confused with "Signed into Law."

### IF TYPE C (CORPORATE/DATA):
Apply the "Ledger" Standard:
- REJECT: Substack rumors or "Sources close to the matter."
- ACCEPT: SEC EDGAR (8-K/10-Q), Official Central Bank Press Releases, Bureau of Labor Statistics (.gov).

### IF TYPE D (GEOPOLITICS/WAR):
Apply the "Triangulation" Standard (Anti-Propaganda Filter):
- THE UNILATERAL BAN: Never trust a combatant's official statement about their own success or adherence to a truce unless the enemy confirms it.
- Example: "Army A says truce holding" = REJECT (Bias).
- Example: "Army A and Army B issue joint start time" = ACCEPT (Bilateral).
- TRUSTED NEUTRALS: If bilateral confirmation is missing, accept only on-ground verification from:
- IAEA (Nuclear), UN Security Council (Resolutions), Red Cross/Crescent (Humanitarian Access).
- TRAP CHECK: Watch for "Ceasefire Agreed" vs "Ceasefire in Effect." (Agreements are easy; "in effect" markets are traps because one bullet voids the bet).

---

# PHASE 2: THE "NEGATIVE SEARCH" (The Black Swan Hunt)
Do not search for confirmation. Search for the failure mode.
Run these queries based on the market type:

- Type A/B/C: "[Candidate/Bill]" delay OR lawsuit OR "blocked by"
- Type D (War): "[Location]" "violations" OR "skirmish" OR "fighting reported" -official
- Note: The "-official" tag helps find independent reports contradicting government narratives.

- Immediate Kill Rule: If any credible report from the last 24h mentions a "TRO" (Restraining Order), "Indefinite Recess," or "Sporadic Clashes" (for war), REJECT.

---

# PHASE 3: EXECUTION MATH (Python)
(Note: You are the AI, perform the mental check of this logic)
Use the user's entry price of {op['real_entry']} and {op['days']} days to resolution.
Compare against a Risk Free Rate of ~4.5%.

# OUTPUT FORMAT
Provide your response in Markdown.
1. **Classification:** (Type A/B/C/D)
2. **The Verdict:** (KILL / WARNING / APPROVED)
3. **Risk Analysis:** (Bullet points on specific failure modes found)
4. **Execution Check:** (Does the yield beat the 4.5% risk free rate + premium?)
"""

        with st.spinner("Forensic Auditor is analyzing..."):
            try:
                res = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": system_prompt}]
                )
                st.session_state.audit_log[op["id"]] = res.choices[0].message.content
                st.rerun()
            except Exception as e:
                st.error(f"Audit failed: {e}")

# --- ROUTER ---
if st.session_state.view == "DASHBOARD":
    view_dashboard()
else:
    view_detail()
