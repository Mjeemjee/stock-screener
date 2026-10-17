"""Public HK financial snapshots; no OpenD, API key or persistent fallback cache."""
from copy import deepcopy
from datetime import datetime, timezone
import math
import re
import time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
import requests

URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
REPORT = "RPT_CUSTOM_HKF10_FN_MAININDICATORMAX"
SOURCE = "Eastmoney HK F10"
PAGE_SIZE = 500
REQUIRED = {"SECURITY_CODE", "SECUCODE", "IS_CNY_CODE", "REPORT_DATE", "PE_TTM",
            "PB_TTM", "DIVIDEND_TTM", "DIVIDEND_RATE", "HKSK_MARKET_CAP", "HK_COMMON_SHARES"}
NUMERIC = ("pe_ttm_ratio", "pb_ratio", "dividend_ratio_ttm", "hk_market_val")


def number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def fetch_rows(*, get=None, sleep=time.sleep):
    """Reject incomplete batches rather than quietly reporting a smaller universe."""
    get = get or requests.get
    rows, expected, pages = [], None, 1
    page = 1
    while page <= pages:
        params = {"reportName": REPORT, "columns": "ALL", "pageNumber": str(page),
                  "pageSize": str(PAGE_SIZE), "sortColumns": "SECURITY_CODE",
                  "sortTypes": "1", "source": "F10", "client": "PC"}
        for attempt in range(2):
            try:
                response = get(URL, params=params, timeout=15)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or payload.get("success") is not True:
                    raise ValueError("财务接口返回失败状态")
                result = payload.get("result")
                if not isinstance(result, dict) or not isinstance(result.get("data"), list):
                    raise ValueError("财务接口返回格式错误")
                count, total_pages = result.get("count"), result.get("pages")
                if (type(count) is not int or type(total_pages) is not int or
                        not 0 < count <= 20000 or total_pages != math.ceil(count / PAGE_SIZE)):
                    raise ValueError("财务接口分页元数据不完整")
                if expected is not None and (count != expected or total_pages != pages):
                    raise ValueError("财务接口分页期间记录数变化")
                batch = result["data"]
                if len(batch) != min(PAGE_SIZE, count - (page - 1) * PAGE_SIZE):
                    raise ValueError("财务接口分页记录截断")
                if any(not isinstance(row, dict) or not REQUIRED.issubset(row) for row in batch):
                    raise ValueError("财务接口缺少必要字段")
                expected, pages = count, total_pages
                rows.extend(batch)
                break
            except (requests.RequestException, ValueError, TypeError, KeyError):
                if attempt == 1:
                    raise
                sleep(1)
        page += 1
        if page <= pages:
            sleep(.2)
    codes = [row["SECURITY_CODE"] for row in rows]
    if (any(not isinstance(code, str) or not re.fullmatch(r"\d{5}", code) for code in codes)
            or len(set(codes)) != expected):
        raise ValueError("财务接口代码无效、重复或批次不完整")
    return rows


def latest_completed_session(now):
    from screener.risk import exchange_calendar
    schedule = exchange_calendar("HK").schedule
    closed = schedule.loc[schedule["close"] <= pd.Timestamp(now)]
    if closed.empty or now.date() > schedule.index[-1].date():
        raise ValueError("港股交易日历未覆盖当前时间")
    return closed.index[-1].date()


def quote_instant(value):
    value = str(value or "")
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=ZoneInfo("Asia/Hong_Kong"))
        except ValueError:
            continue
    return None


