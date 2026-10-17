# -*- coding: utf-8 -*-
"""云端版选股引擎：不依赖富途 OpenD，可在 GitHub Actions 等无人值守环境运行。

数据源（全部免费、无需密钥）：
  - 港股宇宙：港交所官方证券列表（ListOfSecurities.xlsx），过滤 Equity 类别
  - 美股宇宙：NASDAQ 官方 screener API（覆盖 NYSE/NASDAQ/AMEX，含行业/国家）
  - 快照行情：腾讯 qt.gtimg.cn 批量快照（价格/涨跌幅/成交额/PE/市值/52周高低）

已验证的腾讯字段口径（2026-10-03 实测，见 reports/research.md）：
  [1]名称 [3]最新价 [4]昨收（[3]-[4]=[31]涨跌额，精确吻合） [32]涨跌幅%
  [36]成交量 [37]成交额（原币） [39]PE [44]总市值(亿原币) [48]52周高 [49]52周低
未确认字段（[43]/[71]/[72] 疑似换手/PE静/股息率但样本矛盾）一律不映射。

与本机版（engine.py）的差异：
  - 港股 PE_TTM/PB/股息由免费东方财富接口补充，逐条与腾讯价格核对；美股仍缺这些字段
  - circular_market_val 用总市值代替流通市值（筛选口径影响可接受）
  - 美股代码格式与 futu 对齐：US.AAPL / US.BRK.B（NASDAQ 的 BRK/B → BRK.B）
  - 港股代码格式与 futu 对齐：HK.00700

用法：python -m screener.cloud_engine
依赖：pandas、requests、openpyxl（读 HKEX xlsx）
"""
import io
import math
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from screener.common import clean, finalize_results, load_strategies, run_strategies, save_payload

HKEX_LIST_URL = "https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx"
NASDAQ_URL = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=25&offset=0&download=true"
TX_URL = "https://qt.gtimg.cn/q="

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TX_HEADERS = {**UA, "Referer": "https://gu.qq.com/"}

TX_BATCH = 400      # 腾讯批量快照每批代码数（实测 800 仍 100% 返回，留足余量）
RETRY = 3           # 单批次失败重试次数


def _get(url, *, headers=None, timeout=60, binary=False):
    """带重试的 GET"""
    last = None
    for i in range(RETRY):
        try:
            r = requests.get(url, headers=headers or UA, timeout=timeout)
            r.raise_for_status()
            return r.content if binary else r
        except Exception as e:
            last = e
            print(f"  [http] 第 {i+1} 次失败：{e}", flush=True)
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"请求失败（重试 {RETRY} 次）：{url} -> {last}")


def fetch_hk_universe() -> pd.DataFrame:
    """港交所官方证券列表 → 港股普通股宇宙（剔除 ETF/权证/牛熊证/债券）"""
    raw = _get(HKEX_LIST_URL, binary=True)
    df = pd.read_excel(io.BytesIO(raw), header=2)
    eq = df[(df["Category"] == "Equity") & df["Sub-Category"].astype(str).str.startswith("Equity Securities")]
    codes = ["HK." + str(int(c)).zfill(5) for c in eq["Stock Code"]]
    # 剔除人民币柜台（8xxxx，与港币柜台重复且流动性极低）
    before = len(codes)
    codes = [c for c in codes if not c.startswith("HK.8")]
    print(f"[universe] HKEX 港股普通股 {before} 只，剔除人民币柜台后 {len(codes)} 只", flush=True)
    return pd.DataFrame({"code": codes, "market": "HK"})


def fetch_us_universe() -> pd.DataFrame:
    """NASDAQ screener → 美股宇宙（含行业信息，顺便作为后备名称来源）"""
    r = _get(NASDAQ_URL)
    rows = r.json()["data"]["rows"]
    df = pd.DataFrame(rows)
    # 剔除明显非普通股：权证/单位/优先股常见符号特征
    df = df[~df["symbol"].str.contains(r"[\^~]", regex=True, na=False)]
    # futu 代码格式：BRK/B -> US.BRK.B（腾讯接口同样用点格式，已实测）
    df["code"] = "US." + df["symbol"].str.replace("/", ".", regex=False)
    df["market"] = "US"
    print(f"[universe] NASDAQ 美股 {len(df)} 只", flush=True)
    return df[["code", "market", "name", "sector", "industry", "country"]]


