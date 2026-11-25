#!/usr/bin/env python3
"""Deterministic benchmark for the experiment-plan skill.

Compares the skill output with a naive fixed-plan baseline on two synthetic
tight-budget / tight-window cases. Standard library only: no network, no
timestamps, no absolute paths in the written artefacts.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BENCH_DIR)
CASE_DIR = os.path.join(BENCH_DIR, "cases")
GOLD_DIR = os.path.join(BENCH_DIR, "gold")
SKILL = os.path.join(ROOT, "scripts", "run_skill.py")
PROTOCOL = "plan-bench-v1"

ECHO_PATTERNS = {
    "culture_volume_ml": r"culture_volume_ml=([0-9.]+)",
    "replicates": r"replicates=([0-9.]+)",
    "duration_h": r"duration_h=([0-9.]+)",
}
CONSTRAINT_KEYS = ("budget", "time_window", "min_replicates", "controls_and_risks")


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def round6(value):
    if value is None:
        return None
    return round(float(value), 6)


def run_skill(case_path):
    """Run the skill in a throw-away directory and return its result.json."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "result.json")
        work = os.path.join(tmp, "work")
        proc = subprocess.run(
            [sys.executable, SKILL, "--case", case_path, "--out", out, "--work", work],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        if proc.returncode != 0 or not os.path.isfile(out):
            raise RuntimeError("skill run failed for %s (exit %d): %s"
                               % (os.path.basename(case_path), proc.returncode, proc.stderr.strip()[:400]))
        return load_json(out)


def plan_cost(plan, resources):
    """Price a plan with one rule shared by the skill and the baseline.

    consumables: catalog quantity * unit price
    equipment:   plan duration_h * unit price (the price is a per-hour rate)
    """
    consumable = 0.0
    equipment = 0.0
    for item in resources:
        unit_price = float(item.get("unit_price") or 0.0)
        kind = str(item.get("kind") or "").lower()
        if kind == "equipment":
            hours = plan.get("duration_h")
            if hours is None:
                continue
            equipment += float(hours) * unit_price
        else:
            consumable += float(item.get("quantity") or 0.0) * unit_price
    return {
        "consumable": round6(consumable),
        "equipment": round6(equipment),
        "total": round6(consumable + equipment),
        "rule": "consumables = sum(quantity*unit_price); equipment = duration_h*unit_price",
    }


def baseline_plan(case):
    """Naive baseline: adopt the first (pre-revision) plan verbatim."""
    plans = case.get("plans") or []
    first = plans[0] if plans else {}
    return {
        "label": "naive_fixed_plan_v%s" % first.get("version"),
        "version": first.get("version"),
        "culture_volume_ml": first.get("culture_volume_ml"),
        "replicates": first.get("replicates"),
        "duration_h": first.get("duration_h"),
        "arms": first.get("arms"),
    }


def skill_plan(result, case):
    """Recover the plan the skill adopted, from the echoed step constraints."""
    payload = result.get("result") or {}
    steps = payload.get("steps") or []
    joined = " ".join(str(step.get("action") or "") for step in steps)
    parsed = {}
    for key, pattern in ECHO_PATTERNS.items():
        match = re.search(pattern, joined)
        parsed[key] = float(match.group(1)) if match else None
    version = (payload.get("plan") or {}).get("version")
    reference = None
    for item in case.get("plans") or []:
        if str(item.get("version")) == str(version):
            reference = item
    echoed = parsed["replicates"] is not None and parsed["duration_h"] is not None
    for key in ("culture_volume_ml", "replicates", "duration_h"):
        if parsed[key] is None and reference is not None:
            parsed[key] = reference.get(key)
    return {
        "label": "skill_selected_plan_v%s" % version,
        "version": version,
        "culture_volume_ml": parsed["culture_volume_ml"],
        "replicates": parsed["replicates"],
        "duration_h": parsed["duration_h"],
        "arms": (reference or {}).get("arms"),
        "constraint_echoed_in_steps": echoed,
    }


def deliverables(result):
    payload = result.get("result") or {}
    plan = payload.get("plan")
    items = {
        "plan": isinstance(plan, dict) and bool(plan),
        "steps": isinstance(payload.get("steps"), list) and len(payload.get("steps") or []) > 0,
        "risks": isinstance(payload.get("risks"), list) and len(payload.get("risks") or []) > 0,
        "budget": isinstance(payload.get("budget"), dict) and payload["budget"].get("total_cost") is not None,
    }
    items["single_run_complete"] = all(items.values())
    return items


def evaluate(plan, payload, case, gold):
    limits = gold["constraints"]
    costs = plan_cost(plan, case.get("resources") or [])
    controls = payload.get("controls") or []
    risks = payload.get("risks") or []
    checks = {
        "budget": costs["total"] <= limits["budget_limit"],
        "time_window": plan.get("duration_h") is not None
        and float(plan["duration_h"]) <= limits["time_window_h"],
        "min_replicates": plan.get("replicates") is not None
        and float(plan["replicates"]) >= limits["min_replicates"],
        "controls_and_risks": len(controls) >= 3 and len(risks) >= 4,
    }
    return {
        "cost": costs["total"],
        "cost_breakdown": costs,
        "duration_h": round6(plan.get("duration_h")),
        "replicates": round6(plan.get("replicates")),
        "culture_volume_ml": round6(plan.get("culture_volume_ml")),
        "controls": len(controls),
        "risks": len(risks),
        "constraint_checks": checks,
        "constraints_satisfied": sum(1 for key in CONSTRAINT_KEYS if checks[key]),
        "constraints_unmet": sum(1 for key in CONSTRAINT_KEYS if not checks[key]),
    }


def benchmark_case(case_path, gold_path):
    case = load_json(case_path)
    gold = load_json(gold_path)
    if case.get("case_id") != gold.get("case_id"):
        raise RuntimeError("case/gold id mismatch: %s" % os.path.basename(case_path))
    for field in ("budget_limit", "time_window_h", "min_replicates"):
        if case.get(field) != gold["constraints"].get(field):
            raise RuntimeError("gold %s does not match case %s" % (field, os.path.basename(case_path)))

    result = run_skill(case_path)
    payload = result.get("result") or {}

    skill_plan_entry = skill_plan(result, case)
    skill_metrics = evaluate(skill_plan_entry, payload, case, gold)
    skill_metrics["plan"] = skill_plan_entry
    skill_metrics["status"] = result.get("status")
    skill_metrics["deliverables"] = deliverables(result)

    base_payload = {"controls": [], "risks": []}
    base_metrics = evaluate(baseline_plan(case), base_payload, case, gold)
    base_metrics["plan"] = baseline_plan(case)
    base_metrics["status"] = "not_applicable"
    base_metrics["deliverables"] = {"plan": True, "steps": False, "risks": False,
                                    "budget": False, "single_run_complete": False}

    gain = {
        "constraints_satisfied_delta": skill_metrics["constraints_satisfied"] - base_metrics["constraints_satisfied"],
        "constraints_unmet_delta": skill_metrics["constraints_unmet"] - base_metrics["constraints_unmet"],
        "cost_delta": round6(base_metrics["cost"] - skill_metrics["cost"]),
        "hours_delta": round6(base_metrics["duration_h"] - skill_metrics["duration_h"]),
        "skill_strictly_better": (
            skill_metrics["constraints_satisfied"] > base_metrics["constraints_satisfied"]
            and skill_metrics["constraints_unmet"] < base_metrics["constraints_unmet"]
        ),
    }
    return {
        "case_id": case["case_id"],
        "case_file": "bench/cases/" + os.path.basename(case_path),
        "gold_file": "bench/gold/" + os.path.basename(gold_path),
        "gold": gold["constraints"],
        "skill": skill_metrics,
        "baseline": base_metrics,
        "gain": gain,
    }


def render_report(payload):
    lines = []
    lines.append("# 实验方案基准报告")
    lines.append("")
    lines.append("协议版本：`%s`。本报告由 `bench/run_bench.py` 生成，内容只依赖案例、金标准与两次运行输出。" % PROTOCOL)
    lines.append("")
    lines.append("## 公平协议")
    lines.append("")
    lines.append("- 案例：`bench/cases/*.json`，合成且自洽；金标准：`bench/gold/*.json`，只取案例中明示的约束。")
    lines.append("- 两侧使用同一条成本规则：耗材按目录 `quantity*unit_price`，设备按方案 `duration_h*unit_price`（单价为每小时费率）。")
    lines.append("- 技能侧：运行 `scripts/run_skill.py`，从其输出中恢复所选方案版本、重复数与时长；约束判定只比较数值与计数，不做人工解释。")
    lines.append("- 基线：直接采用案例中的第 1 版方案（未核算预算与排期的默认方案），不生成对照、风险与预算核对。")
    lines.append("- 判定：预算 `cost <= budget_limit`、时间 `duration_h <= time_window_h`、重复 `replicates >= min_replicates`、")
    lines.append("  对照/风险 `controls >= 3 且 risks >= 4`（协议级要求，非案例约束；技能在 SKILL.md 中承诺，基线不提供）。")
    lines.append("- 每个案例独立运行一次，运行目录为临时目录并在结束后删除；不使用网络、不使用随机数。")
    lines.append("")
    lines.append("## 指标定义")
    lines.append("")
    lines.append("- 约束满足数：上述 4 条约束中通过的条数；未满足约束数为 4 减去满足数。")
    lines.append("- 单次运行交付：一次运行是否同时产出 `plan`、`steps`、`risks`、`budget`（且 `budget.total_cost` 非空）。")
    lines.append("- 成本、时长、重复数均按该方案自身声明的字段计算，两侧规则完全一致。")
    lines.append("")
    lines.append("## 逐例结果")
    lines.append("")
    for case in payload["cases"]:
        lines.append("### `%s`" % case["case_id"])
        lines.append("")
        lines.append("- 金标准：预算 %s、时间窗 %s h、最少重复 %s。"
                     % (case["gold"]["budget_limit"], case["gold"]["time_window_h"], case["gold"]["min_replicates"]))
        lines.append("")
        lines.append("| 方法 | 方案 | 成本 | 时长(h) | 重复 | 对照 | 风险 | 预算 | 时间 | 重复 | 对照/风险 | 满足 | 未满足 |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for name, key in (("技能", "skill"), ("基线", "baseline")):
            entry = case[key]
            checks = entry["constraint_checks"]
            mark = lambda flag: "是" if flag else "否"
            lines.append("| %s | v%s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                name, entry["plan"].get("version"), entry["cost"], entry["duration_h"], entry["replicates"],
                entry["controls"], entry["risks"],
                mark(checks["budget"]), mark(checks["time_window"]), mark(checks["min_replicates"]),
                mark(checks["controls_and_risks"]),
                entry["constraints_satisfied"], entry["constraints_unmet"],
            ))
        lines.append("")
        lines.append("- 技能 `status`：`%s`；单次运行交付完整：`%s`。"
                     % (case["skill"]["status"], str(case["skill"]["deliverables"]["single_run_complete"]).lower()))
        lines.append("- 增益：约束满足数 +%s，未满足约束数 %+d，成本减少 %s，时长减少 %s。"
                     % (case["gain"]["constraints_satisfied_delta"], case["gain"]["constraints_unmet_delta"],
                        case["gain"]["cost_delta"], case["gain"]["hours_delta"]))
        lines.append("")

    summary = payload["summary"]
    lines.append("## 汇总")
    lines.append("")
    lines.append("| 指标 | 技能 | 基线 |")
    lines.append("|---|---|---|")
    lines.append("| 约束满足数合计 | %s | %s |" % (summary["skill_constraints_satisfied"], summary["baseline_constraints_satisfied"]))
    lines.append("| 未满足约束数合计 | %s | %s |" % (summary["skill_constraints_unmet"], summary["baseline_constraints_unmet"]))
    lines.append("| 成本合计 | %s | %s |" % (summary["skill_total_cost"], summary["baseline_total_cost"]))
    lines.append("| 全部案例严格更优 | %s | - |" % str(summary["skill_strictly_better_on_all_cases"]).lower())
    lines.append("")
    lines.append("## 复现")
    lines.append("")
    lines.append("```bash")
    lines.append("python bench/run_bench.py")
    lines.append("```")
    lines.append("")
    lines.append("脚本重写 `bench/bench_metrics.json` 与 `bench/bench_report.md`；同一输入重复运行字节一致。")
    lines.append("")
    return "\n".join(lines)


def main():
    cases = sorted(
        name for name in os.listdir(CASE_DIR)
        if name.endswith(".json")
    )
    results = []
    for name in cases:
        case_path = os.path.join(CASE_DIR, name)
        gold_path = os.path.join(GOLD_DIR, name)
        if not os.path.isfile(gold_path):
            raise RuntimeError("missing gold file for %s" % name)
        results.append(benchmark_case(case_path, gold_path))

    summary = {
        "cases": len(results),
        "skill_constraints_satisfied": sum(r["skill"]["constraints_satisfied"] for r in results),
        "baseline_constraints_satisfied": sum(r["baseline"]["constraints_satisfied"] for r in results),
        "skill_constraints_unmet": sum(r["skill"]["constraints_unmet"] for r in results),
        "baseline_constraints_unmet": sum(r["baseline"]["constraints_unmet"] for r in results),
        "skill_total_cost": round6(sum(r["skill"]["cost"] for r in results)),
        "baseline_total_cost": round6(sum(r["baseline"]["cost"] for r in results)),
        "skill_strictly_better_on_all_cases": all(r["gain"]["skill_strictly_better"] for r in results),
    }
    payload = {"protocol_version": PROTOCOL, "cases": results, "summary": summary}

    metrics_path = os.path.join(BENCH_DIR, "bench_metrics.json")
    with open(metrics_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")

    report_path = os.path.join(BENCH_DIR, "bench_report.md")
    with open(report_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_report(payload))

    sys.stdout.write("cases=%d skill_satisfied=%d baseline_satisfied=%d strict_win=%s\n" % (
        summary["cases"], summary["skill_constraints_satisfied"],
        summary["baseline_constraints_satisfied"],
        str(summary["skill_strictly_better_on_all_cases"]).lower(),
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
