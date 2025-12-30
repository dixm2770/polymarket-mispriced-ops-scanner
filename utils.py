import requests
import json
import logging
from datetime import datetime, timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIG ---
GAMMA_URL = "https://gamma-api.polymarket.com/events"
CLOB_URL = "https://clob.polymarket.com/books"
HEADERS = {"User-Agent": "MispricedOps/Scanner-2.0"}

# --- LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("Scanner")

# --- ROBUST SESSION ---
def get_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session

session = get_session()

# --- HELPERS ---
def utc_now():
    return datetime.now(timezone.utc)

def safe_float(val):
    try:
        return float(val)
    except Exception:
        return 0.0

def parse_iso_date(date_str):
    """Safely parse Polymarket ISO timestamps."""
    try:
        if not date_str:
            return None
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception as e:
        logger.debug(f"Date parse error: {e}")
        return None

# --- API FETCHERS ---
def fetch_events_paginated(limit=500):
    """
    Fetch active Polymarket events ordered by volume.
    Returns a list of raw event objects.
    """
    params = {
        "limit": 100,
        "active": "true",
        "closed": "false",
        "order": "volume",
        "ascending": "false"
    }

    events = []
    offset = 0

    logger.info("Fetching events from Gamma API...")

    while len(events) < limit:
        params["offset"] = offset
        try:
            r = session.get(GAMMA_URL, params=params, timeout=10)
            if r.status_code != 200:
                logger.error(f"Gamma API error {r.status_code}: {r.text}")
                break

            data = r.json()
            if not data:
                break

            events.extend(data)
            offset += 100

            if len(data) < 100:
                break

        except Exception as e:
            logger.error(f"Event fetch failed: {e}")
            break

    logger.info(f"Fetched {len(events)} raw events.")
    return events[:limit]

def fetch_liquidity(token_ids):
    """
    Batch-fetch order books for given token IDs.
    Returns dict keyed by token_id.
    """
    results = {}
    unique_ids = list(set(str(t) for t in token_ids if t))
    chunk_size = 20

    logger.info(f"Fetching liquidity for {len(unique_ids)} tokens...")

    for i in range(0, len(unique_ids), chunk_size):
        chunk = unique_ids[i:i + chunk_size]
        payload = [{"token_id": t} for t in chunk]

        try:
            r = session.post(CLOB_URL, json=payload, timeout=5)
            if r.status_code == 200:
                for item in r.json():
                    results[str(item.get("asset_id"))] = item
            else:
                logger.warning(f"Liquidity fetch warning: {r.status_code}")
        except Exception as e:
            logger.error(f"Liquidity batch failed: {e}")

    return results

# --- LIQUIDITY MATH ---
def calculate_slippage(asks, capital):
    """
    Simulate market buy to determine deployability.

    Returns:
    (fill_pct, avg_entry, slippage, max_liquidity, spread_warning)
    """
    if not asks:
        return 0.0, 0.0, 0.0, 0.0, False

    asks = sorted(asks, key=lambda x: safe_float(x.get("price")))
    best_price = safe_float(asks[0].get("price"))

    # Spread / thin book checks
    if len(asks) < 3:
        return 0.0, 0.0, 0.0, 0.0, True

    next_price = safe_float(asks[1].get("price"))
    if (next_price - best_price) > 0.05:
        return 0.0, 0.0, 0.0, 0.0, True

    spent = 0.0
    shares = 0.0
    max_liq = 0.0

    for level in asks:
        price = safe_float(level.get("price"))
        size = safe_float(level.get("size"))
        if price <= 0 or size <= 0:
            continue

        level_liq = price * size
        max_liq += level_liq

        remaining = capital - spent
        if remaining <= 0:
            break

        if level_liq >= remaining:
            shares += remaining / price
            spent += remaining
        else:
            shares += size
            spent += level_liq

    if shares <= 0:
        return 0.0, 0.0, 0.0, max_liq, False

    avg_entry = spent / shares
    fill_pct = spent / capital
    slippage = avg_entry - best_price

    return fill_pct, avg_entry, slippage, max_liq, False