def enrich(snap, official_codes, *, now=None, fetch=None):
    """Fill only corroborated HK records; failure leaves other strategies unchanged."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("采集时间必须包含时区")
    out = snap.copy(deep=True)
    out.attrs = deepcopy(snap.attrs)
    hk = out["code"].isin(set(official_codes)) & out["code"].str.startswith("HK.")
    for field in NUMERIC:
        if field not in out:
            out[field] = float("nan")
        out.loc[hk, field] = float("nan")
    for field in ("fundamentals_source", "fundamentals_fetched_at", "fundamentals_report_date",
                  "fundamentals_quote_date", "fundamentals_status"):
        if field not in out:
            out[field] = pd.Series(None, index=out.index, dtype=object)
    out.loc[hk, "fundamentals_status"] = "unavailable"
    summary = {"source": SOURCE, "status": "unavailable", "fetched_at": now.isoformat(timespec="seconds"),
               "requested_count": int(hk.sum()), "source_count": 0, "matched_count": 0,
               "verified_count": 0, "dividend_available_count": 0,
               "note": "仅港股；空股息为未知；港股市值与流通市值不同，美股未覆盖。"}
    if not hk.any():
        summary["status"] = "not_applicable"
        return out, summary
    try:
        session = latest_completed_session(now)
        rows = (fetch or fetch_rows)()
        by_code = {"HK." + row["SECURITY_CODE"]: row for row in rows
                   if str(row.get("IS_CNY_CODE")) == "0" and not row["SECURITY_CODE"].startswith("8")
                   and row.get("SECUCODE") == row["SECURITY_CODE"] + ".HK"}
        summary["source_count"] = len(rows)
        for index in out.index[hk]:
            row = by_code.get(out.at[index, "code"])
            if row is None:
                out.at[index, "fundamentals_status"] = "not_covered"
                continue
            summary["matched_count"] += 1
            period = pd.to_datetime(row.get("REPORT_DATE"), errors="coerce")
            qinstant = quote_instant(out.at[index, "quote_time"] if "quote_time" in out else None)
            qdate = qinstant.date() if qinstant else None
            price = number(out.at[index, "last_price"])
            cap, shares = number(row.get("HKSK_MARKET_CAP")), number(row.get("HK_COMMON_SHARES"))
            status = None
            if pd.isna(period) or period.date() > now.date() or (now.date() - period.date()).days > 550:
                status = "invalid_report_period"
            elif qdate != session or qinstant > now:
                status = "stale_quote"
            elif not price or price <= 0 or not cap or cap <= 0 or not shares or shares <= 0:
                status = "missing_price_basis"
            elif abs(cap / shares / price - 1) > .01:
                status = "price_mismatch"
            if status:
                out.at[index, "fundamentals_status"] = status
                continue
            out.at[index, "pe_ttm_ratio"] = number(row.get("PE_TTM"))
            out.at[index, "pb_ratio"] = number(row.get("PB_TTM"))
            out.at[index, "hk_market_val"] = cap
            out.at[index, "fundamentals_source"] = SOURCE
            out.at[index, "fundamentals_fetched_at"] = summary["fetched_at"]
            out.at[index, "fundamentals_report_date"] = period.date().isoformat()
            out.at[index, "fundamentals_quote_date"] = qdate.isoformat()
            out.at[index, "fundamentals_status"] = "verified"
            summary["verified_count"] += 1
            dps, dy = number(row.get("DIVIDEND_TTM")), number(row.get("DIVIDEND_RATE"))
            if (dps is not None and dy is not None and dps >= 0 and dy >= 0
                    and abs(dps / price * 100 - dy) <= .0001):
                out.at[index, "dividend_ratio_ttm"] = dy
                summary["dividend_available_count"] += 1
            else:
                out.at[index, "fundamentals_status"] = "dividend_unknown_or_mismatch"
        summary["status"] = "ok" if summary["verified_count"] else "unavailable"
    except Exception as exc:
        # No partial or cached values may escape a failed fetch/normalization.
        out.loc[hk, list(NUMERIC)] = float("nan")
        out.loc[hk, "fundamentals_status"] = "source_error"
        summary.update(status="error", verified_count=0, dividend_available_count=0,
                       error=f"{type(exc).__name__}: {str(exc)[:200]}")
    return out, summary


def cloud_strategy(summary):
    """A distinct identity keeps the listed-share-cap variant out of old archives."""
    from screener.strategies import value_dividend
    meta = deepcopy(value_dividend.META)
    meta.update(id="value_dividend_hk", name="低估值高股息 · 港股市值版", status="watch", markets=["HK"],
                principle="PE_TTM > 0 且 ≤12，PB > 0 且 ≤1.5，TTM股息率 ≥5%，港股上市股份市值 ≥390亿港元。",
                source="东方财富港股财务指标 + 腾讯价格交叉验证；项目价值与红利规则",
                params={**meta["params"], "min_market_val": 39e9, "market_value_field": "hk_market_val"},
                cloud_note="免费云端港股数据，观察中。采用港股上市股份市值，非流通市值；与本机版分开追踪。美股暂未覆盖。",
                fundamentals=deepcopy(summary))

    def required_fields(params):
        return ["pe_ttm_ratio", "pb_ratio", "dividend_ratio_ttm", "hk_market_val"]

    def run(df, params):
        hits = value_dividend.run(df, params).copy()
        hits["market_cap_basis"] = "hk_listed"
        if not hits.empty:
            hits["reason"] += f"，港股市值≥{params['min_market_val'] / 1e8:g}亿港元（观察版）"
        return hits

    return SimpleNamespace(META=meta, required_fields=required_fields, run=run)
