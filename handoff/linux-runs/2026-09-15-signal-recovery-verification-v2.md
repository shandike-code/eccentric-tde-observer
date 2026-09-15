# Slurm 信号与恢复实测验证（新版本 `2bec4d9`）

对象：`b5155e9`（本地信号报告）+ Mac `de8e0e9` 的合并结果 `2bec4d9`。
上一轮验证针对 `6b5349f`；诊断源码 SHA 已变，**按 Mac 报告第 3 节要求新建一次性 run**，
不改写旧 `declaration`、不用新代码续跑旧 run。

## 1. 为何必须新建 run

每个 run 的 `diagnostic_declaration.json` 固定了全部 `diagnostics/*.py|*.sbatch` 的 SHA、
git 提交与执行参数，且**不可变**。旧 run `hhe-signal-check` 声明的是 `6b5349f` 的源码哈希，
合并后源码已变，用它续跑会被声明检查拒绝——这是设计使然，不是障碍。

新 run：`outputs/hpc/hhe-signal-check-v2`
- 种子 = `hhe-diag-r025/state_2.dat`（已提交 SHA `eb4c30283322c41c…`）的副本
- `declaration` 实测：**git `2bec4d96`**，**6 个诊断源文件**，
  参数 `{maps_per_job:1, feedback_every:4, workers:2, maximum_maps:1, radiation_threshold:0.00025}`

## 2. 阶段一：运行中打断

| 时刻 | 事件 |
|---|---|
| 23:40:59 | 提交 `63687`（真 `interval.sbatch`，`TDE_MAPS=1`，墙钟 `00:30:00`） |
| 23:43:55 | 已提交 **20 块**；`scancel --batch --signal=USR1 63687` |
| 23:44:10 | **块数 22**（在飞的那一批提交完成）；**`Stop requested` 记录 1 次**；作业退出 |

- **`JobState=COMPLETED`、`ExitCode=0:0`**，`stderr` 为空
- 驱动末行 `{"operation": "map", "completed_blocks": 22, "total": 76}`
- **从发信号到作业退出约 15 秒**；此后无任何新块、无下一批 worker

这一批比上一轮更干净：上一轮信号到时恰逢最后一批判界（74/76），本轮信号落在一批**运行中**，
该批**完整提交**（20→22）后停止，正是要求的行为。

## 3. 阶段二：恢复

| 时刻 | 事件 |
|---|---|
| 23:44:10 | 提交 `63691`（同 run、同命令） |
| 23:52:41 | 作业结束 |

| 证据 | 值 |
|---|---|
| 恢复作业**首行** | `{"operation": "map", "completed_blocks": 24, ...}` —— **从 22 续起** |
| 最终 | **76 / 76**，`JobState=COMPLETED`、`ExitCode=0:0`、`RunTime=00:08:26`、`anode17` |
| `stderr` | 为空 |
| 阶段一已提交的 22 块 **mtime 被改写数** | **0** |
| **逐块 `output_block_sha256` 重算比对** | **相同 22 / 22，不同 0** |

SHA 比对方法：阶段一停止后、**状态未被覆盖时**快照 `state.active_map.records` 里每个块的
`output_block_sha256`；阶段二结束后用 `pipeline.block_hash` 从状态文件逐块重算并比对。
这是**逐块 SHA 证据**，不是只比数量。

终态：`status=diagnostic_round_complete`、`history=1`、`active_map=None`，
`residual=1.930156e-04`、`boundary_l1=2.4089e-06`。无半成品映射。

## 4. 合并说明（无 reset、无强推）

```
2bec4d9  Merge Mac feedback-ledger fixes with the local signal verification
b5155e9  Verify Slurm signal handling and block recovery on a real allocation（本地信号报告，保留）
de8e0e9  (Mac) Fix feedback ledger identities and interrupted diagnostic recovery
6b5349f  Fix the diagnostic driver's archive, recovery, ledger and stop control
```

`b5155e9` 与 `de8e0e9` 同以 `6b5349f` 为父，属分叉；在独立 worktree 显式 merge：

- `interval_diagnostic.py` —— **取远端版本**。它持久化 pending 在 mkdir **之前**（中断窗口可恢复）、
  带 `history_rows`/`feedback_claims`、并把账本输入与冻结协议来源交叉核对，是本地版本的超集。
- `interval_supervise.py` —— **两边都保留**：远端的 `acknowledge_failed_job` + `--retry-failed-job`，
  与本地拒绝在恢复条件未满足时盲目续交的 `recovery_refusal`。二者互补。
- `tests/test_interval_diagnostic.py` —— 按合并后的契约改写（旧用例针对已被取代的 `start_round`）。

**合并后测试 62 passed**（本地 26 + Mac 集成 13 + 账本 9 + Mac 审计 4 + warm seed 10）。

## 5. 一条可复用的操作要点

**`scancel --signal=USR1 <job>` 在本集群（Slurm 25.11）对本作业静默无效**：
不带 `-b`/`-f` 时只作用于 step，而本作业没有 srun step，批处理 shell 的 trap 不会触发。
必须用 **`scancel --batch --signal=USR1 <job>`**。
作业脚本里的 `--signal=B:USR1@600` 不受影响（sbatch 的 `B:` 前缀本就指向批处理 shell）。

## 6. 本轮确立与未确立

**确立（新版本 `2bec4d9`）：** 信号经 `interval.sbatch` trap 正确转发、`pipeline.STOP` 被置位；
当前批完整提交、下一批不派发；恢复只跑未完成块，**22/22 块 SHA 逐块相同、0 块 mtime 被改写**。

**未实测（仍由单元测试覆盖）：** ① 账本失败 → `diagnosis_incomplete` → 只重做账本；
② 已登记 pending round 的真实中途恢复。二者为 Mac 的 `test_interval_recovery_integration.py`
与本地 `test_interval_diagnostic.py` 覆盖，**本报告不把它们写成实测**。
