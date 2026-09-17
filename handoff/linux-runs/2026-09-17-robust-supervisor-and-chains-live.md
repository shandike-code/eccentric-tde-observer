# 无人值守阻塞已解除：健壮监督器与两条延续链上线

## 阻塞的根因（本轮修复）

三条监督器（ext16 的、两条 cont48 的）先后死于同一处：

```python
while subprocess.check_output(["squeue", "-h", "-j", current, "-o", "%i"], text=True).strip():
```

`squeue -j <id>` 在作业记录过期（MinJobAge）后**返回非零退出码**，`check_output` 直接抛 `CalledProcessError`。于是：

- ext16 的监督器在 72052 记录过期后死亡，欠下的第 4 轮反馈无人结算；
- 两条 cont48 监督器一启动就读到指向已过期作业 72207/72208 的收据，立刻死亡。

这解释了当天所有"监督器自己退出"的现象，也说明**在修复前"无人值守"不成立**。

## 修复方式（未触碰被哈希钉住的代码）

`hpc/supervise.py` 与 `diagnostics/interval_supervise.py` 都被既有 run 的依赖哈希固定（前者在 `src/scripts/hpc` 集合里，后者在每轮 `diagnostic_declaration.json` 里），改它们会让既有 run 的下一个作业 `verify_claims` 失败。因此新增 `operations/interval_supervise_robust.py`：

- 通过 import 复用被钉住模块里已验证的语义：`submit`、`recovery_refusal`、`acknowledge_failed_job`、`CONTINUE`；
- 只替换两处会抛异常的查询：
  - `queue_state(job)`：`squeue -j` 非零退出或空列表都解释为"已不在队列"，返回 `None`；不再异常；
  - `terminal_accounting(job)`：先 `scontrol`（记录存活期内权威），再 `sacct`（可能滞后或为空），两者都返回非零时返回 `None` 并由主循环显式报错，而不是崩溃；
- 使用独立收据 `supervisor-robust.json`，与旧的 `supervisor.json` 隔离；共享 `supervisor.lock` 防止同一 run 被两个监督器同时驱动。

三遍检查记录：第一遍通读确认四个复用符号存在、收据字段为 `active_job`/`finished_jobs`、故障策略（非零退出即停、不盲目重试）保持不变；第二遍 6 项单元测试覆盖"过期记录非异常"、"空列表"、"scontrol 优先"、"sacct 兜底"、"未知作业返回 None 而非抛异常"、"非终态 scontrol 落到 sacct"，期间修掉一个真实缺陷（空输出时 `splitlines()[0]` 越界——而这正是作业离开队列时的常见情形）；第三遍在学校平台对两条 run 跑 `--dry-run`，收据干净、状态 `radiation`、`would_submit: true`，随后正式启动。

## 当前实际运行状态（2026-09-17 23:0x）

| 作业 | run | 说明 |
|---|---|---|
| 72219 | hhe-r025-ext16-20260917 | 结算第 4 轮欠账（16/16 张 map 已完成） |
| 72222 | small-step-a078125-cont48-20260917 | α=0.0078125，8 worker，48 张预算，每 8 张一轮反馈 |
| 72223 | small-step-a15625-cont48-20260917 | α=0.015625，同上 |

两个健壮监督器（`--max-jobs 6 --poll-seconds 120`）在登录节点 nohup 运行，各驱动 6 个 8 张 map 的作业；两条链并行占用 16 核、2×50 GiB，在 cpu_long 上限（32 核/128 GiB）内。日志：`outputs/hpc/logs/<run>-robust-supervise.log`。

预计每条链约 4 小时收敛到 R < 2.5e-4，期间产出 6 轮反馈；两个 α 点的编码残差比值会随 R 下降逐步显现，无需等全部收敛即可判读趋势。若中途作业非零退出、OOM 或超时，监督器按设计停止续交并保留证据，需要人工检查后用 `--retry-failed-job <jobid>` 恢复（收据里已记录终态与来源）。

## 判读口径（不变）

`‖r(α)‖/‖r(base)‖`，base = `outputs/phase7b9f_base_material_residual.npy`（L2=15.588864）。已知三点：α→0 按定义为 1.0；α=0.0625 为 1.126（三轮稳定）；α=0.03125 旁支 43 个单元离开物理域。小步 <1 则方向可用、用线搜索收缩步长；小步也 ≥1 则方向必须重做（阶段 D）。
