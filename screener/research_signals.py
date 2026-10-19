"""Typed, bounded factor expressions on completed point-in-time OHLCV panels."""
from copy import deepcopy
import json
import math

import numpy as np
import pandas as pd

from screener.factor_rank import calculate_factors

FEATURES = {
    "relative_volume": {"name": "相对成交量", "formula": "V[t] / mean(V[t-20:t])", "family": "volume"},
    "close_location": {"name": "收盘位置", "formula": "(C-L)/(H-L)", "family": "price_action"},
    "breakout": {"name": "突破幅度", "formula": "C[t]/max(H[t-20:t])-1", "family": "trend"},
    "compression": {"name": "波动收缩", "formula": "-std(r[-5:])/std(r[-20:])", "family": "volatility"},
    "reversal3": {"name": "三日反转", "formula": "1-C/C[-4]", "family": "reversal"},
    "recovery": {"name": "日内修复", "formula": "(C-O)/mean(TR[-20:])", "family": "price_action"},
    "gap": {"name": "隔夜跳空", "formula": "O/C[-2]-1", "family": "overnight"},
    "downside_stability": {"name": "下行稳定性", "formula": "-sqrt(mean(min(r,0)^2))", "family": "risk"},
    "volume_price": {"name": "量价协同", "formula": "corr(r[-20:],diff(log(V))[-20:])", "family": "volume"},
    "legacy_bias": {"name": "原有乖离趋势", "formula": "legacy bias slope", "family": "control"},
    "legacy_slope": {"name": "原有趋势斜率", "formula": "legacy slope * R2", "family": "control"},
    "legacy_efficiency": {"name": "原有趋势效率", "formula": "legacy efficiency", "family": "control"},
}


def feature(name):
    return {"op": "feature", "name": name}


SEEDS = [
    {"family": "volume_breakout", "name": "放量确认突破", "op_type": "new_factor_family",
     "hypothesis": "突破伴随相对放量和高位收盘，可能减少突破后回落。",
     "change": "独立引入相对成交量、收盘位置与突破幅度",
     "expected": "验证未来5日扣费收益是否优于同期研究池；不预设收益幅度",
     "expression": {"op": "mean", "args": [feature(n) for n in ("relative_volume", "close_location", "breakout")]},
     "filters": [{"feature": "breakout", "gte": 0}, {"feature": "relative_volume", "gte": 1.2},
                 {"feature": "close_location", "gte": 0.65}]},
    {"family": "compression_breakout", "name": "波动收缩突破", "op_type": "new_factor_family",
     "hypothesis": "短期波动收窄后出现突破，可能包含不同于平稳趋势的信息。",
     "change": "独立引入短长波动比，并结合突破与量能",
     "expected": "验证未来5日相对研究池的增益及与原有趋势因子的重复性",
     "expression": {"op": "mean", "args": [feature(n) for n in ("compression", "breakout", "relative_volume")]},
     "filters": [{"feature": "compression", "gte": -0.8}, {"feature": "breakout", "gte": 0}]},
    {"family": "short_reversal", "name": "短期超跌修复", "op_type": "new_factor_family",
     "hypothesis": "短期急跌后出现日内修复和量能变化，可能有五日反转效应。",
     "change": "独立引入三日反转、日内修复与相对成交量",
     "expected": "验证未来5日反转效果及扣费后相对研究池表现",
     "expression": {"op": "mean", "args": [feature(n) for n in ("reversal3", "recovery", "relative_volume")]},
     "filters": [{"feature": "reversal3", "gte": 0.03}, {"feature": "recovery", "gte": 0}]},
]


def validate_expression(expr, depth=0):
    if depth > 4 or not isinstance(expr, dict):
        raise ValueError("Expression must be a bounded JSON tree")
    op = expr.get("op")
    if op == "feature" and set(expr) == {"op", "name"} and expr["name"] in FEATURES:
        return
    if op == "neg" and set(expr) == {"op", "arg"}:
        validate_expression(expr["arg"], depth + 1)
        return
    if (op in ("mean", "product") and set(expr) == {"op", "args"}
            and isinstance(expr["args"], list) and 2 <= len(expr["args"]) <= 3):
        for arg in expr["args"]:
            validate_expression(arg, depth + 1)
        return
    raise ValueError("Unsupported expression operator or fields")


def validate_spec(spec):
    validate_expression(spec["expression"])
    if not isinstance(spec["filters"], list) or len(spec["filters"]) > 5:
        raise ValueError("At most five feature filters are supported")
    for clause in spec["filters"]:
        if (not isinstance(clause, dict) or clause.get("feature") not in FEATURES
                or not set(clause) <= {"feature", "gte", "lte"} or len(clause) < 2):
            raise ValueError("Invalid raw-feature filter")
        for key in ("gte", "lte"):
            if key in clause and (type(clause[key]) not in (int, float) or not math.isfinite(clause[key])
                                  or abs(clause[key]) > 1e6):
                raise ValueError("Invalid filter bound")
        if clause.get("gte", -math.inf) > clause.get("lte", math.inf):
            raise ValueError("Inverted feature filter")


def fingerprint(spec):
    def canonical(expr):
        node = deepcopy(expr)
        if "args" in node:
            node["args"] = sorted([canonical(arg) for arg in node["args"]], key=lambda x: json.dumps(x, sort_keys=True))
        if "arg" in node:
            node["arg"] = canonical(node["arg"])
        return node
    return json.dumps({"expression": canonical(spec["expression"]),
                       "filters": sorted(spec["filters"], key=lambda x: json.dumps(x, sort_keys=True))}, sort_keys=True)


