# 撤回：两条"小步"延续链跑错了物质候选（trial 身份错误）

## 事实

2026-09-18 09:1x，我在做"信号割线对"测量时发现 a15625-cont48 的 trial 里 `relaxation = 0.0625`。逐条核对三个量（trial 的 `relaxation`、由 `‖encoded−base‖/‖direction‖` 反推的 α、以及与固定 `MATERIAL` 的编码距离）后确认：

步长一律写成"原步长 0.125 的几分之一"，避免数字混淆：

| run | 声明的步长 | trial 实际步长 | \|enc − MATERIAL\| | 判定 |
|---|---|---|---|---|
| hhe-r025-cont64 / ext16 | 1/2（α=0.0625） | 1/2 | 0.000 | ✓ |
| small-step-a15625-20260917（原始 4 张） | 1/8（α=0.015625） | 1/8 | 0.726 | ✓ |
| **small-step-a15625-cont48**（43 张、我据以判词） | 1/8 | **1/2（α=0.0625）** | **0.000** | **✗** |
| small-step-a078125-20260917（原始 4 张） | 1/16（α=0.0078125） | 1/16 | 0.847 | ✓ |
| **small-step-a078125-cont48**（已取消） | 1/16 | **1/2（α=0.0625）** | **0.000** | **✗** |
| small-step-a00390625-20260917（今早新建） | 1/32（α=0.00390625） | 1/32 | 0.908 | ✓ |

## 根因

`operations/prepare_extension_run.py`（我写的、只继承源 run 配置）**不写 `trial_material.npz`**。初始化时 `hpc/pipeline.py::run_pipeline` 发现该文件缺失，就调用 `migrate_trial()` 复制固定的 `MATERIAL`（即 α=0.0625 候选），**静默替换**了本应延续的小步候选。

项目自己的 `operations/prepare_encoded_backtrack.py` 为防这个坑专门写了 `initialize_declared_trial()`（"Existing trial_material.npz is owned and hashed by the new declaration; pipeline initialization consumes it without invoking the old 0.0625 migration"）。我写的工具掉进了同一个坑，而我的三遍检查**只断言了 config 字段与 warm seed 身份，没有断言 trial 的 `encoded_state`**——那恰恰是定义实验本身的量。

## 撤回的结论

1. **α=1/8（0.015625）的判词作废**。`2026-09-18-small-step-verdict-not-descending.md` 里 43 张 map、10 轮、比值 1.1330 的那条链，实际跑的是 α=0.0625 候选；它只是 α=0.0625 的**第二次独立测量**，不是小步。
2. **有限差分"饱和"分析作废**。`2026-09-18-fd-saturation-and-next-step.md` 比较的两个点（signal 12.547 与 12.669）实际是**同一个物质候选**，所以"signal 与 α 无关"是同义反复，不是饱和。
3. **由此推出的步长区间（h ≳ 3e-3、α≈1/32 的判别）作废**。判据本身（信噪比 ≥10 与半步自洽）仍然成立，但当时喂进去的两个点无效。

## 仍然成立的结论

1. **α=0.0625 候选不下降**：ext16 四轮比值 1.1267/1.1260/1.1261/1.1268，且 a15625-cont48 这条"意外的第二次测量"给出 1.1330（同一候选、不同种子与历史），两者相差 0.6%，互相印证；收缩门要求 <1，稳定失败 12.6%–13.3%。
2. **α=0.03125 旁支离开物理域**（43 个单元）——该 run 由 `prepare_encoded_backtrack.py` 创建，trial 身份正确，不受此事影响。
3. **噪声底**（确定性 1e-14、跨平台 2.4e-11）与判据工具本身（`collect_encoded_ratios`、`small_step_verdict`、`finite_difference_linearity`）不受影响。
4. **α=1/32 链（a00390625）trial 正确**，仍在运行，是当前唯一有效的小步数据来源。

## 处置

1. 已停止 a078125-cont48 的监督器并 `scancel 72350`；该 run 的全部数据保留为证据，不删除。
2. a15625-cont48 已自行跑满预算并停止，数据保留。
3. **已完成**：两个无效 run 目录里写入了 `INVALID-run-notice.json`（注明原因、证据与撤回文件位置，数据保留）。
4. **已完成**：`prepare_extension_run.py` 修复并三遍检查通过（提交 5fe4611）。新增 `carry_trial()`：在写 config/state **之前**把源 trial 复制进新 run，并逐位断言 `encoded_state`/`base_encoded_state`/`finite_direction`/`base_residual` 与 `relaxation`；源缺 trial 或复制后被篡改都直接拒绝（新增两条负路径测试，合计 6 项通过）。平台的 dry-run 会打印 `source_trial` 与 `source_trial_relaxation` 供人工核对。
5. **已完成**：重做了 α=1/8 与 1/16 的正确延续链——`small-step-a15625-cont48-v2-20260918` 与 `small-step-a078125-cont48-v2-20260918`，源 run 分别是 trial 身份已验证的 `small-step-a15625-20260917`（1/8）与 `small-step-a078125-20260917`（1/16）。准备后独立复核：两条 v2 的 `encoded_state` 与 `finite_direction` 与源**逐位一致**，relaxation 分别为 0.015625 与 0.0078125。两条链已初始化（各完成第 1 张 map，R=3.02e-3 与 3.49e-3，属各自场的初始失配）并由健壮监督器驱动（作业 72419、72420）；α=1/32 链（作业 72354）继续运行。

三条链的预算均为 48 张 map、每 8 张一轮反馈，预计数小时内给出真正属于 1/8、1/16、1/32 三个步长的 `‖r(α)‖/‖r(base)‖`。

## 教训（写入操作纪律）

对候选 run 而言，"实验"就是 `trial_material.npz` 里的那个物质态。任何只校验配置、不校验 trial 的检查都不算通过三重检查；后续所有候选 run 的准备脚本都必须把
`assert array_equal(new_trial["encoded_state"], source_trial["encoded_state"])`
作为硬门，并在 `AGENTS.md` 里写明。
