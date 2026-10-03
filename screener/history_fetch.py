# -*- coding: utf-8 -*-
"""历史K线数据管道：为网页回测预取流动性股票池的日K数据。

数据源（全部免费、无需密钥；2026-10-03 实测，见 reports/research.md）：
  - 港股：腾讯 fqkline 前复权（640 根 ≈ 2.5 年）；兜底 东财 push2his（116 前缀）→ 雅虎（0700.HK 格式）
  - 美股：东财 push2his 前复权（105/106/107 前缀自动探测）；兜底 Yahoo chart
  - 基准指数：东财 100.SPX / 100.HSI；兜底 Yahoo ^GSPC / ^HSI
  - 腾讯美股历史已失效（任何复权参数均只返回 2 根），不可用作美股来源

输出（紧凑 JSON，放 vite public 目录随构建自动部署；文件大不入 git）：
  portfolio-board/public/data/history/hk.json     港股池
  portfolio-board/public/data/history/us.json     美股池
  portfolio-board/public/data/history/index.json  基准指数（SPX/HSI）
bar 格式：[yyyymmdd(int), open, high, low, close, volume]，前复权，按日期升序。

已知偏差（必须在 UI 披露）：股票池按「当日」成交额选取流动性 Top N，
对历史区间回测存在幸存者偏差（已退市/流动性衰退的标的不在池中），结果偏乐观。

用法：
  独立运行：python -m screener.history_fetch             （自行拉快照确定股票池）
  被 cloud_engine 调用：history_fetch.main(snap=df)      （复用当日快照，不重复拉取）
"""
import json
import os
import time

import pandas as pd
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "portfolio-board", "public", "data", "history")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TX_HEADERS = {**UA, "Referer": "https://gu.qq.com/"}
EM_HEADERS = {**UA, "Referer": "https://quote.eastmoney.com/"}

TX_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{count},qfq"
EM_KLINE_URL = (
    "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}"
    "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56"
    "&klt=101&fqt=1&beg=0&end=20500101&lmt={count}"
)
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=3y&interval=1d"

BAR_COUNT = 640        # 每标的日K根数（≈2.5 年）
POOL_SIZE = 300        # 每市场股票池大小（按当日成交额 Top N）
MIN_BARS = 480         # 少于此根数的标的剔除（上市时间太短，指标无法稳定）
RETRY = 3
SLEEP = 0.15           # 单标的请求间隔（礼貌限速）

# 东财美股 secid 市场前缀（NASDAQ/NYSE/AMEX），按命中率顺序探测
EM_US_PREFIXES = ["105", "106", "107"]
EM_INDEX = {"SPX": "100.SPX", "HSI": "100.HSI"}   # 基准：标普500 / 恒生指数
YAHOO_INDEX = {"SPX": "^GSPC", "HSI": "^HSI"}


def _get(url, *, headers=None, timeout=25):
    """带重试的 GET。返回 (response|None, 是否网络层失败)。
    HTTP 状态错误（4xx/5xx）是确定性失败，不重试；网络错误重试 RETRY 次。"""
    for i in range(RETRY):
        try:
            r = requests.get(url, headers=headers or UA, timeout=timeout)
            r.raise_for_status()
            return r, False
        except requests.exceptions.HTTPError as e:
            print(f"  [http] 状态错误不重试：{e.response.status_code} {url[:90]}", flush=True)
            return None, False
        except Exception as e:
            print(f"  [http] 第 {i+1} 次失败：{type(e).__name__} {str(e)[:60]}", flush=True)
            time.sleep(2 * (i + 1))
    return None, True


# 东财接口熔断器：连续网络失败 3 次判定主机不可达，本轮不再尝试
# （本机代理对 push2his 间歇断连时，避免每只股票白等 3 次重试；Actions 干净网络不会触发）
_EM = {"consec_fails": 0, "down": False}


def _ymd(date_str: str) -> int:
    return int(date_str.replace("-", ""))


def _bar(date_str, o, h, l, c, v):
    return [_ymd(date_str), round(float(o), 3), round(float(h), 3),
            round(float(l), 3), round(float(c), 3), int(float(v))]


# ---------------------------------------------------------------- 各源取数

