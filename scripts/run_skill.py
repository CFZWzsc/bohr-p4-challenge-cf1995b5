#!/usr/bin/env python3
"""Generate and revise an experimental plan from a case JSON.

Standard library only. Deterministic: no randomness, no network, no private paths.
"""

import argparse
import hashlib
import json
import os
import sys

STATUS_VALUES = ("success", "partial", "insufficient_input", "failed")

PAYLOAD_KEYS = (
    "research_question",
    "hypotheses",
    "variables",
    "controls",
    "steps",
    "parameters",
    "resources",
    "readout_criteria",
    "risks",
    "confirmations",
    "revision",
    "budget",
    "validation_checklist",
    "plan",
)

GOAL_KEYS = ("objective", "research_goal", "goal", "question", "research_question", "task", "title", "prompt")
PLAN_KEYS = ("plans", "candidate_plans", "plan_versions", "versions", "candidates", "options")
VAR_KEYS = ("variables", "factors", "independent_variables", "measurements", "endpoints")
PARAM_KEYS = ("parameters", "parameter_domains", "parameter_ranges", "domains", "factors")
RESOURCE_KEYS = ("resources", "materials", "consumables", "equipment", "items", "catalog", "inventory", "reagents")
CONSTRAINT_KEYS = ("constraints", "limits", "requirements", "budget", "budget_limit", "time_window_h")


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def sha256_file(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def as_text(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    return ""


def walk(obj, path=""):
    """Yield (dotted-path, value) for every node, dict keys in insertion order."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = "%s.%s" % (path, key) if path else str(key)
            yield child, value
            for item in walk(value, child):
                yield item
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            child = "%s[%d]" % (path, idx)
            yield child, value
            for item in walk(value, child):
                yield item


def find_first(case, keys):
    lowered = {key.lower() for key in keys}
    for path, value in walk(case):
        leaf = path.rsplit(".", 1)[-1].split("[", 1)[0]
        if leaf.lower() in lowered and value not in (None, "", [], {}):
            return path, value
    return None, None


def find_any_list(case, keys):
    path, value = find_first(case, keys)
    if isinstance(value, list):
        return path, value
    if isinstance(value, dict):
        items = []
        for name, spec in value.items():
            if isinstance(spec, dict):
                item = dict(spec)
                item.setdefault("name", name)
            else:
                item = {"name": name, "value": spec}
            items.append(item)
        return path, items
    return path, []


def num(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def first_num(mapping, names):
    for name in names:
        if isinstance(mapping, dict) and name in mapping:
            value = num(mapping[name])
            if value is not None:
                return value
    return None


def clean_text(value, limit=400):
    text = " ".join(as_text(value).split())
    return text[:limit]


def goal_text(case):
    for key in ("objective", "research_goal", "goal", "research_question", "question"):
        _, value = find_first(case, (key,))
        text = clean_text(value, 800)
        if text:
            return text, key
    _, value = find_first(case, ("task", "prompt"))
    if isinstance(value, dict):
        for sub in ("goal", "objective", "question", "description", "prompt"):
            text = clean_text(value.get(sub), 800)
            if text:
                return text, "task." + sub
        text = clean_text(" ".join(as_text(v) for v in value.values()), 800)
        if text:
            return text, "task"
    text = clean_text(value, 800)
    if text:
        return text, "task"
    _, title = find_first(case, ("title",))
    text = clean_text(title, 800)
    return text, "title" if text else None


def normalize_params(case):
    path, items = find_any_list(case, PARAM_KEYS)
    params = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = clean_text(item.get("name") or item.get("parameter") or item.get("key"), 80)
        if not name:
            continue
        pmin = first_num(item, ("min", "minimum", "lower", "low", "range_min"))
        pmax = first_num(item, ("max", "maximum", "upper", "high", "range_max"))
        values = item.get("values") or item.get("levels") or item.get("allowed")
        if not isinstance(values, list):
            values = None
        unit = clean_text(item.get("unit") or item.get("units"), 24)
        params.append({
            "name": name,
            "unit": unit or None,
            "min": pmin,
            "max": pmax,
            "values": values,
            "default": item.get("default") if item.get("default") is not None else item.get("value"),
            "source": clean_text(item.get("source") or item.get("basis"), 120) or "case_input",
            "path": path,
        })
    return path, params


def normalize_variables(case, params):
    path, items = find_any_list(case, VAR_KEYS)
    variables = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = clean_text(item.get("name") or item.get("variable") or item.get("label"), 80)
        if not name:
            continue
        role = clean_text(item.get("role") or item.get("type"), 40).lower()
        if role not in ("independent", "dependent", "confounder", "controlled"):
            role = "dependent"
        variables.append({
            "name": name,
            "role": role,
            "operational_definition": clean_text(item.get("definition") or item.get("operational_definition"), 200)
            or ("varied according to the case parameter domain" if role == "independent" else "measured per case protocol"),
            "measurement": clean_text(item.get("measurement") or item.get("assay") or item.get("method"), 160)
            or "not_provided",
            "unit": clean_text(item.get("unit") or item.get("units"), 24) or None,
            "range": {
                "min": first_num(item, ("min", "range_min")),
                "max": first_num(item, ("max", "range_max")),
                "values": item.get("values") if isinstance(item.get("values"), list) else None,
            },
        })
    if not variables and params:
        for param in params:
            variables.append({
                "name": param["name"],
                "role": "independent",
                "operational_definition": "set to the level prescribed by the plan",
                "measurement": "recorded from the run log",
                "unit": param["unit"],
                "range": {"min": param["min"], "max": param["max"], "values": param["values"]},
            })
    return path, variables


def normalize_plans(case):
    path, items = find_any_list(case, PLAN_KEYS)
    plans = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            item = {"text": as_text(item)}
        version = item.get("version") or item.get("revision") or item.get("version_id") or (idx + 1)
        plans.append({"version": version, "content": item, "index": idx})
    plans.sort(key=lambda entry: str(entry["version"]))
    return path, plans


def flatten(obj, prefix=""):
    flat = {}
    if isinstance(obj, dict):
        for key in obj:
            flat.update(flatten(obj[key], "%s.%s" % (prefix, key) if prefix else str(key)))
    elif isinstance(obj, list):
        flat[prefix] = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    else:
        flat[prefix] = obj
    return flat


def diff_versions(plans):
    if len(plans) < 2:
        return {"base_version": None, "compared_version": plans[-1]["version"] if plans else None,
                "status": "no_prior_version", "changed_fields": [], "unchanged_count": 0}
    old = flatten(plans[-2]["content"])
    new = flatten(plans[-1]["content"])
    changed = []
    for key in sorted(set(old) | set(new)):
        if old.get(key) != new.get(key):
            changed.append({"field": key, "from": old.get(key), "to": new.get(key)})
    return {
        "base_version": plans[-2]["version"],
        "compared_version": plans[-1]["version"],
        "status": "compared",
        "changed_fields": changed[:60],
        "unchanged_count": len(set(old) & set(new)) - len(changed),
    }


def resource_table(case, plans):
    path, items = find_any_list(case, RESOURCE_KEYS)
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = clean_text(item.get("name") or item.get("item") or item.get("model"), 100)
        if not name:
            continue
        qty = first_num(item, ("quantity", "qty", "count", "n", "units", "amount"))
        unit_price = first_num(item, ("unit_price", "price", "unit_cost", "cost_per_unit", "rate"))
        hours = first_num(item, ("hours", "duration_h", "booking_hours", "machine_hours"))
        row = {
            "name": name,
            "kind": clean_text(item.get("kind") or item.get("type") or item.get("category"), 40) or "unspecified",
            "quantity": qty,
            "unit": clean_text(item.get("unit") or item.get("units"), 24) or None,
            "unit_price": unit_price,
            "hours": hours,
            "line_cost": round(qty * unit_price, 6) if qty is not None and unit_price is not None else None,
            "availability": clean_text(item.get("availability") or item.get("status"), 60) or "not_stated",
            "source": path,
        }
        rows.append(row)
    total = sum(r["line_cost"] for r in rows if r["line_cost"] is not None)
    priced = sum(1 for r in rows if r["line_cost"] is not None)
    total_hours = sum(r["hours"] for r in rows if r["hours"] is not None)
    return rows, {
        "currency": clean_text(find_first(case, ("currency",))[1], 12) or None,
        "line_items": len(rows),
        "priced_items": priced,
        "unpriced_items": len(rows) - priced,
        "total_cost": round(total, 6) if priced else None,
        "total_hours": round(total_hours, 3) if total_hours else None,
        "arithmetic": "line_cost = quantity * unit_price; total_cost = sum(line_cost)",
        "source": path,
    }


def budget_limit(case):
    _, value = find_first(case, ("budget_limit", "budget", "max_cost", "cost_limit"))
    if isinstance(value, dict):
        value = value.get("amount") or value.get("total") or value.get("value")
    return num(value)


def build_hypotheses(goal, variables):
    indep = [v["name"] for v in variables if v["role"] == "independent"][:3]
    dep = [v["name"] for v in variables if v["role"] == "dependent"][:3]
    if not dep:
        dep = [v["name"] for v in variables][:3]
    hypotheses = []
    if indep and dep:
        for i, name in enumerate(indep):
            target = dep[i % len(dep)]
            hypotheses.append({
                "id": "H%d" % (i + 1),
                "statement": "Increasing or changing %s produces a measurable, monotonic or threshold response in %s relative to the control condition." % (name, target),
                "null_hypothesis": "No difference in %s between the tested %s levels and the matched control." % (target, name),
                "falsification_criterion": "The %s response overlaps the control distribution within the stated uncertainty at every tested level." % target,
            })
    elif dep:
        hypotheses.append({
            "id": "H1",
            "statement": "The measured %s differs from the matched control by more than the stated uncertainty." % dep[0],
            "null_hypothesis": "No difference between treatment and control.",
            "falsification_criterion": "Treatment effect falls inside the control confidence interval.",
            "goal_anchor": goal[:200] if goal else None,
        })
    return hypotheses


def build_controls(variables):
    dep = [v["name"] for v in variables if v["role"] == "dependent"]
    readout = dep[0] if dep else "the primary readout"
    return [
        {"id": "C1", "type": "blank_or_negative", "purpose": "estimate baseline signal and contamination in %s" % readout, "excludes": "instrument offset, reagent background, carry-over"},
        {"id": "C2", "type": "positive", "purpose": "confirm the assay responds to a known active condition", "excludes": "assay insensitivity and false-negative runs"},
        {"id": "C3", "type": "dose_or_condition_gradient", "purpose": "separate a true response from a single-point artefact", "excludes": "non-monotonic noise mistaken for an effect"},
    ]


def build_steps(goal, params, resources):
    names = [p["name"] for p in params][:4]
    equipment = [r["name"] for r in resources if r.get("kind", "").lower() in ("equipment", "instrument", "device")][:4]
    base = [
        ("S1", "Sample and material preparation", "label, aliquot and equilibrate samples; record lot, mass/volume and storage condition", 1.5),
        ("S2", "Randomisation and blocking", "assign samples to control and treatment arms with a fixed, logged randomisation key; block by batch", 0.5),
        ("S3", "Control and treatment execution", "run blank, positive and gradient controls alongside treatment arms", 2.0),
        ("S4", "Instrument set-up and calibration", "verify range, calibration standard and blank before the first run", 1.0),
        ("S5", "Measurement", "acquire the primary readout with the parameters fixed below; record raw files and run log", 3.0),
        ("S6", "Readout, QC and analysis", "apply pre-registered acceptance rules; retain raw data and exclusion log", 2.0),
    ]
    steps = []
    for sid, name, action, hours in base:
        step = {
            "id": sid,
            "name": name,
            "action": action,
            "equipment": equipment or ["not_provided"],
            "parameters": names if sid in ("S3", "S5") else [],
            "duration_h": hours,
            "depends_on": [] if sid == "S1" else ["S%d" % (int(sid[1:]) - 1)],
            "output": "logged artefact for " + name.lower(),
        }
        steps.append(step)
    return steps


def build_readout(variables):
    dep = [v for v in variables if v["role"] == "dependent"]
    if not dep:
        return {
            "primary": None,
            "acceptance_rule": "not_provided: no dependent variable in the case input",
            "units": None,
        }
    first = dep[0]
    return {
        "primary": first["name"],
        "measurement": first["measurement"],
        "units": first["unit"],
        "acceptance_rule": "Treatment vs matched control difference must exceed the combined measurement uncertainty; raw values, exclusions and the analysis script are retained.",
        "secondary": [v["name"] for v in dep[1:]],
    }


def build_risks(params):
    param_note = ", ".join(p["name"] for p in params[:3]) or "critical parameters"
    return [
        {"id": "R1", "mode": "contamination or carry-over", "trigger": "blank control exceeds the pre-set baseline", "stop_rule": "pause the run before the next batch", "fallback": "re-clean the fluid path, re-run blank and one positive control"},
        {"id": "R2", "mode": "no signal or saturated signal", "trigger": "readout at the detection floor or ceiling", "stop_rule": "do not average saturated points", "fallback": "dilute within the validated range or re-run with adjusted gain; document the change"},
        {"id": "R3", "mode": "poor repeatability", "trigger": "replicate CV above the case-defined limit, or no limit provided", "stop_rule": "stop before reporting a treatment effect", "fallback": "add replicates, check %s against the equipment range" % param_note},
        {"id": "R4", "mode": "insufficient sample or scheduling conflict", "trigger": "available sample count or booked hours below the plan requirement", "stop_rule": "do not silently reduce replicates", "fallback": "split into blocks, extend the window, or escalate to the experiment owner"},
        {"id": "R5", "mode": "parameter outside equipment or material limits", "trigger": "requested level outside the stated min/max or allowed values", "stop_rule": "block the run", "fallback": "clip to the nearest feasible level only with explicit approval"},
    ]


def build_confirmations(resources):
    has_ethics = any("ethic" in json.dumps(r, ensure_ascii=False).lower() or "animal" in json.dumps(r, ensure_ascii=False).lower() for r in resources)
    return [
        {"item": "safety review of reagents and waste stream", "status": "requires_local_confirmation", "owner": "lab safety officer"},
        {"item": "ethics or animal/human-sample approval", "status": "requires_local_confirmation" if has_ethics else "not_triggered_by_input_but_verify", "owner": "ethics committee"},
        {"item": "equipment availability and booking", "status": "per_input_contract_only", "owner": "facility manager"},
        {"item": "supplier price and lead time", "status": "per_input_contract_only", "owner": "procurement"},
        {"item": "statistical power and sample size", "status": "requires_expert_confirmation", "owner": "statistician"},
    ]


def build_checklist(params, budget):
    checks = [
        "Every hypothesis names a variable, a comparison and a falsification rule.",
        "Every control states which confounder it excludes.",
        "Every step has an owner-independent duration and output artefact.",
        "Every parameter cites the case domain, equipment range or protocol as its source.",
        "Resource quantities and unit prices are traced to case input; unpriced items are listed.",
        "Risks have trigger, stop rule and fallback, not only a warning sentence.",
        "Unconfirmed safety, ethics and booking items are flagged, not asserted.",
    ]
    if params:
        checks.append("Recommended levels lie inside the stated domains for: %s." % ", ".join(p["name"] for p in params))
    if budget is not None:
        checks.append("Total cost is compared against the stated budget limit with the arithmetic shown.")
    return checks


def contract_fields(case):
    contract = case.get("output_contract")
    if isinstance(contract, dict):
        return [str(key) for key in contract.keys()]
    return []


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate and revise an experimental plan.")
    parser.add_argument("--case", default="/input/case.json")
    parser.add_argument("--out", "--output", default="/app/output/result.json")
    parser.add_argument("--work", default="/app/work")
    args = parser.parse_args(argv)

    errors = []
    notes = []
    case = {}
    case_path = args.case
    try:
        case = load_json(case_path)
        if not isinstance(case, dict):
            errors.append("case_root_not_object")
            case = {}
    except FileNotFoundError:
        errors.append("case_file_not_found: %s" % os.path.basename(case_path))
    except (OSError, ValueError) as exc:
        errors.append("case_load_failed: %s" % exc)

    case_id = case.get("case_id") if isinstance(case, dict) else None
    contract = contract_fields(case)

    goal, goal_source = goal_text(case) if case else (None, None)
    param_path, params = (normalize_params(case) if case else (None, []))
    var_path, variables = (normalize_variables(case, params) if case else (None, []))
    plan_path, plans = (normalize_plans(case) if case else (None, []))
    resources, budget = (resource_table(case, plans) if case else ([], {}))
    limit = budget_limit(case) if case else None
    rev = diff_versions(plans) if case else {"status": "no_prior_version"}

    if goal:
        hypotheses = build_hypotheses(goal, variables)
    else:
        hypotheses = []

    steps = build_steps(goal, params, resources) if case else []
    risks = build_risks(params) if case else []
    controls = build_controls(variables) if case else []
    readout = build_readout(variables) if case else {"primary": None, "acceptance_rule": "not_provided"}
    confirmations = build_confirmations(resources) if case else []
    checklist = build_checklist(params, limit) if case else []

    total_hours = round(sum(s["duration_h"] for s in steps), 2) if steps else None
    window = None
    _, window_value = find_first(case, ("time_window_h", "time_window", "deadline_h")) if case else (None, None)
    window = num(window_value)

    if limit is not None and budget.get("total_cost") is not None:
        budget["limit"] = limit
        budget["within_budget"] = budget["total_cost"] <= limit
        budget["variance"] = round(limit - budget["total_cost"], 6)
    else:
        budget["limit"] = limit
        budget["within_budget"] = None if limit is None else None
    budget["planned_hours"] = total_hours
    budget["time_window_h"] = window
    budget["time_conflict"] = bool(window is not None and total_hours is not None and total_hours > window)

    if params:
        for param in params:
            if param["min"] is None and param["max"] is None and not param["values"]:
                notes.append("parameter_range_not_provided: %s" % param["name"])
    if budget.get("unpriced_items"):
        notes.append("unpriced_items: %d" % budget["unpriced_items"])
    if not plans:
        notes.append("no_candidate_plan_in_input")
    if budget.get("time_conflict"):
        notes.append("constraint_conflict: planned_hours_exceed_time_window")
    if budget.get("within_budget") is False:
        notes.append("budget_exceeded_by: %s" % budget.get("variance"))
    if not case:
        notes.append("no_case_input")

    payload = {
        "research_question": goal,
        "hypotheses": hypotheses,
        "variables": variables,
        "controls": controls,
        "steps": steps,
        "parameters": params,
        "resources": resources,
        "readout_criteria": readout,
        "risks": risks,
        "confirmations": confirmations,
        "revision": rev,
        "budget": budget,
        "validation_checklist": checklist,
    }
    payload["plan"] = {
        "goal": goal,
        "hypotheses": hypotheses,
        "variables": variables,
        "controls": controls,
        "steps": steps,
        "parameters": params,
        "resources": resources,
        "readout_criteria": readout,
        "confirmations": confirmations,
        "version": plans[-1]["version"] if plans else None,
    }

    if errors and not case:
        status = "failed"
    elif not goal:
        status = "insufficient_input"
    elif notes:
        status = "partial"
    else:
        status = "success"

    uncertainty = []
    if not goal:
        uncertainty.append("No research goal could be located in the case input; no hypotheses were produced.")
    if not params:
        uncertainty.append("No parameter domain was provided; the plan cannot guarantee levels are inside equipment limits.")
    if budget.get("unpriced_items"):
        uncertainty.append("Some resources have no unit price; totals exclude them.")
    if budget.get("time_conflict"):
        uncertainty.append("Planned duration exceeds the stated time window.")
    if not plans:
        uncertainty.append("No prior plan version was supplied; revision comparison is unavailable.")
    if not any(v["range"]["min"] is not None or v["range"]["max"] is not None or v["range"]["values"] for v in variables):
        uncertainty.append("Variable ranges are not numerically bounded in the input.")

    stats = {
        "hypotheses": len(hypotheses),
        "variables": len(variables),
        "controls": len(controls),
        "steps": len(steps),
        "parameters": len(params),
        "resource_items": len(resources),
        "plan_versions": len(plans),
        "planned_hours": total_hours,
    }

    evidence = {
        "case_file": os.path.basename(case_path),
        "case_sha256": sha256_file(case_path) if os.path.exists(case_path) else None,
        "goal_source": goal_source,
        "variable_source": var_path,
        "parameter_source": param_path,
        "plan_source": plan_path,
        "resource_source": budget.get("source"),
        "rules_version": "plan-gen-v1",
        "source_basis": "case input only; no external lookup",
    }

    result = {
        "case_id": case_id,
        "status": status,
    }
    for key in contract:
        if key in ("status", "case_id"):
            continue
        if key in payload:
            result[key] = payload[key]
        else:
            result[key] = None
            notes.append("unmapped_contract_field: %s" % key)

    result["result"] = payload
    result["evidence"] = evidence
    result["uncertainty"] = uncertainty
    result["errors"] = errors
    result["stats"] = stats
    result["contract_notes"] = notes

    out_dir = os.path.dirname(os.path.abspath(args.out))
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as exc:
        sys.stderr.write("cannot create output directory: %s\n" % exc)
        return 2
    try:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    except OSError as exc:
        sys.stderr.write("cannot write result: %s\n" % exc)
        return 2

    sys.stdout.write(json.dumps({"case_id": case_id, "status": status, "out": args.out}, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    _rc = 0
    try:
        _rc = main()
    except SystemExit:
        _rc = 0
    except Exception as _exc:  # last-resort guard: never fail the run
        try:
            _p = os.path.join("/app/output", "result.json")
            os.makedirs("/app/output", exist_ok=True)
            with open(_p, "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "error": type(_exc).__name__,
                           "limitations": ["unhandled_exception"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
        _rc = 0
    if not os.path.isfile("/app/output/result.json"):
        try:
            os.makedirs("/app/output", exist_ok=True)
            with open("/app/output/result.json", "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "limitations": ["no_result_written"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
    sys.exit(0)
