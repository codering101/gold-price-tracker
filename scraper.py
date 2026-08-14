import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import os
from datetime import datetime

DAILY_SAVE_PATH = "gold_prices_bangalore.csv"   # one row per day, for the chart
LIVE_SAVE_PATH = "gold_prices_live.csv"         # one row per scrape, for "current price"
URL = "https://www.goodreturns.in/gold-rates/bangalore.html"

def clean_price(raw):
    match = re.match(r"₹?([\d,]+)\(([+-]?\d+)\)", raw)
    if not match:
        return None, None
    price = float(match.group(1).replace(",", ""))
    change = float(match.group(2))
    return price, change

def update_gold_data():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(URL, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")

    if len(tables) < 2:
        raise RuntimeError("Expected tables not found — site structure may have changed.")

    # ---------- LIVE snapshot (today's per-gram table, includes 18K) ----------
    today_table = tables[0]
    today_rows = today_table.find_all("tr")
    today_header = [c.get_text(strip=True) for c in today_rows[0].find_all(["td", "th"])]
    gram_1_row = [c.get_text(strip=True) for c in today_rows[1].find_all(["td", "th"])]

    snapshot = {"timestamp": datetime.now().isoformat(timespec="seconds")}
    for label, raw in zip(today_header[1:], gram_1_row[1:]):
        price, change = clean_price(raw)
        key = label.lower()
        snapshot[key] = price
        snapshot[key + "_change"] = change

    df_snapshot = pd.DataFrame([snapshot])
    if os.path.exists(LIVE_SAVE_PATH):
        df_snapshot.to_csv(LIVE_SAVE_PATH, mode="a", header=False, index=False)
    else:
        df_snapshot.to_csv(LIVE_SAVE_PATH, mode="w", header=True, index=False)

    print(f"[OK] Live snapshot saved: {snapshot}")

    # ---------- Daily history (for the chart) ----------
    history_table = tables[1]
    history_rows = history_table.find_all("tr")

    history_data = []
    for row in history_rows[1:]:
        cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        date = cols[0]
        rate_24k, chg_24k = clean_price(cols[1])
        rate_22k, chg_22k = clean_price(cols[2])
        if rate_24k is None or rate_22k is None:
            continue
        history_data.append({
            "date": date, "24k": rate_24k, "24k_change": chg_24k,
            "22k": rate_22k, "22k_change": chg_22k
        })

    if not history_data:
        raise RuntimeError("No rows parsed — check table structure.")

    df_new = pd.DataFrame(history_data)
    df_new["date"] = pd.to_datetime(df_new["date"], format="%b %d, %Y")
    df_new = df_new.sort_values("date").reset_index(drop=True)

    if os.path.exists(DAILY_SAVE_PATH):
        df_existing = pd.read_csv(DAILY_SAVE_PATH, parse_dates=["date"])
        df_combined = pd.concat([df_existing, df_new]).drop_duplicates(subset="date", keep="last")
        df_combined = df_combined.sort_values("date").reset_index(drop=True)
    else:
        df_combined = df_new

    df_combined.to_csv(DAILY_SAVE_PATH, index=False)
    print(f"[OK] {datetime.now()} — Daily history updated. {len(df_combined)} total rows.")

if __name__ == "__main__":
    update_gold_data()