def fetch_tx_kline(tx_code: str, count: int = BAR_COUNT) -> list | None:
    """腾讯前复权日K（港股主用）。返回 [date,o,h,l,c,v] 升序，失败 None。
    响应行格式：[date, open, close, high, low, volume, ...] → 重排为 o,h,l,c,v"""
    r, _ = _get(TX_KLINE_URL.format(code=tx_code, count=count), headers=TX_HEADERS)
    if r is None:
        return None
    try:
        node = r.json()["data"][tx_code]
        key = next((k for k in node if "day" in k), None)
        raw = node[key] if key else []
        bars = [_bar(b[0], b[1], b[3], b[4], b[2], b[5]) for b in raw if len(b) >= 6]
        return bars if len(bars) >= 10 else None
    except Exception:
        return None


def fetch_em_kline(secid: str, count: int = BAR_COUNT) -> list | None:
    """东财前复权日K（美股主用、港股/指数兜底）。带主机级熔断。
    klines 行格式：date,open,close,high,low,volume → 重排为 o,h,l,c,v"""
    if _EM["down"]:
        return None
    r, network_failed = _get(EM_KLINE_URL.format(secid=secid, count=count), headers=EM_HEADERS)
    if r is None:
        if network_failed:
            _EM["consec_fails"] += 1
            if _EM["consec_fails"] >= 3 and not _EM["down"]:
                _EM["down"] = True
                print("[em] 东财连续网络失败，本轮熔断，后续标的直连备用源", flush=True)
        return None
    _EM["consec_fails"] = 0
    try:
        data = r.json().get("data")
        raw = data["klines"] if data else []
        bars = []
        for line in raw:
            f = line.split(",")
            if len(f) >= 6:
                bars.append(_bar(f[0], f[1], f[3], f[4], f[2], f[5]))
        return bars[-count:] if len(bars) >= 10 else None
    except Exception:
        return None


def fetch_em_us_kline(symbol: str, count: int = BAR_COUNT) -> list | None:
    """美股东财日K：自动探测 secid 市场前缀（105/106/107）"""
    for prefix in EM_US_PREFIXES:
        bars = fetch_em_kline(f"{prefix}.{symbol}", count)
        if bars:
            return bars
    return None


def fetch_yahoo_kline(symbol: str, count: int = BAR_COUNT) -> list | None:
    """Yahoo chart 日K（兜底，含拆股调整的 adjclose；此处用原始 OHLC + adjclose 修正收盘）"""
    r, _ = _get(YAHOO_URL.format(symbol=symbol), headers=UA)
    if r is None:
        return None
    try:
        res = r.json()["chart"]["result"][0]
        ts = res["timestamp"]
        q = res["indicators"]["quote"][0]
        adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose", q["close"])
        bars = []
        for i, t in enumerate(ts):
            o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
            if None in (o, h, l, c) or v is None:
                continue
            # 用 adjclose/close 比例把 OHLC 调整为前复权口径
            ratio = (adj[i] / c) if c and adj[i] else 1.0
            d = time.strftime("%Y-%m-%d", time.gmtime(t))
            bars.append(_bar(d, o * ratio, h * ratio, l * ratio, c * ratio, v))
        return bars[-count:] if len(bars) >= 10 else None
    except Exception:
        return None


# ---------------------------------------------------------------- 按市场封装

def hk_bars(code: str) -> list | None:
    """HK.00700 → 前复权日K（腾讯主，东财备，雅虎 0700.HK 兜底）"""
    sym = code.split(".", 1)[1]
    bars = fetch_tx_kline("hk" + sym)
    if bars is None:
        bars = fetch_em_kline(f"116.{sym}")
    if bars is None:
        bars = fetch_yahoo_kline(f"{int(sym):04d}.HK")
    return bars


def us_bars(code: str) -> list | None:
    """US.BRK.B → 前复权日K（东财主，Yahoo 备；Yahoo 符号用 BRK-B 横线格式）"""
    sym = code.split(".", 1)[1]
    bars = fetch_em_us_kline(sym)
    if bars is None:
        bars = fetch_yahoo_kline(sym.replace(".", "-"))
    return bars


def fetch_index_bars(key: str) -> list | None:
    """基准指数日K（东财主，Yahoo 备）"""
    bars = fetch_em_kline(EM_INDEX[key])
    if bars is None:
        bars = fetch_yahoo_kline(YAHOO_INDEX[key])
    return bars


