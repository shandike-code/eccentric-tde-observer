# 内层精度诊断轮次：8 张 map + 2 轮正式反馈与逐层能量账本

run `outputs/hpc/hhe-diag-r025`，`config_sha256 = af2d1f1570c0733f839370d92fa9b6c6ae0455f83d648f1eafb6ac0ed56eb10e`。

**结论先行：三组端点的测量值在每一项上都单调改善，但两个门槛都还没到。**
本报告只报观测值与趋势方向，**不由少量点外推完成时间**。

---

## 1. 为什么要另起一个 driver

`hpc/pipeline.py` 把 `pair_ready` 当作辐射阶段的终点：map 循环在下一轮 `break`，
正式反馈跑一次，运行进入终态。从**已经达标**的种子出发，这意味着两张 map 后反馈一次、
此后内层精度不再推进。

`diagnostics/interval_diagnostic.py` **复用该模块自己的机制**（`worker`、`batches`、
`aggregate`、`feedback_protocol`、`verify_claims`、`block_hash`、run.lock、原子块提交），
**只改一条**：map 循环键在运行内的 map 预算上，不在 `pair_ready` 上。正式反馈改为
**每 4 张 map 主动调用一次**，每轮归档。

`src/`、`scripts/`、`hpc/` **一字未动**。

## 2. 设置

| 项 | 值 |
|---|---|
| 种子 | **Linux 态** `outputs/hpc/hhe-r025-warm/state_2.dat`，`35a4ff2f8bd1a34669be2bf41ffd99b762e9b1c9e540de724a0d725213a08b3d` |
| 播种方式 | `diagnostics/seed_from_linux_state.py`（`pipeline.prepare --seed warm` **固定**取 Mac 端点，且该清单同时是 `fetch_warm_seed.py` 的校验基准，改不得） |
| 独立缓冲 | 新 run 三个槽位自持，`hhe-r025-warm` 的态**从未被写入** |
| `maximum_maps` | 8 |
| 作业 | `TDE_MAPS=1`、`TDE_WALLTIME=04:00:00`、4 CPU / 16 G、2 worker |
| 监督 | `diagnostics/interval_supervise.py --max-jobs 8`（分离、`PPID=1`；import `hpc/supervise.py` 的 `scontrol_state`/`job_id`/`CONTINUE`） |

## 3. 八张 map

| map | 作业 | residual | boundary_l1 | boundary_bolometric | 墙钟 s | 节点 |
|---|---|---|---|---|---|---|
| 1 | 63199 | 2.054378e-04 | 3.6249e-06 | 2.5700e-06 | 665 | anode18 |
| 2 | 63216 | 2.038208e-04 | 3.3995e-06 | 2.5030e-06 | 671 | — |
| 3 | 63218 | 2.022243e-04 | 3.1939e-06 | 2.4455e-06 | 644 | — |
| 4 | 63226 | 2.006466e-04 | 3.0117e-06 | 2.3966e-06 | 652 | — |
| 5 | 63257 | 1.990872e-04 | 2.8514e-06 | 2.3554e-06 | 778 | — |
| 6 | 63267 | 1.975452e-04 | 2.7040e-06 | 2.3212e-06 | 762 | — |
| 7 | 63277 | 1.960205e-04 | 2.5777e-06 | 2.2934e-06 | 873 | — |
| 8 | 63283 | **1.945105e-04** | 2.4815e-06 | 2.2712e-06 | 850 | — |

全部 76/76 块、非负、有限、峰值 RSS 3500–3505 MiB（« 6144 MiB 资源门）。
8 张全部达标（`residual < 2.5e-4`、两个边界门 `< 1e-3`）。

**相邻收缩比 ≈ 0.9922 / 张**（cold 那轮是 0.946 / 张）。规律一致：**越接近不动点收缩越慢**。

## 4. 三轮反馈的账本对照

`Q` 为净加热（负 = 净冷却）；`dt·Q/ρ` 与旧气体热能同为 erg/g。

| 端点 | 加热指标 atomic | formal | 失败层 | 缺口/旧气体热能 | `dt·Q/ρ` |
|---|---|---|---|---|---|
| warm (1,2) | 6.631653e-03 | 6.631676e-03 | 16 / 14 | 0.5255 / 0.4904 | −1.6655e+13 |
| **第1轮 (3,4)** | **6.417382e-03** | 6.417407e-03 | 14 / 13 | 0.3865 / 0.3524 | −1.5138e+13 |
| **第2轮 (7,8)** | **6.196344e-03** | 6.196369e-03 | **9 / 9** | **0.2516 / 0.2185** | −1.3665e+13 |
| 门 | 1e-3 | 1e-3 | — | — | — |

率门始终通过：`photoionization` 1.9243e-4 → 1.8587e-4 → **1.7956e-4**（门 1e-3）；
`total_recombination` 1.7712e-7 → 1.7028e-7 → **1.6372e-7**。

**每一项都单调改善，无一例外。**

### 第 2 轮最严重层（cell 96，previous）完整账本

| 量 | 值 |
|---|---|
| 旧气体热能 | 1.0918e+13 erg/g |
| 新电离能 | 1.4415e+13 erg/g |
| Δ电离能 | **−1.1423e+03 erg/g**（相对 7.9e-11） |
| `Q` | 负（净冷却） |
| `dt·Q/ρ` | **−1.3665e+13 erg/g** |
| 剩余气体热能 | **−2.7470e+12 erg/g** |

机制三轮不变：`dt·Q/ρ` 超过旧气体热能；**Δ电离能始终可忽略**。

### 加热指标：仍是相消放大，不是发散

