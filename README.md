# Runtime contract

Bohrium Playground Period 4 submission — challenge `challenge-cf1995b5` (track: `experimental-design`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable pipeline and all supporting documents. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `experiment-plan-generate-and-revise`
- Summary: Use when an experimental-design case asks to turn a research goal and its resource constraints into a runnable, reviewable experiment plan, or to revise an existing versioned plan; run scripts/run_skill.py to emit a contract-preserving result.json with hypotheses, variables, controls, steps, parameters, resources, risks and revision diffs.

## Contents

| File |
|------|
| `SKILL.md` |
| `examples/demo-case/case.json` |
| `examples/quickstart.md` |
| `scripts/publish_artifacts.py` |
| `scripts/run_skill.py` |
| `README.md` |

## How to run

```bash
python scripts/sk_entry.py --input /input --work /app/work --out /app/output
```

A single deterministic pass reads `/input`, computes the deliverable and writes a
contract-complete `/app/output/result.json` plus the human-readable review files
described in `SKILL.md`. The same input always produces byte-identical output; no
network access is used, and fields the materials cannot support are reported
explicitly instead of being left empty.
