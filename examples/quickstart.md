# Quickstart — experimental plan generator

Python 3.10+ standard library only; no network access.

## 1. Run the bundled demo

```bash
python scripts/run_skill.py --case examples/demo-case/case.json --out result.json
```

Expected on the demo case (byte-identical across runs):

- `status` = `success`
- `steps` = S1…S6; the measurement step carries `duration_h` taken from the
  equipment `hours` field and `duration_source` names that field; steps whose
  duration is not stated in the input keep `duration_h = null`
- `budget.planned_hours` sums only the stated durations (10.0 h here, from the
  shaker booking) and `time_conflict` compares it with `time_window_h`
- `hypotheses[*].statement` names the dependent variable, never the parameter
  itself, and quotes the case goal
- `revision.changed_fields` lists the diff between the last two plans

## 2. Your own case

Minimal `case.json`:

```json
{
  "case_id": "my-plan",
  "goal": "Maximise titre of protein X within 12 h",
  "parameters": [{"name": "induction_temp_c", "min": 16, "max": 37, "unit": "C"}],
  "variables": [
    {"name": "induction_temp_c", "role": "independent", "unit": "C", "range": {"min": 16, "max": 37}},
    {"name": "titre_mg_l", "role": "dependent", "measurement": "SDS-PAGE", "unit": "mg/L"}
  ],
  "plans": [{"version": "v1", "culture_volume_ml": 50, "induction_temp_c": 30, "replicates": 3}],
  "resources": [{"name": "shaker", "kind": "equipment", "hours": 10, "quantity": 1, "unit_price": 0}],
  "budget_limit": 500,
  "time_window_h": 24
}
```

```bash
python scripts/run_skill.py --case case.json --out result.json
```

`budget.unit_price`/`line_cost` are computed only when both quantity and price
are present; otherwise the item is reported as unpriced instead of guessed.
Missing or unreadable input still writes `result.json` with `status` set and
exit code 0.
