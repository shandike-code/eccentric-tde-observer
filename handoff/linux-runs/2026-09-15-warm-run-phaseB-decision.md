# Linux 运行报告：warm run 与 Phase B 辐射/反馈判定

**结论：`material_trial_not_accepted`。** 辐射侧全部达标；有**两类未满足条件**
（加热稳定性、物质响应物理域）。**两者的因果关系待诊断**，本条不作因果断言。

> 更正（2026-09-15 第二轮）：本文件初稿写作「两个各自独立的根因」，那是**过度断言**。
> 诊断尚未确定两者是否共享同一原因，措辞已改为「两类未满足条件，因果关系待诊断」。

门数按性质三分（保持 fail-closed，未评估的门不按通过计）：
**3 门加热实测失败 + 2 门响应物理域失败 + 6 门未评估 = 11 门失败。**

**明确不成立的说法：** 本结果**不构成**"静态大气不存在"的证据——判定文件自身的
`static_approximation_rejected_from_one_failed_trial = False` 就拒绝了这个推论。
也**没有**任何"全盘大气升级完成"的成分（见 §5）。

---

## 1. 交接链路（GitHub Release → warm run）

仓库 `shandike-code/eccentric-tde-observer`，Release `warm-seed-2026-09-15`，10 个分片共 9.41 GiB。

| 环节 | 结果 |
|---|---|
| 远端代码更新 | 远端 main 领先本地 3 个提交（`c5b9208f` / `9e100f84` / `cfbbf112`）。用 `codeload.github.com` 取完整树比对后，仅复制 4 个新文件（3 个 `handoff/` + 1 个 `tests/`），**`src/`、`scripts/` 逐文件相同，`hpc/` 未改动**，冻结源哈希安全 |
| 分片下载 | 24 分钟。本集群 egress **封 `github.com`**（000），但 `api.github.com` 与 `release-assets.githubusercontent.com` 可达；改用 API 302 重定向绕开 |
| 逐片校验 | `handoff/fetch_warm_seed.py download` → `Verified existing part 1..10/10`，14.3 s |
| batch 拼接 | 作业 `63096`，`COMPLETED` / `0:0`，`RunTime=00:00:19` |
| **全文件 SHA** | **`5999be906b78e5478c34868e210eb3a135a579df9ff7d203badc31b37ae03e6b`**，与 `handoff/restart_manifest.json` 的 `checkpoints[0]` 逐字符一致 |
| warm run | `outputs/hpc/hhe-r025-warm`，`seed=warm`、2 worker、门槛 `2.5e-4`、`maximum_maps=4`、`config_sha256=a15f994b…` |

### 未解决的分叉（需在可访问 github.com 的一侧处理）

`1040b7b`（上个会话给 `hpc/supervise.py` 加的 `scontrol` 回退）**只存在于学校侧，远端没有**。
本集群 `sacct` 恒空，cold 夜间轮的 16 次自动接续全靠它。远端 main 的 `hpc/supervise.py` 仍是
sacct-only 版本。**直接 `git pull` 会撤掉该修复，并击穿 `hhe-r025` 的冻结源哈希。**

## 2. 两张辐射映射（新平台自检，非继承历史值）

| map | 作业 | 节点 | residual | boundary_l1 | boundary_bolometric | 映射墙钟 | 峰值 RSS |
|---|---|---|---|---|---|---|---|
| 1 | `63097` | anode17 | **2.087341e-04** | **4.1269e-06** | **2.7363e-06** | 628 s | 3500.6 MiB |
| 2 | `63117` | anode01 | **2.070752e-04** | **3.8685e-06** | **2.6474e-06** | 3587 s | 3499.4 MiB |

| 门 | 阈值 | map1 | map2 |
|---|---|---|---|
| `residual` | 2.5e-4 | 2.087e-4 ✅ | 2.071e-4 ✅ |
| `boundary_l1` | 1e-3 | 4.13e-6 ✅（242×余量） | 3.87e-6 ✅ |
| `boundary_bolometric` | 1e-3 | 2.74e-6 ✅（365×余量） | 2.65e-6 ✅ |

完整性：两张均 76/76 块、频率归属 9632 组每组恰好 1 次、强度非负、数值有限、
RSS « 6144 MiB 资源门。`pair_ready` 成立（连续两张三指标均达标）→ 流水线进入正式 H/He 反馈对。
`state_1.dat` sha256 `74819a1e6462c8ceac7e1e705c400f9f2e15a082fc4a02514df4466b82a2a1f9`。

**未解释的节点级差异**：map1 在 `anode17` 用 628 s，map2 在 `anode01` 用 3587 s（5.7×），
块墙钟从 12 s 涨到 174–229 s 且集中在前半段。cold 夜间轮在 `anode01` 上单张只要 ~725 s，
所以不是节点身份本身。**记录，不解释。**

## 3. 失败门（18 门：7 通过 / 11 失败）

### 通过（7）

`last_two_photoionization_pass`、`last_two_total_recombination_pass`、
`two_formal_feedback_states_pass`、`two_inner_radiation_residuals_pass`、
`two_boundary_spectra_pass`、`two_boundary_bolometric_pass`、`candidate_state_bytes_pass`

### 条件 A（未满足）— 加热稳定性超阈：**3 门实测失败**

| 门 | 阈值 | 实测 | 判定 |
|---|---|---|---|
| `last_two_atomic_heating_pass` | 1e-3 | **6.6317e-03** | ❌ **6.63×** |
| `last_two_direct_heating_pass` | 1e-3 | **6.6317e-03** | ❌ **6.63×** |
| `last_two_formal_heating_pass` | 1e-3 | **6.6317e-03** | ❌ **6.63×** |