def raw_features(bars):
    """Caller supplies a validated, consecutive 61-session prefix, never future bars."""
    arr = np.asarray(bars, dtype=float)
    if arr.ndim != 2 or len(arr) < 61 or arr.shape[1] < 6 or not np.isfinite(arr[:, :6]).all():
        raise ValueError("61 valid OHLCV bars required")
    o, h, l, c, v = arr[:, 1:6].T
    if np.any(np.minimum.reduce([o, h, l, c]) <= 0) or np.any(v <= 0):
        raise ValueError("Nonpositive price/volume")
    if np.any(h < np.maximum(o, c)) or np.any(l > np.minimum(o, c)):
        raise ValueError("Invalid OHLC range")
    r = np.diff(np.log(c))
    tr = np.maximum.reduce([h[1:] - l[1:], abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])])
    vol = float(np.std(r[-20:]))
    atr = float(np.mean(tr[-20:]))
    dv = np.diff(np.log(v))[-20:]
    correlation = float(np.corrcoef(r[-20:], dv)[0, 1]) if np.std(dv) > 1e-10 and vol > 1e-10 else 0.0
    legacy = calculate_factors(bars)
    result = {"relative_volume": float(v[-1] / np.mean(v[-21:-1])),
              "close_location": float((c[-1] - l[-1]) / (h[-1] - l[-1])) if h[-1] > l[-1] else 0.5,
              "breakout": float(c[-1] / max(h[-21:-1]) - 1),
              "compression": -float(np.std(r[-5:]) / vol) if vol > 1e-10 else 0.0,
              "reversal3": float(1 - c[-1] / c[-4]),
              "recovery": float((c[-1] - o[-1]) / atr) if atr > 0 else 0.0,
              "gap": float(o[-1] / c[-2] - 1),
              "downside_stability": -float(np.sqrt(np.mean(np.minimum(r[-20:], 0) ** 2))),
              "volume_price": correlation,
              **{"legacy_" + k: float(value) for k, value in (legacy or {}).items()}}
    if set(result) != set(FEATURES) or not all(math.isfinite(v) for v in result.values()):
        raise ValueError("Incomplete or nonfinite factors")
    return result


def standardize(panel):
    if not panel:
        return {}
    codes = sorted(panel)
    result = {code: {} for code in codes}
    for key in FEATURES:
        values = np.array([panel[code][key] for code in codes], dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("Missing feature values are not zero")
        values = np.clip(values, *np.quantile(values, [0.05, 0.95]))
        sigma = float(np.std(values))
        values = (values - np.mean(values)) / sigma if sigma > 1e-10 else np.zeros(len(values))
        for code, value in zip(codes, values):
            result[code][key] = float(value)
    return result


def expression_values(expr, normalized):
    validate_expression(expr)
    def value(node, row):
        if node["op"] == "feature":
            return row[node["name"]]
        if node["op"] == "neg":
            return -value(node["arg"], row)
        args = [value(arg, row) for arg in node["args"]]
        return float(np.mean(args) if node["op"] == "mean" else np.prod(args))
    codes = sorted(normalized)
    if not codes:
        return {}
    values = np.array([value(expr, normalized[code]) for code in codes], dtype=float)
    values = np.clip(values, *np.quantile(values, [0.05, 0.95]))
    sigma = float(np.std(values))
    values = (values - np.mean(values)) / sigma if sigma > 1e-10 else np.zeros(len(values))
    return {code: float(score) for code, score in zip(codes, values)}


def select(spec, panel, top_n=10):
    validate_spec(spec)
    scores = expression_values(spec["expression"], standardize(panel))
    eligible = [code for code in scores if all(
        clause.get("gte", -math.inf) <= panel[code][clause["feature"]] <= clause.get("lte", math.inf)
        for clause in spec["filters"])]
    return [{"code": code, "score": scores[code], "features": panel[code]}
            for code in sorted(eligible, key=lambda code: (-scores[code], code))[:top_n]]


def correlation(a, b, rank=True):
    codes = sorted(set(a) & set(b))
    if len(codes) < 5:
        return None
    x, y = pd.Series([a[c] for c in codes], dtype=float), pd.Series([b[c] for c in codes], dtype=float)
    if rank:
        x, y = x.rank(), y.rank()
    if x.std() < 1e-10 or y.std() < 1e-10:
        return None
    return float(x.corr(y))


def candidates(parent):
    """One interpretable new input per proposal, including genuinely new interactions."""
    used = set()
    def visit(node):
        if node["op"] == "feature":
            used.add(node["name"])
        for arg in node.get("args", []):
            visit(arg)
        if "arg" in node:
            visit(node["arg"])
    visit(parent["expression"])
    for key, info in FEATURES.items():
        if key in used or info["family"] == "control":
            continue
        for op in ("mean", "product"):
            spec = {"expression": {"op": op, "args": [deepcopy(parent["expression"]), feature(key)]},
                    "filters": deepcopy(parent["filters"]), "family": parent["family"],
                    "name": parent["name"][:30] + " + " + info["name"],
                    "op_type": "add_feature" if op == "mean" else "feature_interaction",
                    "hypothesis": f"加入{info['name']}，检验是否提供母策略之外的未来收益信息。",
                    "change": f"{op}: {key}",
                    "expected": "探索样本只用于提出假设；仅创建后的独立五日跟踪可用于评估"}
            try:
                validate_spec(spec)
            except ValueError:
                continue
            yield spec