def to_tx_code(code: str) -> str:
    """HK.00700 -> hk00700；US.BRK.B -> usBRK.B"""
    mkt, sym = code.split(".", 1)
    return ("hk" if mkt == "HK" else "us") + sym


def parse_tx_line(line: str) -> dict | None:
    """解析单条腾讯快照；无效代码返回 None"""
    if "=" not in line or "pv_none_match" in line:
        return None
    f = line.split("=", 1)[1].strip().rstrip(";").strip('"').split("~")
    if len(f) < 50:
        return None

    def num(i):
        try:
            v = float(f[i])
            return v if math.isfinite(v) else None
        except (ValueError, IndexError):
            return None

    return {
        "tx_code": line.split("=", 1)[0].replace("v_", "").strip(),
        "name": f[1],
        "last_price": num(3),
        "prev_close_price": num(4),
        "quote_time": f[30] or None,
        "change_rate": num(32),
        "volume": num(36),
        "turnover": num(37),
        "pe_ratio": num(39) if num(39) and num(39) > 0 else None,
        "circular_market_val": (num(44) * 1e8) if num(44) else None,  # 亿 -> 原币
        "highest52weeks_price": num(48),
        "lowest52weeks_price": num(49),
    }


def fetch_tx_snapshots(codes: list) -> pd.DataFrame:
    """分批拉腾讯快照并合并。无效的 tx_code（停牌/退市/代码错误）自动剔除"""
    recs = []
    failed_batches = 0
    tx_map = {to_tx_code(c): c for c in codes}
    tx_codes = list(tx_map.keys())
    for i in range(0, len(tx_codes), TX_BATCH):
        batch = tx_codes[i : i + TX_BATCH]
        for attempt in range(RETRY):
            try:
                r = requests.get(TX_URL + ",".join(batch), headers=TX_HEADERS, timeout=60)
                r.raise_for_status()
                r.encoding = "gbk"
                lines = r.text.strip().split(";")
                break
            except Exception as e:
                print(f"  [snapshot] 批次 {i//TX_BATCH+1} 第 {attempt+1} 次失败：{e}", flush=True)
                time.sleep(3 * (attempt + 1))
        else:
            failed_batches += 1
            print(f"  [snapshot] 批次 {i//TX_BATCH+1} 放弃", flush=True)
            continue
        for line in lines:
            rec = parse_tx_line(line)
            if rec and rec["tx_code"] in tx_map:
                rec["code"] = tx_map[rec["tx_code"]]
                recs.append(rec)
        print(f"[snapshot] {min(i + TX_BATCH, len(tx_codes))}/{len(tx_codes)}", flush=True)
        time.sleep(0.5)
    if not recs:
        raise RuntimeError("腾讯快照全部失败或无有效记录，保留上次选股结果")
    df = pd.DataFrame(recs).drop(columns=["tx_code"]).drop_duplicates("code", keep="last")
    # 腾讯字段里没有的列补 NaN，保持与本机版列结构一致
    for col in ["pe_ttm_ratio", "pb_ratio", "dividend_ratio_ttm", "turnover_rate", "amplitude"]:
        df[col] = None
    print(f"[snapshot] 腾讯快照共 {len(df)} 只（宇宙 {len(codes)} 只）", flush=True)
    df.attrs["snapshot_quality"] = {
        "requested_count": len(tx_codes),
        "received_count": int(len(df)),
        "coverage_pct": round(len(df) / len(tx_codes) * 100, 2),
        "failed_batches": failed_batches,
    }
    return df


