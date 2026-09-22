"""TWSE/TPEx public realtime snapshot adapter.

The website uses this only for an explicitly requested intraday analysis.  The
scheduled/Telegram path continues to use FinMind's official daily rows.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import requests


SNAPSHOT_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"


def _number(value) -> float | None:
    try:
        text = str(value).replace(",", "").strip()
        if not text or text == "-":
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _channels(row: dict) -> list[str]:
    sid = str(row["stock_id"])
    market = str(row.get("market", ""))
    if market == "上市":
        return [f"tse_{sid}.tw"]
    if market == "上櫃":
        return [f"otc_{sid}.tw"]
    # Google Sheet watchlists do not necessarily contain the exchange.
    return [f"tse_{sid}.tw", f"otc_{sid}.tw"]


def get_realtime_bars(rows: list[dict], timeout: int = 20) -> dict[str, dict]:
    """Return today's provisional OHLCV rows keyed by stock id.

    Volume from the exchange snapshot is quoted in lots, while FinMind daily
    history uses shares, so it is multiplied by 1,000 before being appended.
    """
    if not rows:
        return {}
    channels = [channel for row in rows for channel in _channels(row)]
    response = requests.get(
        SNAPSHOT_URL,
        params={"ex_ch": "|".join(channels), "json": "1", "delay": "0"},
        headers={"User-Agent": "Mozilla/5.0 stock-strategies-only/3.3"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    messages = payload.get("msgArray", [])
    if not isinstance(messages, list):
        raise ValueError("交易所即時行情格式異常")

    today = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y%m%d")
    bars: dict[str, dict] = {}
    for item in messages:
        sid = str(item.get("c", "")).strip()
        date = str(item.get("d", "")).strip()
        open_, high, low = (_number(item.get(k)) for k in ("o", "h", "l"))
        close = _number(item.get("z"))
        volume_lots = _number(item.get("v"))
        if not sid or date != today or None in (open_, high, low, close, volume_lots):
            continue
        if min(open_, high, low, close) <= 0 or volume_lots < 0:
            continue
        bars[sid] = {
            "date": datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume_lots * 1000,
            "snapshot_time": str(item.get("t", "")).strip(),
        }
    return bars
