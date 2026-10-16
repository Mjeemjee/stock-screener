# -*- coding: utf-8 -*-
"""选股引擎：拉取美股/港股全市场快照，加载 strategies/ 下全部策略并执行，输出 data/screener_results.json

用法：python -m screener.engine   （需 OpenD 已启动并登录）
"""
import time
from datetime import datetime, timezone

import pandas as pd
from futu import Market, OpenQuoteContext, RET_OK, SecurityType
from screener.common import clean, load_strategies, run_strategies, save_payload

BATCH = 400  # get_market_snapshot 单次上限

def get_universe(q) -> pd.DataFrame:
    """美股（仅 NYSE/NASDAQ/AMEX 主板，排除 OTC）+ 港股主板普通股代码列表"""
    frames = []
    for mkt, prefix in [(Market.US, "US"), (Market.HK, "HK")]:
        ret, df = q.get_stock_basicinfo(mkt, SecurityType.STOCK)
        if ret != RET_OK:
            print(f"[universe] {prefix} 获取失败: {df}", flush=True)
            continue
        if prefix == "US" and "exchange_type" in df.columns:
            before = len(df)
            df = df[df["exchange_type"].isin(["US_NYSE", "US_NASDAQ", "US_AMEX"])]
            print(f"[universe] US 剔除 OTC：{before} -> {len(df)}", flush=True)
        if prefix == "HK":
            before = len(df)
            # 剔除人民币柜台（8xxxx，与港币柜台重复且流动性极低）
            df = df[~df["code"].str.replace("HK.", "", regex=False).str.startswith("8")]
            print(f"[universe] HK 剔除人民币柜台：{before} -> {len(df)}", flush=True)
        df["market"] = prefix
        frames.append(df[["code", "name", "market"]])
    if not frames:
        raise RuntimeError("未获取到任何市场的股票列表，请检查 OpenD 登录与行情权限")
    uni = pd.concat(frames, ignore_index=True)
    print(f"[universe] 美股+港股共 {len(uni)} 只", flush=True)
    return uni


def fetch_snapshots(q, codes) -> pd.DataFrame:
    """分批拉快照并合并"""
    frames = []
    for i in range(0, len(codes), BATCH):
        batch = codes[i : i + BATCH]
        ret, snap = q.get_market_snapshot(batch)
        if ret != RET_OK:
            print(f"[snapshot] 批次 {i//BATCH+1} 失败: {snap}", flush=True)
            continue
        frames.append(snap)
        print(f"[snapshot] {min(i + BATCH, len(codes))}/{len(codes)}", flush=True)
        time.sleep(1.2)  # 快照有频率限制，留余量
    if not frames:
        raise SystemExit("快照全部失败，请检查 OpenD 登录与行情权限")
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    t0 = time.time()
    q = OpenQuoteContext(host="127.0.0.1", port=11111)
    try:
        uni = get_universe(q)
        snap = fetch_snapshots(q, uni["code"].tolist())
    finally:
        q.close()

    df = clean(snap)
    from screener.risk import enrich_snapshot
    df = enrich_snapshot(df)
    print(f"[clean] 流动性过滤后 {len(df)} 只", flush=True)

    strategies = load_strategies()
    print(f"[strategies] 发现 {len(strategies)} 个策略", flush=True)

    results = run_strategies(df, strategies)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "elapsed_sec": round(time.time() - t0, 1),
        "universe_total": int(len(uni)),
        "universe_after_filter": int(len(df)),
        "data_source": "Futu OpenD",
        "data_quality": df.attrs.get("data_quality", {}),
        "strategies": results,
    }
    from screener.common import finalize_results
    from screener.tracking import freeze_snapshot, update_tracking
    record = freeze_snapshot(payload)
    payload["archive_id"] = record["id"]
    payload["strategy_version"] = record["strategy_version"]
    finalize_results(results)
    save_payload(payload)
    update_tracking()


if __name__ == "__main__":
    main()
