# 实验方案生成与修订（包说明）

把研究目标与资源契约转成可检验假设、可执行步骤、预算与时间核算、风险清单，并在多版候选方案之间给出字段级修订差异。以下说明输入、口径、输出与限制，均对应 `SKILL.md` 与 `scripts/run_skill.py` 的实际行为。

## 输入字段

| 字段 | 含义 | 必需 |
|---|---|---|
| `case_id` | 案例标识，原样回填 | 是 |
| `output_contract` | 需要回填的输出键及其类型 | 是 |
| `objective` | 研究目标文本；缺失时状态降为 `insufficient_input` | 建议 |
| `parameters[]` | 参数名、`min`/`max`、`unit`、`source`；用于变量操作化与步骤绑定 | 否 |
| `variables[]` | 变量名、`role`（independent/dependent/confounder/controlled）、`measurement`、`unit` | 否 |
| `plans[]` | 版本化候选方案（`version`、体积、重复数、时长、温度等）；按 `version` 排序，最新版为比较基线 | 否 |
| `resources[]` | 资源名、`kind`（consumable/equipment）、`quantity`、`unit`、`unit_price`、设备 `hours` | 否 |
| `budget_limit` | 预算上限（金额） | 建议 |
| `currency` | 币种 | 否 |
| `time_window_h` | 可用排期窗口（小时） | 建议 |
| `min_replicates` | 最少生物学重复数（供复核方使用，脚本原样不推导） | 否 |

字段缺失不会被补造：价格缺失标 `unit_price_not_provided`，参数无范围标 `range_not_provided`，无目标文本则状态为 `insufficient_input`。

## 生成口径

1. 从目标生成 1–3 条可证伪假设，每条含自变量、因变量、比较方向与判据。
2. 变量按角色操作化，取值范围只继承输入参数域或设备量程。
3. 对照固定给出空白/阴性、阳性、剂量或条件梯度三类，并注明各自排除的混杂。
4. 步骤按“样品准备→分组/对照→处理→测量→判读”生成，绑定设备、参数与依赖关系；若输入含候选方案，最新版的体积、温度、重复数、时长会写进处理与测量步骤。
5. 成本按目录行汇总：`line_cost = quantity * unit_price`，`total_cost = Σ line_cost`；设备时长取 `hours` 字段。
6. 与上一版本做字段级差异（`revision`），列出采纳/未采纳的字段变化。
7. 风险给触发条件、止损点与替代路径；安全、伦理、排期、报价单列为待本地确认项。

## 阈值与约束

- 预算：`total_cost <= budget_limit` 时 `budget.within_budget = true`，否则为 `false` 并在 `contract_notes` 记录超出额。
- 时间：`planned_hours <= time_window_h` 时无冲突，否则 `budget.time_conflict = true`，`status` 降为 `partial`。
- 约束互相冲突（时间窗小于计划时长、预算不足）时不会静默裁剪，只标注冲突并保留最短可行路径。
- 含任一未决提示（未标价的资源、缺失参数范围、无候选方案、约束冲突）时 `status = partial`；全部齐全才为 `success`。
- 本包不设“正确答案”阈值；`min_replicates` 等案例内明示约束由复核方对照输出执行判断。

## 输出字段

`result.json` 顶层：

| 字段 | 含义 |
|---|---|
| `case_id` / `status` | 案例标识与状态（`success` / `partial` / `insufficient_input` / `failed`） |
| `output_contract` 各键 | 若与内部载荷同名则填真实内容，否则 `null` 并在 `contract_notes` 说明 |
| `plan` | 汇总视图：目标、假设、变量、对照、步骤、参数、资源、读出标准、确认项、版本号 |
| `hypotheses` / `variables` / `controls` | 假设、变量表、三类对照 |
| `steps` | 有序步骤，含设备、参数、时长、依赖与产出物 |
| `resources` | 资源行及行成本 |
| `readout_criteria` | 主读出指标、单位与接受规则 |
| `risks` | 风险条目（触发、止损、替代） |
| `revision` | 版本差异或 `no_prior_version` |
| `budget` | 总成本、上限、差额、计划时长、时间窗与冲突标记 |
| `confirmations` | 待本地确认的安全/伦理/排期/报价/统计功效 |
| `validation_checklist` | 自检项 |
| `result` | 上述内容的完整载荷 |
| `evidence` | 输入文件名与哈希、命中键路径、规则版本 |
| `uncertainty` / `errors` / `stats` / `contract_notes` | 不确定项、真实错误、计数汇总、未映射字段说明 |

同目录还会写出 `report.md`、`validation.json`、`provenance.json`（人类可读报告、自检结果、输入哈希）。

## 依赖与限制

- 依赖：Python 3.8+，仅标准库；不联网、不读私有路径、不查数据库。
- 不生成供应商报价、真实库存或伦理批号；这些只能来自输入契约。
- 不做统计功效计算，除非输入提供效应量与方差；样本量只给下限提示。
- 不把候选方案中的宣传性描述当作已验证事实。
- 案例与示例均为合成数据，输出不代表真实实验室条件。

## 单次运行

在包根目录执行：

```bash
python scripts/run_skill.py --case examples/demo-case/case.json --out ./demo-output/result.json --work ./demo-output/work
```

一次运行即产出完整交付物，不存在第二阶段；同一输入重复运行字节一致。

## 复核与基准

`bench/` 内含两个紧预算/紧时间合成案例、金标准、朴素基线对比脚本与协议说明；`templates/plan_checklist.md` 提供可直接复用的方案复核清单。
