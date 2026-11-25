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

## 交付保证（单次运行）

一次 `python scripts/run_skill.py` 即产出完整交付物：`result.json`（`output_contract` 全键 + 实质内容）、`report.md`（人类可读报告）、`validation.json`（自检项与证据）、`provenance.json`（输入哈希与可复现声明）。不存在第二阶段：输入无法支持的项目写入 `uncertainty` 并说明原因，不写占位符、不留 `pending`。

- 输入缺失、JSON 损坏、字段异常时仍写出结构化 `result.json` 并以 0 退出。
- 不联网、不伪造实验数据、不声称平台评分或官方案例结果。
- 同一输入重复运行字节一致；`validation.json` 的 `all_passed` 应为 `true`。
