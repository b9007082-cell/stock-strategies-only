"""FastAPI 後端

啟動：
  uv run uvicorn api.main:app --reload --port 8000

提供：
  GET    /api/health
  GET    /api/strategies              列出所有策略
  GET    /api/strategies/defaults     回傳預設參數 schema
  GET    /api/strategies/{id}         取單一策略
  POST   /api/strategies              新增 / 更新策略
  DELETE /api/strategies/{id}         刪除
  POST   /api/strategies/generate     AI 生策略 (Gemini)
  GET    /api/market                  目前大盤狀態
  GET    /api/watchlist               讀 watchlist
  POST   /api/run                     用指定策略跑一次完整評分
"""

from __future__ import annotations

import os
import time
import traceback
from typing import Any, Optional, Literal

import numpy as np
from fastapi.encoders import jsonable_encoder
from fastapi import FastAPI, HTTPException
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from stock_strategies.universe import get_active_stocks, get_active_stocks_by_price
from stock_strategies import loader
from stock_strategies.evaluate import evaluate
from stock_strategies.market import apply_market_filter, get_market_state
from stock_strategies.sheet import read_watchlist

from api.services.ai_generator import generate_strategy_with_ai

app = FastAPI(title="Stock Strategies API", version="1.0.0")


@app.middleware("http")
async def require_web_password(request: Request, call_next):
    password = os.environ.get("WEB_PASSWORD")
    if password and request.url.path.startswith("/api/") and request.url.path != "/api/health":
        if request.headers.get("X-Web-Password") != password:
            return JSONResponse(status_code=401, content={"detail": "請輸入網站密碼"})
    return await call_next(request)

# CORS：dev 期間給 localhost:3000 (Next.js)
_origins_env = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins_env.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Schemas ----------


class StrategyIn(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = ""
    source: Optional[str] = "manual"
    params: dict[str, Any] = Field(default_factory=dict)


class AIGenerateIn(BaseModel):
    prompt: str = Field(..., description="使用者用自然語言描述想要的策略風格")
    name: Optional[str] = None


class RunIn(BaseModel):
    universe: Literal["watchlist", "active", "price_groups"] = "watchlist"
    active_count: int = Field(20, ge=1, le=30)
    strategy_id: str
    limit: Optional[int] = Field(None, description="只跑前 N 檔（debug 用）")


# ---------- Routes ----------


@app.get("/api/health")
def health():
    return {"ok": True, "ts": int(time.time())}


@app.get("/api/strategies")
def list_strategies():
    return {"strategies": loader.list_strategies()}


@app.get("/api/strategies/defaults")
def defaults():
    return {"params": loader.param_defaults()}


@app.get("/api/strategies/{sid}")
def get_strategy(sid: str):
    s = loader.get_strategy(sid)
    if not s:
        raise HTTPException(404, f"找不到策略 {sid}")
    return s


@app.post("/api/strategies")
def save_strategy(payload: StrategyIn):
    try:
        clean = loader.save_strategy(payload.model_dump())
        return clean
    except loader.StrategyError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/strategies/{sid}")
def delete_strategy(sid: str):
    if sid in ("default", "conservative"):
        raise HTTPException(400, "預設策略不可刪除")
    ok = loader.delete_strategy(sid)
    if not ok:
        raise HTTPException(404, f"找不到策略 {sid}")
    return {"ok": True}


@app.post("/api/strategies/generate")
def generate_strategy(payload: AIGenerateIn):
    try:
        strategy = generate_strategy_with_ai(payload.prompt, name=payload.name)
        return strategy
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"AI 生策略失敗：{e}")


@app.get("/api/market")
def market():
    return get_market_state()


@app.get("/api/watchlist")
def watchlist():
    try:
        return {"items": read_watchlist()}
    except Exception as e:
        # 沒設定 Google Sheet 時不要整個 500
        return {"items": [], "error": str(e)}


@app.post("/api/run")
def run(payload: RunIn):
    strategy = loader.get_strategy(payload.strategy_id)
    if not strategy:
        raise HTTPException(404, f"找不到策略 {payload.strategy_id}")

    try:
        if payload.universe == "active":
            wl = get_active_stocks(payload.active_count)
        elif payload.universe == "price_groups":
            wl = get_active_stocks_by_price(min(payload.active_count, 10))
        else:
            wl = read_watchlist()
    except Exception as e:
        raise HTTPException(500, f"讀取股票清單失敗：{e}")

    if payload.limit:
        wl = wl[: payload.limit]

    params = strategy["params"]
    market_filter_on = params.get("market_filter_enabled", True)
    if market_filter_on:
        market_state = get_market_state(int(params.get("market_filter_ma_period", 20)))
    else:
        market_state = {"bullish": True, "note": "已關閉大盤濾鏡"}

    results = []
    for row in wl:
        sid = str(row["stock_id"])
        name = row.get("name", "")
        r = evaluate(sid, name, strategy=strategy)
        if r:
            results.append(r)
        time.sleep(0.4)

    if market_filter_on:
        downgraded = apply_market_filter(results, market_state)
    else:
        downgraded = 0

    order = {"BUY": 0, "WATCH": 1, "SKIP": 2, "ERROR": 3}
    results.sort(key=lambda x: (order.get(x.get("action"), 4), -x.get("signal_score", 0)))

    return jsonable_encoder({
        "universe": {"source": payload.universe, "count": len(wl), "date": wl[0].get("date") if wl else None},
        "strategy": {"id": strategy["id"], "name": strategy["name"]},
        "market": market_state,
        "downgraded": downgraded,
        "summary": {
            "total": len(results),
            "buy": sum(1 for r in results if r.get("action") == "BUY"),
            "watch": sum(1 for r in results if r.get("action") == "WATCH"),
            "skip": sum(1 for r in results if r.get("action") == "SKIP"),
            "error": sum(1 for r in results if r.get("action") == "ERROR"),
        },
        "results": results,
    }, custom_encoder={np.generic: lambda value: value.item()})