def main(*, output_path=None, include_history=True, archive_dir=None) -> None:
    t0 = time.time()

    hk = fetch_hk_universe()
    us = fetch_us_universe()
    uni = pd.concat([hk[["code", "market"]], us[["code", "market"]]], ignore_index=True)
    print(f"[universe] 美股+港股共 {len(uni)} 只", flush=True)

    snap = fetch_tx_snapshots(uni["code"].tolist())
    snapshot_quality = snap.attrs.get("snapshot_quality", {})

    # 美股补充行业信息（NASDAQ screener 提供；前端暂不展示，留作后续策略用）
    us_meta = us.drop(columns=["market"]).drop_duplicates("code")
    snap = snap.merge(us_meta, on="code", how="left", suffixes=("", "_nasdaq"))
    snap["name"] = snap["name"].fillna(snap.get("name_nasdaq"))
    snap = snap.drop(columns=[c for c in ["name_nasdaq"] if c in snap.columns])

    from screener.free_hk_fundamentals import enrich, cloud_strategy
    snap, fundamentals_summary = enrich(snap, hk["code"].tolist())
    print(f"[fundamentals] {fundamentals_summary}", flush=True)
    df = clean(snap)
    from screener.risk import enrich_snapshot
    df = enrich_snapshot(df)
    print(f"[clean] 流动性过滤后 {len(df)} 只", flush=True)

    strategies = load_strategies()
    # The cloud listed-share-cap variant has a new identity; local Futu keeps its original rules.
    strategies = [cloud_strategy(fundamentals_summary) if mod.META["id"] == "value_dividend" else mod
                  for mod in strategies]
    print(f"[strategies] 发现 {len(strategies)} 个策略", flush=True)

    results = run_strategies(df, strategies)

    # 三因子二次筛（方案 B）：对初筛命中名单拉 K 线做横截面重排序。
    # 失败不影响选股结果——策略本身的命中名单仍然完整可用。
    factor_summary = {"applied": False}
    try:
        from screener import factor_rank
        factor_summary = factor_rank.rerank(results)
    except Exception as e:
        factor_summary = {"applied": False, "reason": str(e)}
        print(f"[factor] 三因子二次筛失败（不影响选股结果）：{e}", flush=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "elapsed_sec": round(time.time() - t0, 1),
        "data_source": "cloud (HKEX + NASDAQ + Tencent + Eastmoney HK fundamentals)",
        "fundamentals": fundamentals_summary,
        "universe_total": int(len(uni)),
        "universe_after_filter": int(len(df)),
        "data_quality": {**df.attrs.get("data_quality", {}), **snapshot_quality},
        "factor_rank": factor_summary,
        "strategies": results,
    }
    from pathlib import Path
    from screener.tracking import ARCHIVE_DIR, TRACKING_OUT, freeze_snapshot, update_tracking
    archive_dir = Path(archive_dir) if archive_dir else (
        Path(output_path).resolve().parent / "screening_archive" if output_path else ARCHIVE_DIR)
    tracking_output = Path(output_path).resolve().parent / "tracking.json" if output_path else TRACKING_OUT
    record = freeze_snapshot(payload, archive_dir)
    payload["archive_id"] = record["id"]
    payload["strategy_version"] = record["strategy_version"]
    finalize_results(results, limit=50)
    if output_path is None:
        save_payload(payload)
    else:
        save_payload(payload, path=output_path)

    if not include_history:
        update_tracking(archive_dir, output_path=tracking_output)
        return

    # 网页回测历史数据管道：复用当日快照选股池，失败不影响选股结果部署
    try:
        from screener import history_fetch
        history_fetch.main(snap=df)
    except Exception as e:
        print(f"[history] 历史数据管道失败（不影响选股结果）：{e}", flush=True)

    update_tracking(archive_dir, output_path=tracking_output, fetch_missing=True)

    # ETF 轮动池数据管道（横截面轮动回测用，固定 4 只 A 股 ETF，无需快照）
    try:
        from screener import etf_fetch
        etf_fetch.main()
    except Exception as e:
        print(f"[etf] ETF 轮动池数据管道失败（不影响选股结果）：{e}", flush=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Write screening results to a separate JSON file")
    parser.add_argument("--skip-history", action="store_true", help="Skip rebuilding the backtest and ETF history pools")
    parser.add_argument("--archive-dir", help="Directory for immutable screening archives")
    args = parser.parse_args()
    main(output_path=args.output, include_history=not args.skip_history, archive_dir=args.archive_dir)
