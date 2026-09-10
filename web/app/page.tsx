"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Strategy, RunResult } from "@/lib/api";
import { ActionBadge, SourceBadge } from "@/components/ActionBadge";

export default function Dashboard() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [picked, setPicked] = useState<string>("default");
  const [market, setMarket] = useState<any>(null);
  const [watchCount, setWatchCount] = useState<number | null>(null);
  const [universe, setUniverse] = useState<"watchlist" | "active" | "price_groups">("price_groups");
  const [activeCount, setActiveCount] = useState(10);
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listStrategies().then((d) => {
      setStrategies(d.strategies);
      if (d.strategies.find((s) => s.id === "default")) setPicked("default");
      else if (d.strategies[0]) setPicked(d.strategies[0].id);
    });
    api.getMarket().then(setMarket).catch(() => setMarket(null));
    api.getWatchlist().then((w) => setWatchCount(w.items?.length ?? 0)).catch(() => setWatchCount(null));
  }, []);

  async function doRun() {
    setRunning(true);
    setError(null);
    setRun(null);
    try {
      const r = await api.run(picked, undefined, universe, activeCount);
      setRun(r);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  const selected = strategies.find((s) => s.id === picked);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-muted mt-1">選擇成交活躍台股或自己的觀察清單，再執行策略。</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <div className="text-xs text-muted">大盤狀態</div>
          {market ? (
            <>
              <div className={"text-2xl font-semibold mt-2 " + (market.bullish ? "text-buy" : "text-err")}>
                {market.bullish ? "🟢 多頭" : "🔴 空頭"}
              </div>
              <div className="text-xs text-muted mt-2 leading-relaxed">{market.note}</div>
            </>
          ) : (
            <div className="text-muted mt-2 text-sm">載入中…</div>
          )}
        </div>
        <div className="card">
          <div className="text-xs text-muted">Watchlist</div>
          <div className="text-2xl font-semibold mt-2">{watchCount ?? "—"} 檔</div>
          <div className="text-xs text-muted mt-2">來自 Google Sheet</div>
        </div>
        <div className="card">
          <div className="text-xs text-muted">可用策略</div>
          <div className="text-2xl font-semibold mt-2">{strategies.length}</div>
          <div className="text-xs text-muted mt-2">
            <Link href="/strategies/ai" className="hover:text-text underline-offset-4 hover:underline">+ AI 生一個</Link>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="font-medium mb-4">執行今日選股</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
          <label className="label">股票來源
            <select className="input" disabled={running} value={universe} onChange={e => setUniverse(e.target.value as "active" | "watchlist" | "price_groups")}>
              <option value="price_groups">高／中／低價分組掃描</option>
              <option value="active">成交活躍台股（上市＋上櫃）</option>
              <option value="watchlist">我的 Watchlist</option>
            </select>
          </label>
          {universe === "active" && <label className="label">依成交金額取前幾檔
            <select className="input" disabled={running} value={activeCount} onChange={e => setActiveCount(Number(e.target.value))}>
              {[10,20,30].map(n => <option key={n} value={n}>{n} 檔</option>)}
            </select>
          </label>}
          {universe === "price_groups" && <label className="label">每個價位取前幾檔
            <select className="input" disabled={running} value={activeCount} onChange={e => setActiveCount(Number(e.target.value))}>
              {[5,10].map(n => <option key={n} value={n}>{n} 檔（共 {n * 3} 檔）</option>)}
            </select>
          </label>}
        </div>
        {universe === "active" && <p className="text-xs text-muted mb-4">依交易所最新公布的日成交金額排序；限四碼普通股、成交量至少 1,500 張，成交金額不限。非即時盤中排行，分析可能需要數分鐘。此選項不會修改 Watchlist 或雲端排程。</p>}
        {universe === "price_groups" && <p className="text-xs text-muted mb-4">高價股 200 元以上、中價股 50～未滿 200 元、低價股低於 50 元；各組依成交金額排序，成交量至少 1,500 張，成交金額不限。GitHub 每日排程也使用相同分組。</p>}
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-end">
          <div>
            <label className="label">選擇策略</label>
            <select className="input" value={picked} onChange={(e) => setPicked(e.target.value)}>
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>{s.name}（{s.id}）</option>
              ))}
            </select>
            {selected && (
              <div className="flex items-center gap-2 mt-2 text-xs">
                <SourceBadge source={selected.source} />
                <span className="text-muted">{selected.description}</span>
              </div>
            )}
          </div>
          <button onClick={doRun} disabled={running || !picked} className="btn-primary h-10">
            {running ? "分析中…請稍候，可能需要數分鐘" : "▶ 執行"}
          </button>
        </div>
        {error && <div className="text-sm text-err mt-3">錯誤：{error}</div>}
      </div>

      {run && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-medium">執行結果</h2>
            <div className="flex gap-2 text-xs">
              <span className="badge-buy">BUY {run.summary.buy}</span>
              <span className="badge-watch">WATCH {run.summary.watch}</span>
              <span className="badge-skip">SKIP {run.summary.skip}</span>
              {run.summary.error > 0 && <span className="badge-err">ERR {run.summary.error}</span>}
            </div>
          </div>
          <div className="text-xs text-muted mb-3">{run.market.note}</div>
          <div className="text-xs text-muted mb-3">來源：{run.universe?.source === "price_groups" ? "高／中／低價分組" : run.universe?.source === "active" ? "成交活躍台股" : "Watchlist"} · 分析 {run.summary.total} 檔 {run.universe?.date && `· 成交排行日期 ${run.universe.date}`}</div>
          <div className="space-y-2">
            {run.results.map((r) => (
              <div key={r.stock_id} className="bg-panel2 border border-line rounded-lg p-3 flex items-center gap-3">
                <ActionBadge action={r.action} />
                <div className="font-mono w-16">{r.stock_id}</div>
                <div className="flex-1 truncate">
                  <div className="text-sm">{r.name}</div>
                  <div className="text-xs text-muted">
                    {r.risk_notes?.join(" · ") || r.components?.tech_signals?.join(" · ") || "—"}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono">{r.signal_score}</div>
                  <div className="text-xs text-muted">
                    勝率 {r.components?.backtest_winrate != null
                      ? `${(r.components.backtest_winrate * 100).toFixed(0)}%` : "—"}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
