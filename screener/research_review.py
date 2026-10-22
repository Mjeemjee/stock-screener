"""Read-only research explanations; the frozen evaluation engine remains authoritative."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path

from screener import factor_research as research
from screener import research_signals as signals
from screener.research_lab import reprice

VERSION = "research-review-v1"
CARD_FIELDS = {"version", "evidence", "failure_condition", "data_risks"}
PROPOSAL_FIELDS = {"name", "op_type", "hypothesis", "change", "expected", "expression", "filters", "market", "parent_id"}


def validate_card(card):
    if not isinstance(card, dict) or set(card) != CARD_FIELDS or type(card["version"]) is not int or card["version"] != 1:
        raise ValueError("Research card must use version 1 and the declared fields")
    for key in CARD_FIELDS - {"version"}:
        if not isinstance(card[key], str) or not 1 <= len(card[key].strip()) <= 400:
            raise ValueError("Research card needs evidence, failure condition and data risks (1-400 characters)")
    return card


def feature_names(spec):
    def visit(expr):
        if expr["op"] == "feature":
            return {expr["name"]}
        if expr["op"] == "neg":
            return visit(expr["arg"])
        return set().union(*(visit(arg) for arg in expr["args"]))
    return sorted(visit(spec["expression"]) | {clause["feature"] for clause in spec["filters"]})


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def complete(row):
    return row.get("due") is True and finite(row.get("benchmark_pct")) and all(
        row.get(key, {}).get("complete") is True and finite(row[key].get("return_pct"))
        for key in ("branch", "parent", "pool"))


def stress_return(row, cost):
    basket = row["branch"]
    holdings = basket.get("holdings", [])
    if type(basket.get("count")) is not int or basket["count"] != len(holdings):
        return None
    for hit in holdings:
        if hit.get("status") == "no_trade":
            continue
        if hit.get("status") != "matured" or not all(finite(hit.get(k)) and hit[k] > 0 for k in ("entry_price", "exit_price")):
            return None
    value = reprice(basket, cost)
    return value if finite(value) else None


def summarize(program, observations, rules):
    rows = sorted((r for r in observations if r["trial_id"] == program["id"]), key=lambda r: r["entry_date"])
    if any(r.get("definition_hash", program["definition_hash"]) != program["definition_hash"] for r in rows):
        raise ValueError("Review rows belong to a different frozen definition")
    dates = [r["entry_date"] for r in rows]
    duplicate = len(dates) != len(set(dates))
    due = [r for r in rows if r.get("due") is True]
    # Conflicting or repeated cohorts must not inflate explanatory statistics.
    paired = [] if duplicate else [r for r in rows if complete(r)]
    average = lambda values: sum(values) / len(values) if values else None
    returns = [r["branch"]["return_pct"] for r in paired]
    excess = [r["branch"]["return_pct"] - r["benchmark_pct"] for r in paired]
    delta = [r["branch"]["return_pct"] - r["parent"]["return_pct"] for r in paired]
    stressed = [stress_return(r, rules["stress_cost_bps"]) for r in paired]
    stress = average([value - row["benchmark_pct"] for value, row in zip(stressed, paired)]) if paired and all(finite(v) for v in stressed) else None
    independent, last_exit = 0, 0
    for row in paired:
        if row["entry_date"] >= last_exit:
            independent += 1
            last_exit = row["exit_date"]
    summary = {"total": len(rows), "pending": len(rows) - len(due), "due": len(due),
               "paired": len(paired), "missing": sum(not complete(r) for r in due), "duplicate": duplicate,
               "independent": independent, "wins": sum(v > 0 for v in returns),
               "losses": sum(v < 0 for v in returns), "flat": sum(v == 0 for v in returns),
               "beat_parent": sum(v > 0 for v in delta), "beat_benchmark": sum(v > 0 for v in excess),
               "cash": sum(r["branch"].get("count") == 0 for r in paired),
               "mean_return_pct": average(returns), "mean_delta_pp": average(delta),
               "mean_excess_pp": average(excess), "stress_excess_pp": stress,
               "worst_period_pct": min(returns) if returns else None}
    return summary, rows


def program_review(program, observations, rules):
    values, rows = summarize(program, observations, rules)
    card = program.get("discovery", {}).get("research_card")
    if card is not None:
        validate_card(card)
    checks = []

    def check(key, label, passed, detail):
        checks.append({"id": key, "label": label, "status": "pending" if passed is None else "pass" if passed else "fail", "detail": detail})

    n, due = values["paired"], values["due"]
    check("integrity", "期次不重复", not values["duplicate"], "同一入场日只计一期；发现重复时不汇总成绩。")
    check("coverage", "到期成绩是否齐全", None if not due else values["missing"] / due <= 1 - rules["min_coverage"] + 1e-12,
          f"到期 {due} 期，缺少完整配对 {values['missing']} 期；缺价不补零、不重新分配。")
    check("sample", "完整样本是否够首个关卡", None if n < min(rules["checkpoints"]) else True,
          f"完整配对 {n} 期，首个固定关卡 {min(rules['checkpoints'])} 期。")
    check("independent", "是否经历足够多的不重叠时段", None if not n else values["independent"] >= rules["min_independent_periods"],
          f"按原协议不重叠计数为 {values['independent']}，要求至少 {rules['min_independent_periods']}；这不是完全独立的统计证明。")
    baseline = "同期父策略" if program.get("parent_id") else "同期研究池等权"
    for key, label in (("mean_delta_pp", "是否优于" + baseline), ("mean_excess_pp", "是否优于同期指数"),
                       ("stress_excess_pp", "成本加大后是否仍优于指数")):
        value = values[key]
        check(key, label, None if value is None else value > 0,
              "尚无可计算的完整证据。" if value is None else f"平均差额 {value:.2f} 个百分点；不代表未来保证。")
    worst = values["worst_period_pct"]
    check("risk", "最差一期是否守住原底线", None if worst is None else worst >= rules["worst_period_floor_pct"],
          f"原底线 {rules['worst_period_floor_pct']}%；最差一期不是账户最大回撤。")
    latest = program.get("assessments", [])[-1:]
    uncertainty = latest[0].get("gates", {}).get("uncertainty") if latest else None
    check("uncertainty", "原固定关卡是否排除了部分偶然性", uncertainty if type(uncertainty) is bool else None,
          "只读取原关卡的修正后改善下界，不重新挑选有利的样本。")
    if values["duplicate"]:
        headline = "期次有重复，先核对档案，不判断成绩。"
    elif not n:
        headline = "尚无完整配对结果，不能判断新想法是否有效。"
    elif values["mean_return_pct"] > 0 and values["mean_excess_pp"] <= 0:
        headline = "目前赚了钱，但平均仍落后指数，不能算选股成功。"
    elif values["mean_return_pct"] < 0:
        headline = "目前扣费后仍亏损；即使优于对照，也不等于赚钱。"
    elif values["mean_delta_pp"] <= 0:
        headline = "目前没有比同期对照更好，继续按原关卡验证。"
    else:
        headline = "目前有改善迹象；样本、成本和原固定关卡仍需一起看。"
    return {"program_id": program["id"], "definition_hash": program["definition_hash"],
            "evidence_hash": research.digest({"rows": rows, "assessments": program.get("assessments", []),
                                              "definition": program["definition_hash"], "rules": rules, "version": VERSION}),
            "card": {"origin": "frozen" if card else "legacy", "hypothesis": program["hypothesis"],
                     "change": program["change"], "expected": program["expected"], "features": feature_names(program),
                     "evidence": card["evidence"] if card else "本实验未单独冻结依据卡；保留原始假设，不事后补写成预先声明。",
                     "failure_condition": card["failure_condition"] if card else "沿用创建时固定关卡；不为旧实验事后补设新的失败条件。",
                     "data_risks": card["data_risks"] if card else "仅使用登记的量价因子；不代表已有新闻、财报或资金流数据。"},
            "summary": values, "checks": checks, "headline": headline,
            "assessment_hash": latest[0]["hash"] if latest else None}


def enrich(report):
    result = deepcopy(report)
    result["research_review"] = {"version": VERSION, "mode": "read_only", "source_generated_at": report["generated_at"],
        "source_engine_version": report["engine_version"], "source_policy_hash": report["policy_hash"],
        "programs": [program_review(p, report["observations"], report["policy"]) for p in report["programs"]]}
    return result


def start_with_card(directory, proposal, actor, now=None):
    """Freeze the explanatory card inside the existing hashed discovery record."""
    if not actor.strip() or not isinstance(proposal, dict) or set(proposal) - (PROPOSAL_FIELDS | {"research_card"}):
        raise ValueError("Invalid owner proposal")
    card = validate_card(proposal.get("research_card"))
    if proposal.get("op_type") not in ("add_feature", "feature_interaction", "negate_signal", "new_factor_family"):
        raise ValueError("Unsupported research operation")
    state = research.load_state(directory)
    parent = next((p for p in state["programs"] if p["id"] == proposal.get("parent_id")), None)
    if proposal.get("parent_id") and not parent:
        raise ValueError("Unknown proposal parent")
    now = now or datetime.now(timezone.utc)
    program = research.register(state, proposal, proposal.get("market"), now,
                                {"kind": "owner_proposal", "actor": actor, "research_card": deepcopy(card)}, parent)
    research.log(state, "started_by_owner", now, program["id"], actor=actor)
    research.save_state(directory, state)
    return program


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=research.PUBLIC_OUT)
    parser.add_argument("--archive-dir", type=Path, default=research.ARCHIVE_DIR)
    parser.add_argument("--history-dir", type=Path, default=research.HISTORY_DIR)
    parser.add_argument("--action-env", action="store_true")
    args = parser.parse_args()
    if args.action_env:
        decision, actor = os.environ.get("RESEARCH_DECISION", ""), os.environ.get("RESEARCH_ACTOR", "")
        if decision == "start":
            raw = os.environ.get("RESEARCH_PROPOSAL", "")
            if len(raw) > 16000:
                raise ValueError("Proposal too large")
            start_with_card(args.archive_dir, json.loads(raw), actor)
        else:
            research.owner_action(args.archive_dir, decision, actor, os.environ.get("RESEARCH_PROGRAM"), os.environ.get("RESEARCH_EVIDENCE"))
        research.run(args.archive_dir, args.history_dir, args.output)
    report = json.loads(args.output.read_text(encoding="utf-8"))
    research.write_json(args.output, enrich(report))


if __name__ == "__main__":
    main()
