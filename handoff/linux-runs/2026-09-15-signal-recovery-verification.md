# Slurm 信号与恢复实测验证（针对 `6b5349f`）

对象：运行控制修复提交 `6b5349f`。方法：一次性 run + **真实** `diagnostics/interval.sbatch`
（其 `SIGUSR1` trap 与投递路径）、**未经修改**的 `pipeline.batches` 调度与块提交、
**真实** worker。仅语料是一次性的，调度/信号/状态持久化逻辑**没有任何 mock**。

## 0. 最重要的一条发现：信号投递方式

**`scancel --signal=USR1 <job>` 在 Slurm 25.11 上对本作业静默无效。**

本作业的批处理脚本没有 srun step，`scancel --signal` 不带 `-b`/`-f` 时只作用于 **step**，
批处理 shell 收不到。实测：

| 命令 | 结果 |
|---|---|
| `scancel --signal=USR1 63638` | `exit=0`，但驱动**从未**打印 `Stop requested`，块数继续增长 |
| `scancel --signal=B:USR1 63638` | `exit=1`，`Unknown job signal: B:USR1` |
| **`scancel --batch --signal=USR1 63638`** | **`exit=0`，驱动立即打印 `Stop requested`，行为正确** |

`scancel --help` 的 `-b, --batch  signal batch shell for specified job` 即为此。

**这不影响作业脚本本身**：`submit.sh` / `interval.sbatch` 里的 `--signal=B:USR1@600`
用的是 sbatch 的 `B:` 前缀（只发批处理 shell），语义正确。受影响的是**人工或测试投递**——
必须加 `-b`。先前夜间轮次的 USR1 处理其实从未被真正触发过，本次是第一次实测。

## 1. 设置

一次性 run `outputs/hpc/hhe-signal-check`：

- `config.json` 源自 `hhe-diag-r025`（冻结源清单一致），仅改 `run` 与 `maximum_maps`
- 种子 = `hhe-diag-r025/state_2.dat`（已提交 SHA `eb4c30283322c41c…`）的副本
- 2 worker、4 CPU / 16 G、`Students` / `qos_stu_default`、墙钟 `00:30:00`
- **`hhe-r025`、`hhe-r025-warm`、`hhe-diag-r025` 三个既有 run 一字未动**

## 2. 阶段一：中途打断

| 时刻 | 事件 |
|---|---|
| 22:58:10 | 提交 `63651`（真 `interval.sbatch`，`TDE_MAPS=1`） |
| 23:01:00 | 已提交 **20 块**（10 个 2-worker 批）；发出 `scancel --batch --signal=USR1 63651`，`exit=0` |
| 23:01:05 | 驱动打印 **`Stop requested`**；块数**仍为 20**；作业已退出 |
| — | `JobState=COMPLETED` **`ExitCode=0:0`**；`stderr` 为空 |

**驱动日志末行 `{"operation": "map", "completed_blocks": 20, "total": 76}`** ——
即当前批**完整提交**后停止，**没有启动下一批 worker**。从发信号到作业退出 5 秒。

## 3. 阶段二：恢复

| 时刻 | 事件 |
|---|---|
| 23:01:05 | 提交 `63652`（同一 run，同一命令） |
| 23:09:46 | 作业结束 |

**恢复证据：**

| 证据 | 值 |
|---|---|
| 恢复作业 **首行**进度 | `{"operation": "map", "completed_blocks": 22, ...}` —— **从 20 续起，不是从头** |
| 最终块数 | **76 / 76** |
| 新增块 | 56 |
| **阶段一已提交的 20 块中，mtime 被改写数** | **0** |
| 退出码 | `COMPLETED` **`ExitCode=0:0`**，`stderr` 为空 |

**更强的证据**：`pipeline.batches` 每次进入都会对**每个已提交块重算 `block_hash`** 并与
记录的 `output_block_sha256` 比对，不一致即 `RuntimeError`。恢复作业全程未抛——说明已提交块
**逐字节未变**，而不是仅仅「看起来没动」。

`state` 终态：`diagnostic_round_complete`，`history=1`，`active_map=None`，
`residual=1.915347e-04`、`boundary_l1=2.3603e-06`。无半成品映射。

## 4. 本轮确立与未确立

**确立：**

1. `SIGUSR1` 经 `interval.sbatch` 的 trap 正确转发到驱动进程，`pipeline.STOP` 被置位。
2. 收到停止后**当前批完整提交、下一批不再派发**，作业以 0 退出。
3. 恢复作业**只跑未完成的块**，已提交块不重复、未被改写（mtime 与 `block_hash` 双重证据）。

**未确立（本轮范围外）：**

1. 本轮**没有**触发「账本失败 → `diagnosis_incomplete` → 只重做账本」这条路径的**真实**运行——
   它由单元测试覆盖（`test_ledger_failure_leaves_the_round_incomplete`、
   `test_supervisor_refuses_to_resubmit_an_unverifiable_recovery`），**不是**实测。
2. 本轮**没有**触发「已登记的 pending round 中途恢复」的真实运行，同样只有单元测试覆盖。
3. 墙钟到点前的 `--signal=B:USR1@600` 自动预警路径未单独实测；本轮用的是人工 `-b` 投递，
   两者走同一个 trap。

## 5. 复现命令

```bash
scancel --batch --signal=USR1 <jobid>          # 不要用不带 -b 的写法
squeue -h -j <jobid> -o %i                     # 判活
grep -c 'Stop requested' outputs/hpc/logs/tde-sigcheck-<jobid>.out
ls outputs/hpc/<run>/map0001/block*.json | wc -l
```
