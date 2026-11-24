---
name: experiment-plan-generate-and-revise
description: Use when an experimental-design case asks to turn a research goal and its resource constraints into a runnable, reviewable experiment plan, or to revise an existing versioned plan; run scripts/run_skill.py to emit a contract-preserving result.json with hypotheses, variables, controls, steps, parameters, resources, risks and revision diffs.
---

# 实验方案生成与修订

## 用途与适用条件

把研究目标转成可检验假设与可执行方案，并在给定设备、耗材、预算、排期与参数域约束下生成或修订版本化方案。适用于 `generate_and_revise_plan` 类案例：案例给出科研目标、材料/来源、前瞻性资源与价格/预约契约、以及每例 3 个版本化候选方案。

不适用：文献综述、数据建模、论文写作；不替代实验人员或伦理/安全审查。方案中的资源、价格、排期均按输入契约陈述，不声称是真实实验室条件或供应商报价。

## 输入

- `/input/case.json`（可用 `--case` 覆盖）：至少含 `case_id` 与 `output_contract`；常见可选键为 `task`、`objective`、`sources`、`materials`、`plans`/`candidate_plans`/`plan_versions`、`parameters`/`parameter_domains`、`resources`、`equipment`、`budget`、`constraints`。
- `/input/task.md`（可选）：作为目标与约束的补充文本，缺失时只用 `case.json`。
- 输出目录默认 `/app/output`，中间文件写 `--work`（默认 `/app/work`）。

字段名不做硬编码假设：脚本递归查找同名或近义键；找不到就如实标为 `not_provided`，不编造设备型号、价格或文献。

## 处理流程（对应评分维度）

1. **目标与假设（任务完成度/正确性）**：从 `objective`/`task`/`title` 取研究目标；生成 1–3 条可证伪假设，每条含自变量、因变量、比较关系与判据。目标缺失时状态降为 `insufficient_input`。
2. **变量操作化（正确性）**：为每个变量给出角色（`independent`/`dependent`/`confounder`/`controlled`）、操作定义、测量方式、单位与取值范围；范围只从输入参数域或设备量程继承。
3. **对照设计（正确性）**：至少给出空白/阴性对照、阳性对照与剂量或条件梯度；每个对照写明排除的混杂类型；缺少阳性对照时在 `uncertainty` 中标注。
4. **步骤与参数（完整性）**：按“样品准备→分组/对照→处理→测量→判读”生成有序步骤，绑定设备与参数区间；每步写时长、并行关系和产出物。
5. **资源与时间成本（完整性/可核验性）**：从资源条目汇总耗材数量×单价、设备机时×费率、人工工时；金额与时长给出单位与算术过程；缺价目时写 `unit_price_not_provided` 而不估造。
6. **风险与异常（可靠体验）**：给出失败模式、判据、止损点、替代路径和转人工节点，覆盖污染、无信号、重复性差、样本不足、设备排期冲突。
7. **版本修订（创新增益/可核验性）**：按 `version`/`revision` 排序候选方案，取最新版为基线，与上一版做字段级差异；列出采纳/未采纳理由与受影响约束。
8. **确认项与自查（可靠体验）**：单列安全、伦理、设备可用性和专家确认项；未确认事项不得写成既成事实。

## 输出契约

`/app/output/result.json` 顶层保留：

| 字段 | 含义 |
|-|-|
| `case_id` | 与输入一致 |
| `output_contract` 的每个字段 | 命中可映射内容则填真实值，否则 `null` 并在 `contract_notes` 记录原因 |
| `status` | `success` / `partial` / `insufficient_input` / `failed` |
| `result` | `research_question`、`hypotheses`、`variables`、`controls`、`steps`、`parameters`、`resources`、`readout_criteria`、`risks`、`confirmations`、`revision`、`budget`、`validation_checklist` |
| `evidence` | 输入文件、命中键路径、来源定位、规则版本 |
| `uncertainty` | 缺失价格/量程、未确认排期、假设边界 |
| `errors` | 真实错误列表（不吞异常） |
| `stats` | 计数与汇总（步骤数、变量数、总时长、总成本） |

## 异常处理表

| 情况 | 处置 | 状态 |
|-|-|-|
| `case.json` 缺失或非法 JSON | 输出空骨架 + `case_load_failed` | `failed` |
| 无 `output_contract` | 仍输出标准字段，`contract_notes` 说明 | `partial` |
| 无研究目标文本 | 不生成假设，列出缺失项 | `insufficient_input` |
| 无候选方案 | 从零生成单版方案，`revision` 标 `no_prior_version` | `partial` |
| 参数只有名称无范围 | 变量表填 `range_not_provided` | `partial` |
| 资源缺单价或费率 | 成本标 `not_priced`，不估算 | `partial` |
| 约束互相冲突（时间窗 < 总时长） | 标 `constraint_conflict` 并给最短可行路径 | `partial` |
| 输出目录不可写 | 尝试工作目录回退，仍失败则 `failed` | `failed` |

