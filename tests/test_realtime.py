from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from stock_strategies import data, realtime


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        today = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y%m%d")
        return {"msgArray": [{
            "c": "2330", "d": today, "t": "13:29:58",
            "o": "1000", "h": "1020", "l": "995", "z": "1015", "v": "1,500",
        }]}


def test_realtime_snapshot_normalizes_ohlcv(monkeypatch):
    monkeypatch.setattr(realtime.requests, "get", lambda *a, **k: FakeResponse())
    bars = realtime.get_realtime_bars([{"stock_id": "2330", "market": "上市"}])
    assert bars["2330"]["close"] == 1015
    assert bars["2330"]["volume"] == 1_500_000
    assert bars["2330"]["snapshot_time"] == "13:29:58"


def test_live_bar_replaces_same_day_daily_row(monkeypatch):
    today = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d")
    raw = pd.DataFrame({
        "date": ["2026-09-21", today], "open": [10, 11], "max": [11, 12],
        "min": [9, 10], "close": [10.5, 11.5], "Trading_Volume": [1000, 2000],
    })
    monkeypatch.setattr(data, "fetch_finmind_cached", lambda *a, **k: raw.copy())
    history = data.get_price_history("2330", live_bar={
        "date": today, "open": 20, "high": 22, "low": 19, "close": 21, "volume": 3000,
    })
    assert len(history) == 2
    assert history.iloc[-1]["close"] == 21
    assert history.iloc[-1]["volume"] == 3000