| 端点 | `absorbed` max 相对变化 | `emitted` max 相对变化 | 净 `Q` max 相对变化 | 相消放大（中位） |
|---|---|---|---|---|
| warm (1,2) | 1.9478e-05 | **0.0** | 2.2500e-03 | 608.7 |
| 第1轮 (3,4) | 1.8930e-05 | **0.0** | 2.1697e-03 | 605.9 |
| 第2轮 (7,8) | 1.8375e-05 | **0.0** | — | 604.6 |

`emitted` **三轮都逐位不变**（发射由冻结物质态决定，各轮端点共用同一旧时间层）。
净加热的相邻变化始终是其分量变化的 ~600 倍——**超阈来自大项相消，不是数值发散**。

## 5. 失败门（三轮完全相同）

`accepted = false`；判定文件三轮一致：

```
formal_h_he_feedback_pair_passed                     True
finite_trial_accepted_as_one_nonlinear_step          False
finite_trial_rejected                                True
static_approximation_rejected_from_one_failed_trial  False   ← 单次失败不否定静态近似
dynamic_nlte_solution_accepted                       False
phase4_replacement                                   False
real_line_formation                                  False
```

11 门失败，按性质三分（**未评估的门不按通过计**）：

- 加热**实测失败** 3：`last_two_{atomic,direct,formal}_heating_pass`
- 响应**实测失败** 2：`previous/final_material_response_physical_pass`
- **未评估** 6：`population_nonnegative`、`all_residual_components_finite`、
  `inner_noise_resolved`、`candidate_{l2,mass_weighted,maximum_cell}_contraction`

`encoded_residual` 的噪声/信号比**保持未评估**，未提供替代值。

## 6. 一次真实故障：我的 driver 缺陷（已修）

第 2 轮首次提交（作业 `63283`）以 `FAILED / 1:0` 退出：

```
RuntimeError: formal feedback-pair summary lineage changed
  scripts/phase7b9_formal_feedback_pair_adapter.py:979  run_pair
```

`run_pair` 在 `feedback_summary.json` 存在且 `protocol_sha256` 不同时拒绝执行——
**这是正确的血缘守卫**，防的是把上一轮的结论冒充成这一轮。缺陷在我：`archive_round`
只**复制**归档、没清走原件，第 2 轮撞上第 1 轮残留。

修正：归档改为**搬移**（`os.replace` / `shutil.move`），并在每轮开始前先挪走 run 根目录里的陈旧工件。
新增断言「归档必须清空 run 根目录」的测试。

**监督器在这个失败上按设计停止、未盲目重试**（`finished_jobs` 记录 `63283 FAILED 1:0`）。
第 2 轮经修复后由手工提交的作业 `63399` 完成（`wall_s = 2290`），无二次故障。

## 7. 本轮**确立**与**未确立**

**确立：**

1. 从已达标端点继续推内层精度，**每一项指标都单调改善**：residual 2.054e-4→1.945e-4、
   加热指标 6.632e-3→6.196e-3、失败层 16→9、缺口/旧气体热能 0.5255→0.2516、`|dt·Q/ρ|` 1.6655e13→1.3665e13。
2. 失败机制三轮不变：深层净冷却超出旧气体热能，**Δ电离能三轮都可忽略**（~1.1e3 erg/g 对 1.4e13）。
3. 加热指标超阈三轮都由**大项相消放大**（~605×）产生，`emitted` 三轮逐位不变，不是发散。
4. 收缩比 ≈0.9922/张，且**越接近不动点越慢**——这与 cold 轮的 0.946/张一致。

**未确立（不得当作结论）：**

1. **不能外推完成时间。** 只有三组端点，且加热门距阈值仍有 **6.2 倍**；缺口虽在收缩，
   但按几何衰减永远到不了零，是否会真正穿零**无法从三个点判定**。
2. **内层噪声是否主导——仍未评估**（该门因响应异常从未求值）。
3. **两类未满足条件是否同源——仍未确立。** 加热指标是全场分布，物理域失败集中在深层局部，
   两者空间上不重合，但这不足以判定无关。
4. **静态近似是否有效——未触及**（判定文件自身拒绝该推论）。

## 8. 未做的事（有意）

未裁剪、未 floor、未 `nan_to_num`、未改物理 dt、未改任何阈值、未改能量定义、
未覆盖任何终态、未盲目重试。`hpc/pipeline.py`、`hpc/supervise.py`、`hpc/job.sbatch`
与 `src/`、`scripts/` 全部未改。

## 9. 交付物

| 文件 | 内容 |
|---|---|
| `diagnostics/interval_diagnostic.py` | 超 `pair_ready` 的 map + 周期性反馈驱动 |
| `diagnostics/interval.sbatch` | 作业包装（镜像 `hpc/job.sbatch` 的环境与信号处理） |
| `diagnostics/interval_supervise.py` | 顺序监督器（共享 `hpc/supervise.py` 的终态判定） |
| `diagnostics/seed_from_linux_state.py` | 从 Linux 态播种 |
| `diagnostics/material_energy_ledger.py` | 逐层能量账本 + 指标分解 |
| `tests/test_interval_diagnostic.py`、`tests/test_material_energy_ledger.py` | 16 项测试，全通过 |
| `outputs/hpc/hhe-diag-r025/feedback-round{1,2}/` | 每轮的 `material_energy_ledger.json`、`round_summary.json`、两个反馈 NPZ、协议与清单 |
| `outputs/hpc/hhe-diag-r025/state.json` | 8 张 map 的完整历史与两轮摘要 |

原 `hhe-r025-warm` 与 `hhe-r025`（cold）**均原样保留**。