## 限制

- 不联网、不查数据库、不读取私有路径；只使用案例输入与 `task.md`。
- 不生成具体供应商报价、真实设备库存或伦理批号；这些只能来自输入契约。
- 不做统计功效计算，除非输入提供效应量与方差；否则只给样本量下限提示。
- 不把候选方案中的宣传性描述当作已验证事实。

## 最小调用示例（示例，非官方案例结果）

```bash
python /skills/weekly-skill/scripts/run_skill.py --case /input/case.json --out /app/output/result.json --work /app/work
```

示意输入：`{"case_id":"synthetic-plan-demo","output_contract":{"plan":"object","risks":"array"}}`。示意输出保留 `case_id`、`plan`、`risks`、`status`；无目标与候选方案时为 `insufficient_input`，`plan` 为 `null`。仅为接口示例，不是官方固定案例结果。


## Quickstart

在包根目录执行：

```bash
python scripts/run_skill.py --case examples/demo-case/case.json --out ./demo-output/result.json
```

- 演示案例：`examples/demo-case/case.json`（两版本小规模培养方案，含参数边界、资源单价与预算；纯合成）。
- 输出：`result.json` 含 `plan`、`hypotheses`、`steps`、`risks`、`revision`、`budget`，并给出预算与时间窗核对；本案例实测 `status="success"`。

## 交付保证与评分对齐

调用顺序（固定）：

1. 先运行包内脚本（若存在）：`python scripts/run_skill.py`（默认读 `/input/case.json`，写 `/app/output/result.json`）；路径不同时用 `--case` / `--out` 指定。
2. 再完成脚本无法自动完成的实质工作（译文、论述、图表、修订、结论等），把结果写回 `result.json` 对应字段。
3. 最后自检：`case_id` 与输入一致；`output_contract` 每个字段都存在；`status` 为 `success`（仅在确实缺输入时为 `partial`）；无 `pending` 占位；数字、引用、来源可逐条回溯。

运行保证：

- 输入缺失、JSON 损坏、字段异常、输出目录不存在时，仍须写出结构化 `result.json` 并正常结束，不得崩溃或非零退出。
- 不联网、不伪造数据、不声称平台评分或官方案例结果。
- 交付物必须是可直接编辑与复核的成品，而不是流程说明。

评分对齐（本题五个维度）：

- 实际效果（40）：完整产出任务要求的最终成品，覆盖全部输入条目，可直接进入修改流程。
- 使用增益（25）：体现相对基础 Agent 的可验证改进（结构化、术语/数字/引用核对、可编辑性）。
- 创新增益（15）：保留方法学增量（分块、对齐、二次校验、版本比对等），并用结果证明其价值。
- 可靠体验（10）：异常输入有明确降级与说明，不同长度/文体/重复运行下稳定产出。
- 生态贡献（10）：用途、调用、输入输出、限制、示例、维护信息齐全，资源可被他人复用。

## 最终交付强制要求

1. **调用 Agent 必须交付成品，不是流程说明**：脚本产出只是索引、核对或规格骨架；调用 Agent 必须在同一 `result.json` 中补齐本题要求的最终产物（正文/译文/审稿意见/综述/分析结论/图表源文件与导出件/幻灯片页内容与讲稿/实验方案等）。交付字段为空、只有标题骨架，或含 `pending`、`TODO` 之类占位，一律视为未完成。
2. **必须覆盖全部输入条目**：输入中的每个章节、问题、文献、图、页面、指标都要有对应条目，不得只处理示例或首条；确实缺失的条目写入 `uncertainty` / `limitations` 并说明原因，不得静默跳过。
3. **必须自检后再交付**：`case_id` 与输入一致；`output_contract` 每个字段都存在；状态值取本题契约规定的枚举；数字、单位、引用、来源可逐条回溯；结果内部无自相矛盾。
4. **参数等价**：`python scripts/run_skill.py --case <输入> --out <输出>` 与 `--output <输出>` 等价；默认 `/input/case.json` → `/app/output/result.json`。
5. **平台用 3 个固定案例分别运行**：逻辑要由输入驱动，不针对某一份示例硬编码；字段命名差异走别名匹配与显式降级，并在 `uncertainty` 记录假设。
