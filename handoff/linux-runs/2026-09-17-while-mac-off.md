# Mac 关机期间平台自行运行说明

用户 2026-09-17 16:25 告知将关闭本机，之后由平台 agent 接手。以下安排不需要 Mac 或本次会话在线。

## 正在自行运行的东西

- run：`outputs/hpc/hhe-r025-ext16-20260917`（cpu_long，16 worker，`maximum_maps=16`，`feedback_every=4`，`radiation_threshold=1e-4`）。
- 监督器：`diagnostics/interval_supervise.py --max-jobs 4`，以 nohup 方式在登录节点运行（PID 会变，用 `pgrep -af interval_supervise` 查）。它只负责提交与轮询，计算全在 Slurm 节点。
- 收据：`outputs/hpc/hhe-r025-ext16-20260917/supervisor.json` 记录当前正在观察的作业号；重启监督器会用这个收据避免重复提交。
- 进度快照（16:22）：history = 3 张 map，status = radiation，作业 71967 运行中，队列中只有它。map1 残差 1.251289e-04（收缩比 0.9939），map2/map3 同量级下降。
- 预计：每张 map 约 9 分钟（节点共享，实测 4–14 分钟波动），剩 13 张 map 约 2 小时，加 4 轮反馈（第 4、8、12、16 张各一轮）总计约 2.5–3 小时。监督器的 4 个作业额度足够覆盖到预算上限 16 张（job1→5，job2→9，job3→13，job4 到 16 并结算最后一轮反馈）。

## 关机期间会发生什么

1. 监督器按 4 张一批提交作业，每批结束自动提交下一批。
2. 每到 4 的倍数张 map，区间驱动形成一轮正式反馈（H/He 率、净加热、物质响应、账本），把结果写进该轮的 `feedback-roundN/`。
3. 到第 16 张 map 后 run 变为 `diagnostic_round_complete`，监督器发现队列为空、额度用尽后自行退出。**不会**继续提交新作业，也不会自动开始新实验——下一步必须由人判读。

## 失败时会怎样

任何非零退出、OOM、超时或未知调度状态，监督器按设计停止自动续交（不会盲目重试），已提交作业不受影响，进度与部分证据保留在 run 目录。恢复前先看 `outputs/hpc/logs/tde-interval-<jobid>.err` 与 `interval-supervise-ext16.log`；
若确认是瞬时故障，可用完全相同的命令重启监督器（它会读收据继续）：

```bash
TDE_RUN=outputs/hpc/hhe-r025-ext16-20260917 TDE_MAPS=4 TDE_PARTITION=Students \
TDE_QOS=qos_stu_cpu_long TDE_CPUS=16 TDE_MEM=110G TDE_WALLTIME=04:00:00 \
nohup .venv-hpc/bin/python diagnostics/interval_supervise.py \
  --run outputs/hpc/hhe-r025-ext16-20260917 --max-jobs 4 --poll-seconds 120 \
  > outputs/hpc/logs/interval-supervise-ext16.log 2>&1 &
```

若上次是失败退出，脚本会要求显式确认：加 `--retry-failed-job <jobid>`，先检查原因再恢复。

## run 完成后要做的判读（平台 agent 或下一次会话）

1. 读 `state.json` 的 `history` 与 `diagnostic.rounds`，列出每轮：两端点残差 R、`atomic_heating_volume_l1`、`photoionization_volume_l1`、`total_recombination_volume_l1`、各 gate 通过情况、两端点非物理单元数。
2. 把新点并入同口径表 `handoff/evidence/ustc-inner-precision-ladder-20260917.json`，用同一 run 内 log-log 拟合更新 `H` 对 `R` 的斜率（当前 α=0.0625 家族 16 轮为 1.635）。
3. 判据：加热量是否继续下降、非物理单元是否保持 0。若延续，则 α=0.0625 是唯一可能越过 1e-3 加热门的路径，再决定是否继续加精度；若出现 confirm run 那样的回升（R 几乎不变而加热量上升），则内层精度路线终止，转阶段 D 的响应闭合/有界回溯。
4. 把结论写进 `handoff/linux-runs/`，大态留在平台存储，只提交代码、说明与小型审计报告到 Git。

## 已入库的参照

- 噪声底结论（作业 71947，Linux）：迭代数探针 0.0、1-ulp 探针 1.18e-14、账本对生产布居 0.0，两平台一致；同尺度残差不是噪声主导。证据 `handoff/evidence/ustc-noise-floor-20260917.json`。
- 同尺度基态/候选比较与精度阶梯：`handoff/linux-runs/2026-09-17-baseline-replay-and-precision-ladder.md`、`handoff/evidence/ustc-baseline-replay-20260917.json`。
- 三遍检查已写入 `AGENTS.md` 成为常设要求；本 run 的代码（prepare_extension_run、response_noise_floor）都过完三遍，期间修掉三个真实缺陷，记录在 `2026-09-17-next-experiment-runbook.md`。