对比同期通过的率门：`photoionization` 1.9243e-04（0.19×）、`recombination` 1.7712e-07。
**两个辐射态的光致电离率与复合率稳定到门的 1/5 与 1/5600，但三个加热量只稳定到门的 6.63 倍。**
三个加热值几乎相同（差在第 8 位），提示由共同成分主导。这三个门是**实测后失败**，
不是别的原因的下游；但「为什么会超阈」与「响应为何离开物理域」是否同源，**尚待诊断**。

### 条件 B（未满足）— 物质响应离开物理域：**2 门实测失败 + 6 门未评估**

两个反馈态**各自独立**抛出：

```
error_type: PhysicalDomainError
message   : specific material energy leaves no positive gas heat
```

即物质响应在某个单元上落到**正气体热能之外**。`previous` 与 `final` 两次都是如此。

以下 8 门**不是被求值后失败**，而是适配器在捕获该异常后**硬编码为 `False`**
（`scripts/phase7b9_formal_feedback_pair_adapter.py:1010-1053`）：

`previous_material_response_physical_pass`、`final_material_response_physical_pass`、
`population_nonnegative_pass`、`all_residual_components_finite_pass`、
`inner_noise_resolved_pass`、`candidate_l2_contraction_pass`、
`candidate_mass_weighted_contraction_pass`、`candidate_maximum_cell_contraction_pass`

其中前两门记录的是**异常本身**（响应未落在物理域内，实测失败）；
后六门**从未被求值**，返回 `False` 只是 fail-closed 的默认值：

- 实测失败（2）：`previous_material_response_physical_pass`、`final_material_response_physical_pass`
- 未评估（6）：`population_nonnegative_pass`、`all_residual_components_finite_pass`、
  `inner_noise_resolved_pass`、`candidate_l2_contraction_pass`、
  `candidate_mass_weighted_contraction_pass`、`candidate_maximum_cell_contraction_pass`

因此 `comparison` 里四个比值项为 `None`，`not_evaluated_reason` =
`"finite material response left the physical domain"`。**未评估的门不按通过计。**
`encoded_residual` 的噪声/信号比因此**保持未评估**，不得用任何替代值充数。

**合计：3 门加热实测失败 + 2 门响应物理域失败 + 6 门未评估 = 11 门失败。**

## 4. 反馈阶段实测资源

| 项 | previous | final |
|---|---|---|
| `rate_direct_volume_l1` | 1.7343933353318683e-12 | 1.733518817355676e-12 |
| `rate_formal_volume_l1` | 2.1870729923380326e-05 | 2.185553735609535e-05 |
| `rate_formal_global_fraction` | 7.972653703682267e-05 | 7.687160359414526e-05 |
| `maximum_parent_mirror_residual` | 2.17094779664859e-12 | 2.1562329484866154e-12 |
| 峰值 RSS | 3945.09 MiB | 3945.09 MiB |
| 累计墙钟 | 933.77 s | 927.60 s |

反馈工件：`previous_feedback.npz`（`bf8e755a…`）、`final_feedback.npz`（`a3239738…`）；
`feedback_summary.json`、`feedback.png`、`feedback/{previous,final}_manifest.json` 均落盘。
`target_material_path` 与 `encoded_residual_path` 为 `None`——物质响应未完成，故无目标物质态与残差。

## 5. 判定文件自身的边界（照抄，避免过度声称）

```
formal_h_he_feedback_pair_passed                     True    ← 反馈对本身算完了
finite_trial_accepted_as_one_nonlinear_step          False   ← 这一步没被接受
finite_trial_rejected                                True
static_approximation_rejected_from_one_failed_trial  False   ← 单次失败不否定静态近似
dynamic_nlte_solution_accepted                       False
phase4_replacement                                   False
real_line_formation                                  False
```

## 6. 现场状态

| 项 | 值 |
|---|---|
| 队列 / 监督器 | **均无**，无作业在跑，无自动续交 |
| `hhe-r025-warm` | `status=material_trial_not_accepted`，`history` 2，`active_map=None`（无半成品映射） |
| 工作态 | `state_0/1/2.dat` 各 10,099,884,032 bytes 齐全 |
| cold run `hhe-r025` | **原样保留未动**（24 张，残差 1.3072e-3，`status=radiation`） |
| warm 检查点 | `outputs/checkpoints/phase7b9k_retained_trial_map3.dat` + 10 个分片（分片保留供审计） |

## 7. 两类未满足条件与历史先例的关系

`AGENT_TASKS_ZH.md` 记载：历史 `0.125` 候选「完成了两个严格收敛辐射态和**稳定正式反馈**，
随后物质响应离开正气体热能物理域，被拒绝」。

本次 `0.0625` 候选：两个辐射态同样**通过 2.5e-4 放宽辐射门**（该门并非历史严格 `1e-4` 门），
但**正式反馈本身就不稳定**（加热 6.63×），
**且**物质响应同样离开物理域。**我们这一轮在历史失败点之前就已经失败了**——
所以不能把本次拒绝与历史 `0.125` 的拒绝当作同一回事。

## 8. 下一步（按 §阶段 D，不擅自放宽）

`AGENT_TASKS_ZH.md` 对物理域失败的规定：

> 若物理域失败：沿已声明方向做有界回溯或检查该响应闭合；不能通过裁剪、floor 或改物理步长蒙混过关。

对加热不稳定（条件 A）没有任何放宽条款——`AGENTS.md` 明确「Do not relax … feedback stability」。
`inner_noise_to_trial_signal_l2_ratio_below = 0.1` 未求值，所以**尚不能判断内层噪声是否主导**。

**未做的事（有意）：** 未裁剪、未 floor、未改物理步长、未改阈值、未启动后续阶段、未盲目重试。
