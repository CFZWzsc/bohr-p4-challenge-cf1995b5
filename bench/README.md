# 实验方案基准（bench）

本目录用两个合成但自洽的案例，对比技能输出与“朴素固定方案”基线在预算、时间窗、重复数与交付完整性上的差异。目的是给出可复核的过程证据，而不是评分声明。

## 公平协议

1. 每个案例只运行一次 `scripts/run_skill.py`，输出写入临时目录，运行结束后删除；两次正式复跑分别落在独立临时目录中。
2. 两侧使用同一条成本规则，由 `bench/run_bench.py` 的 `plan_cost` 实现：
   - 耗材：目录中的 `quantity * unit_price`；
   - 设备：方案声明的 `duration_h * unit_price`（案例把设备单价定义为每小时费率）；
   - 该规则对技能与基线逐字相同，不因方法不同而换算法。
3. 金标准 `bench/gold/*.json` 只收录案例正文中明示的约束（`budget_limit`、`time_window_h`、`min_replicates`），不采用技能输出反推，也不补充案例未声明的隐含阈值。脚本启动时会断言金标准三项数值与案例字段逐一相等。
4. 技能侧不使用任何内部字段作为“答案”，只用它声明的方案版本、重复数与时长，以及输出的对照/风险条目计数；判定只做数值与计数比较。
5. 基线不使用技能输出，也不读取技能代码；它只从案例读入。

## 基线定义

基线 = 直接采用案例 `plans` 中的第 1 版（`version` 最小）方案，原样执行：

- 沿用该版本的 `culture_volume_ml`、`replicates`、`duration_h`；
- 不生成假设、对照、步骤与风险；
- 不核对预算与时间窗（这正是要被检验的“朴素”点）。

第 1 版在两例中都是未核算预算与排期的默认方案（50 mL、3 重复、26 h / 30 h），第 2 版是修订后的小时窗、4 重复方案。

## 指标定义

| 指标 | 定义 |
|---|---|
| `constraints_satisfied` | 4 条约束中通过的条数 |
| `constraints_unmet` | 4 条约束中未通过的条数 |
| 预算 | `plan_cost.total <= gold.constraints.budget_limit` |
| 时间窗 | `plan.duration_h <= gold.constraints.time_window_h` |
| 重复数 | `plan.replicates >= gold.constraints.min_replicates` |
| 对照/风险 | `controls >= 3` 且 `risks >= 4`；这是协议级要求（技能在 `SKILL.md` 中承诺），不属于案例金标准 |
| `deliverables` | 单次运行是否同时产出 `plan`、`steps`、`risks`、`budget`，且 `budget.total_cost` 非空 |
| `skill_strictly_better` | 约束满足数严格更高且未满足约束数严格更低 |

## 复现

在包根目录执行：

```bash
python bench/run_bench.py
```

脚本以标准库实现，通过子进程调用 `scripts/run_skill.py`（环境变量 `PYTHONDONTWRITEBYTECODE=1`、`PYTHONHASHSEED=0`），随后写入：

- `bench/bench_metrics.json`：`indent=2`、`sort_keys=True`，无时间戳与绝对路径；
- `bench/bench_report.md`：协议说明与逐例表格。

同一输入重复运行，两份文件字节一致。

## 已知边界

- 案例完全合成，不对应任何真实实验室、供应商报价或已发表结果；数字互相自洽，但不代表现实可复现性。
- 案例的候选方案只有两版，基线固定取第 1 版；不覆盖“多版本择劣”的其他朴素策略。
- 成本规则把设备单价视为每小时费率、耗材按目录数量计价，是对原始报价的简化；技能内部的 `budget.total_cost` 按目录行计价（设备按 1 件），数值可能不同，但在两例中两侧结论一致，判定不依赖该差异。
- 时间只计方案声明的 `duration_h`，不推算多步串行总时长；技能未提供的步骤时长不作推测。
- “对照/风险”计数阈值属于基准协议，不是案例约束；调整阈值会改变该项判定，但不影响预算/时间/重复三项。
- 本基准不评估统计功效、样本量合理性、设备真实可用性或伦理合规性。
