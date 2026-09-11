"""Latest official TWSE/TPEx turnover ranking for ordinary shares."""
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
import requests

SOURCES = [
    ('上市', 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL',
     'Code', 'Name', 'TradeVolume', 'TradeValue', 'ClosingPrice'),
    ('上櫃', 'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes',
     'SecuritiesCompanyCode', 'CompanyName', 'TradingShares', 'TransactionAmount', 'Close'),
]

def number(value):
    try:
        return float(str(value).replace(',', '').strip())
    except (ValueError, TypeError):
        return 0.0

def normalize(rows, source):
    market, _, code, name, volume, amount, close = source
    result = []
    for row in rows:
        sid = str(row.get(code, '')).strip()
        if not re.fullmatch(r'[1-9][0-9]{3}', sid):
            continue
        shares, turnover, price = number(row.get(volume)), number(row.get(amount)), number(row.get(close))
        if shares < 1_500_000 or price <= 0:
            continue
        raw_date = str(row.get('Date', '')).strip()
        if not re.fullmatch(r'\d{7}', raw_date):
            raise ValueError('成交資料日期格式異常')
        date = datetime.strptime(str(int(raw_date[:3])+1911)+raw_date[3:], '%Y%m%d').date()
        age = (datetime.now(ZoneInfo('Asia/Taipei')).date()-date).days
        if age < 0 or age > 14:
            raise ValueError('成交資料已過期，請稍後重試')
        result.append(dict(stock_id=sid, name=row[name].strip(), enabled=True,
                           market=market, turnover=turnover, volume=shares, price=price,
                           date=date.isoformat()))
    return result

def _load_active_stocks():
    def fetch(source):
        for attempt in range(3):
            try:
                response = requests.get(
                    source[1],
                    timeout=20,
                    headers={"User-Agent": "Mozilla/5.0 stock-strategies-only/3.3"},
                )
                response.raise_for_status()
                rows = response.json()
                if not isinstance(rows, list) or not rows:
                    raise ValueError('empty data')
                return normalize(rows, source)
            except Exception:
                if attempt < 2:
                    time.sleep(2 ** attempt)
        return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        batches = list(pool.map(fetch, SOURCES))
    failed = [source[0] for source, batch in zip(SOURCES, batches) if not batch]
    batches = [batch for batch in batches if batch]
    if not batches:
        raise ValueError('上市與上櫃成交資料均讀取失敗，請稍後重試')
    if failed:
        print(f"  注意：{'、'.join(failed)}成交資料暫時無法取得，本次使用其餘市場掃描")
    market_dates = {
        source[0]: sorted({r['date'] for r in batch}, reverse=True)[0]
        for source, batch in zip(SOURCES, batches)
        if batch
    }
    if len(set(market_dates.values())) > 1:
        details = '、'.join(f'{market} {date}' for market, date in market_dates.items())
        print(f'  注意：各市場最新資料日期不同（{details}），本次仍使用各自最新資料掃描')
    rows = sorted([r for batch in batches for r in batch],key=lambda r: (-r['turnover'],r['stock_id']))
    return rows

def get_active_stocks(limit=20):
    if not 1 <= limit <= 30:
        raise ValueError('掃描檔數必須為 1 到 30')
    rows = _load_active_stocks()
    return rows[:limit]

def get_active_stocks_by_price(per_group=10):
    """Return equal-sized high/mid/low price groups, ranked by turnover."""
    if not 1 <= per_group <= 10:
        raise ValueError('每個價位組的掃描檔數必須為 1 到 10')
    rows = _load_active_stocks()
    groups = (
        ('高價', lambda price: price >= 200),
        ('中價', lambda price: 50 <= price < 200),
        ('低價', lambda price: price < 50),
    )
    selected = []
    for label, matches in groups:
        batch = [dict(row, price_group=label) for row in rows if matches(row['price'])]
        selected.extend(batch[:per_group])
    return selected