# ---------------------------------------------------------------- 主流程

def select_pool(snap: pd.DataFrame, market: str, top_n: int = POOL_SIZE) -> list:
    """按当日成交额取流动性 Top N。返回 [(code, name), ...]"""
    df = snap[snap["market"] == market].copy()
    df = df.dropna(subset=["turnover"]).sort_values("turnover", ascending=False)
    pool = [(r["code"], r.get("name") or r["code"]) for _, r in df.head(top_n).iterrows()]
    print(f"[pool] {market} 候选 {len(df)} 只 → 取成交额 Top {len(pool)}", flush=True)
    return pool


def build_market_payload(market: str, pool: list) -> dict:
    """逐只拉历史K线，组装市场数据文件"""
    getter = hk_bars if market == "HK" else us_bars
    stocks, failures = [], []
    t0 = time.time()
    for i, (code, name) in enumerate(pool):
        bars = getter(code)
        if bars and len(bars) >= MIN_BARS:
            stocks.append({"code": code, "name": name, "bars": bars})
        else:
            failures.append({"code": code, "reason": "无数据或K线不足"})
        if (i + 1) % 25 == 0:
            print(f"[history] {market} {i+1}/{len(pool)}（成功 {len(stocks)}，"
                  f"耗时 {time.time()-t0:.0f}s）", flush=True)
        time.sleep(SLEEP)
    print(f"[history] {market} 完成：{len(stocks)}/{len(pool)} 成功，"
          f"失败 {len(failures)}，耗时 {time.time()-t0:.0f}s", flush=True)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "market": market,
        "bar_count": BAR_COUNT,
        "pool_size_requested": len(pool),
        "stock_count": len(stocks),
        "survivorship_note": "股票池按当日成交额选取，回测存在幸存者偏差，结果偏乐观",
        "failures": failures[:50],
        "stocks": stocks,
    }


def cross_check(payload: dict, snap: pd.DataFrame) -> None:
    """AC-401 交叉验证：抽样标的最后一根收盘价 vs 当日快照价，误差应 ≤0.5%"""
    if not payload["stocks"]:
        return
    sample = payload["stocks"][0]
    kline_close = sample["bars"][-1][4]
    row = snap[snap["code"] == sample["code"]]
    if row.empty:
        return
    snap_price = float(row.iloc[0]["last_price"])
    diff = abs(kline_close / snap_price - 1) * 100 if snap_price else float("inf")
    status = "OK" if diff <= 0.5 else "!!超差!!"
    print(f"[xcheck] {sample['code']} K线收盘 {kline_close} vs 快照 {snap_price} "
          f"偏差 {diff:.3f}% {status}", flush=True)


def save(payload: dict, filename: str) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    mb = os.path.getsize(path) / 1e6
    print(f"saved: {path}（{mb:.1f} MB）", flush=True)
    return path


def main(snap: pd.DataFrame | None = None) -> None:
    """snap 为 cloud_engine 已拉好的快照（含 market/turnover 列）；None 时自行拉取"""
    t0 = time.time()
    if snap is None:
        from screener.cloud_engine import (fetch_hk_universe, fetch_tx_snapshots,
                                           fetch_us_universe)
        hk = fetch_hk_universe()
        us = fetch_us_universe()
        uni = pd.concat([hk[["code"]], us[["code"]]], ignore_index=True)
        snap = fetch_tx_snapshots(uni["code"].tolist())
    if "market" not in snap.columns:
        snap = snap.copy()
        snap["market"] = snap["code"].str.split(".").str[0]

    for market, fname in [("HK", "hk.json"), ("US", "us.json")]:
        pool = select_pool(snap, market)
        payload = build_market_payload(market, pool)
        cross_check(payload, snap)
        save(payload, fname)

    idx = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "indexes": {}}
    for key in ("SPX", "HSI"):
        bars = fetch_index_bars(key)
        if bars:
            idx["indexes"][key] = {"name": "标普500" if key == "SPX" else "恒生指数",
                                   "bars": bars}
            print(f"[index] {key} {len(bars)} 根", flush=True)
        else:
            print(f"[index] {key} 获取失败", flush=True)
    save(idx, "index.json")

    print(f"[history] 全部完成，总耗时 {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
