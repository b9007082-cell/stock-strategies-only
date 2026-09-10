"""Latest official TWSE/TPEx turnover ranking for ordinary shares."""
import re
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
        shares, turnover = number(row.get(volume)), number(row.get(amount))
        if shares < 1_500_000 or number(row.get(close)) <= 0:
            continue
        raw_date = str(row.get('Date', '')).strip()
        if not re.fullmatch(r'\d{7}', raw_date):
            raise ValueError('成交資料日期格式異常')
        date = datetime.strptime(str(int(raw_date[:3])+1911)+raw_date[3:], '%Y%m%d').date()
        age = (datetime.now(ZoneInfo('Asia/Taipei')).date()-date).days
        if age < 0 or age > 14:
            raise ValueError('成交資料已過期，請稍後重試')
        result.append(dict(stock_id=sid, name=row[name].strip(), enabled=True,
                           market=market, turnover=turnover, volume=shares, date=date.isoformat()))
    return result

def get_active_stocks(limit=20):
    if not 1 <= limit <= 30:
        raise ValueError('掃描檔數必須為 1 到 30')
    def fetch(source):
        try:
            response = requests.get(
                source[1],
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 stock-strategies-only/3.3"},
            )
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list) or not rows:
                raise ValueError('empty data')
            return normalize(rows, source)
        except Exception:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        batches = list(pool.map(fetch, SOURCES))
    failed = [source[0] for source, batch in zip(SOURCES, batches) if not batch]
    batches = [batch for batch in batches if batch]
    if not batches:
        raise ValueError('上市與上櫃成交資料均讀取失敗，請稍後重試')
    if failed:
        print(f"  注意：{'、'.join(failed)}成交資料暫時無法取得，本次使用其餘市場掃描")
    dates = {r['date'] for batch in batches for r in batch}
    if len(dates) != 1:
        raise ValueError('上市與上櫃資料日期不同，請待資料更新後重試')
    rows = sorted([r for batch in batches for r in batch],key=lambda r: (-r['turnover'],r['stock_id']))
    return rows[:limit]
