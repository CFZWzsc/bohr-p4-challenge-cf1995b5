# Runtime contract

Bohrium Playground Period 4 submission — challenge `challenge-cf1995b5` (track: `experimental-design`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable entry point and all supporting scripts. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `experiment-plan-generate-and-revise`
- Summary: Use when an experimental-design case asks to turn a research goal and its resource constraints into a runnable, reviewable experiment plan, or to revise an existing versioned plan; run scripts/run_skill.py to emit a contract-preserving result.json with hypotheses, variables, controls, steps, parameters, resources, risks and revision diffs.

## Contents

| File |
|------|
| `SKILL.md` |
| `scripts/run_skill.py` |
| `README.md` |

## How to run

```bash
python scripts/run_skill.py --case /input/case.json --output /app/output/result.json
```

The entry point is `SKILL.md`; input/output contracts, error handling and a minimal
usage example are documented there.

## Notes

- Pure Python standard library; no network access required.
- The result JSON keeps the input case id, the main results, per-item evidence,
  a run status and an uncertainty section.
