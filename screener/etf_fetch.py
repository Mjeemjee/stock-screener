# -*- coding: utf-8 -*-
"""ETF 轮动池历史K线管道：为「横截面轮动」回测与样本外验证预取数据。

标的池（聚宽文章 81505 原文的 4 只 ETF）：
  512890 红利低波 / 159949 创业板50 / 513100 纳指100 / 518880 黄金
基准：000300 沪深300

数据源：东财 push2his 前复权（fqt=1），与站内港美股个股同源、同口径。
输出：portfolio-board/public/data/history/etf.json
bar 格式：[yyyymmdd(int), open, high, low, close, volume]，前复权，按日期升序。

用途：
  1. 网页回测页「横截面轮动」模式的默认池；
  2. 样本外验证（2018 / 2022 下跌震荡区间）——见 scripts/validate-rotation.cjs。

用法：python -m screener.etf_fetch
"""
import json
import os
import time

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "portfolio-board", "public", "data", "history")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "Referer": "https://quote.eastmoney.com/"}

EM_KLINE_URL = (
    "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}"
    "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56"
    "&klt=101&fqt=1&beg=0&end=20500101&lmt=100000"
)

# 池顺序即打分并列时的优先级（对应原作 ETF_POOL 顺序）
ETF_POOL = [
    ("512890", "1.512890", "红利低波ETF"),
    ("159949", "0.159949", "创业板50ETF"),
    ("513100", "1.513100", "纳指100ETF"),
    ("518880", "1.518880", "黄金ETF"),
]
BENCH = ("000300", "1.000300", "沪深300")

RETRY = 3
SLEEP = 0.2


def _get(url):
    for i in range(RETRY):
        try:
            r = requests.get(url, headers=UA, timeout=25)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"  [http] 第 {i+1} 次失败：{type(e).__name__} {str(e)[:70]}", flush=True)
            time.sleep(2 * (i + 1))
    return None


def _ymd(date_str: str) -> int:
    return int(date_str.replace("-", ""))


def _bar(line: str):
    # 东财 kline 行：date,open,close,high,low,volume,amount,...
    p = line.split(",")
    return [_ymd(p[0]), round(float(p[1]), 4), round(float(p[3]), 4),
            round(float(p[4]), 4), round(float(p[2]), 4), int(float(p[5]))]


def fetch_bars(secid: str):
    r = _get(EM_KLINE_URL.format(secid=secid))
    if r is None:
        return None
    try:
        data = r.json().get("data")
        if not data or not data.get("klines"):
            return None
        bars = [_bar(k) for k in data["klines"]]
        return bars if len(bars) >= 10 else None
    except Exception as e:
        print(f"  [parse] {secid} 解析失败：{e}", flush=True)
        return None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    stocks, failures = [], []
    for code, secid, name in ETF_POOL:
        bars = fetch_bars(secid)
        if bars:
            stocks.append({"code": code, "name": name, "bars": bars})
            print(f"[etf] {code} {name}: {len(bars)} 根 "
                  f"{bars[0][0]}~{bars[-1][0]}", flush=True)
        else:
            failures.append({"code": code, "reason": "无数据"})
            print(f"[etf] {code} {name}: 失败", flush=True)
        time.sleep(SLEEP)

    bench_bars = fetch_bars(BENCH[1])
    if bench_bars:
        print(f"[etf] 基准 {BENCH[2]}: {len(bench_bars)} 根 "
              f"{bench_bars[0][0]}~{bench_bars[-1][0]}", flush=True)

    # 全部失败时不得覆盖旧数据：轮动回测依赖 etf.json，东财故障不应清空它
    if not stocks and not bench_bars:
        print("[etf] 本次全部取数失败，保留既有 etf.json（不覆盖）", flush=True)
        return

    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pool": ETF_POOL,
        "bench": BENCH[2],
        "bench_bars": bench_bars or [],
        "survivorship_note": "固定 4 只 ETF 池（原文标的），无幸存者偏差",
        "source": "东财 push2his 前复权",
        "stocks": stocks,
        "failures": failures,
    }
    out = os.path.join(OUT_DIR, "etf.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    mb = os.path.getsize(out) / 1e6
    print(f"saved: {out}（{mb:.1f} MB），耗时 {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()