# 下一步实验 runbook：α=0.0625 续跑 + 响应噪声底

用户已同意两条队列同时使用：`cpu_long` 跑内层精度续跑，默认 4 核跑响应噪声底诊断。代码按"检查三遍"流程完成核对、修错与本地端到端验证；GitHub 已推送到 `b9af12d`。**学校侧同步尚未完成：SSH 会话过期（`Permission denied (publickey)`，全新连接同样失败），需要在 Terminal 重新认证后继续。**

## 三遍检查发现了什么

第一遍（兼容性通读）确认：`hpc/pipeline.py` 的 `prepare --seed warm` 硬连到 Mac 交接检查点，无法用学校侧状态做种子；`diagnostics/interval_diagnostic.py` 不实现 `initializing`，必须由基础流水线先初始化；`maps_per_job` 只接受 1..20，所以首作业不能用 0。因此续跑必须"先基础流水线初始化，再交给区间驱动"。

第二遍（单元与负路径测试）发现并修复两个**真实缺陷**：

1. `operations/response_noise_floor.py` 把账本方程残差（线性相对能量缺陷）与旧编码残差（对数比）直接相减。两者归一化不同，实测差值 L2 = 126.6，会让"噪声"看起来比信号（22.4）还大，得出完全错误的结论。已改为同定义对照（能量项与尺度取账本那份，布居换成生产实现的输出），修复后该探针为 0。
2. `operations/prepare_extension_run.py` 的槽位判据用"首次记录优先"，对轮换槽位会误判。实测 cont64 三个槽位都等于各自**最后一次写入**的哈希（state_1 = map64 输出 `bbad1a837889`），链完好；已改为最后写入优先，并把续跑点限制为 run 的 `current_slot`（最后一次 map 的输出）。新增"旧端点必须拒绝"负路径测试。

第三遍（真实数组端到端）在 Mac 上跑通两个脚本的完整 `main()`：噪声底脚本对 7B9f 归档基态给出迭代数探针 0.0、1-ulp 加热探针 7.1e-15、账本对生产布居探针 0.0，信噪比 ≈3e15；续跑脚本的成功/试运行/旧端点/槽位篡改/目录已存在五条路径全部符合预期。相关测试本地 20 项、早前全套 53 项通过；学校侧 11 项相关测试在会话失效前通过。

## 待执行流程（SSH 恢复后）

```bash
# 0) 同步（bundle 已在 Mac：outputs/lecture-draft-20260917/slot-fix.bundle）
git -C /home/scc/pb24511938/eccentric-tde-observer status --porcelain
git -C /home/scc/pb24511938/eccentric-tde-observer fetch /home/scc/pb24511938/slot-fix.bundle HEAD
git -C /home/scc/pb24511938/eccentric-tde-observer merge --ff-only FETCH_HEAD

# 1) 只读试运行：核对种子身份（会哈希 9.41 GiB，约 10 s）
.venv-hpc/bin/python operations/prepare_extension_run.py \
  --source-run outputs/hpc/hhe-r025-cont64 \
  --source-state outputs/hpc/hhe-r025-cont64/state_1.dat \
  --run outputs/hpc/hhe-r025-ext16-20260917 \
  --workers 16 --maximum-maps 16 --feedback-every 4 --radiation-threshold 1e-4 \
  --purpose "extend the alpha=0.0625 chain below the relaxed threshold to test the R-scaling" --dry-run

# 2) 正式准备 + 初始化作业（cpu_long，16 worker）
.venv-hpc/bin/python operations/prepare_extension_run.py ... (同上去掉 --dry-run)
TDE_RUN=outputs/hpc/hhe-r025-ext16-20260917 TDE_MAPS=1 TDE_PARTITION=Students \
TDE_QOS=qos_stu_cpu_long TDE_CPUS=16 TDE_MEM=110G TDE_WALLTIME=04:00:00 \
bash hpc/submit.sh pipeline

# 3) 初始化完成（状态 radiation、history=1）后交给区间驱动
TDE_RUN=outputs/hpc/hhe-r025-ext16-20260917 TDE_MAPS=4 TDE_PARTITION=Students \
TDE_QOS=qos_stu_cpu_long TDE_CPUS=16 TDE_MEM=110G TDE_WALLTIME=04:00:00 \
.venv-hpc/bin/python diagnostics/interval_supervise.py \
  --run outputs/hpc/hhe-r025-ext16-20260917 --max-jobs 4

# 4) 并行：默认 4 核跑响应噪声底
TDE_NOISE_RUN=outputs/hpc/noise-floor-cont64-20260917 \
TDE_SOURCE_RUN=outputs/hpc/hhe-r025-cont64 \
sbatch operations/response_noise_floor.sbatch
```

## 为什么这样安排

区间驱动每 4 张 map 形成一轮反馈，正好把 16 张 map 变成 R ≈ 1.26e-4 → 1.14e-4 上的四个 (R, 配对加热量) 数据点，用来检验 α=0.0625 家族实测的 `H ∝ R^1.6` 是否延续；`radiation_threshold=1e-4` 只改"何时算收敛"的记录，阶段 B 已授权的 2.5e-4 门槛不变，也没有任何验收门被放松。初始化必须由基础流水线完成（区间驱动不实现该状态），且续跑点只能是 run 的最新态。

噪声底诊断回答的是一直没求值的那个问题：同尺度物质残差里有多少是求解器噪声。Mac 结果已经把确定性噪声压到 ≤7e-15，对照信号 22.4 与已实测的跨平台差 2.4e-11，三者相差 12–15 个数量级，所以"三范数分歧"是真实结构而不是舍入。学校作业用于确认同一结论在 Linux 算术下成立。

## 成本与边界

- 续跑：16 张 map、每 4 张一轮反馈；16 worker 实测 ≈131 s/map，预计含反馈 1–1.5 h，作业上限 4 h/次，最多 4 次作业。
- 噪声底：单进程、128 单元、4 核 16G，墙钟上限 30 min（实际秒级）。
- 两者都只读或新建独立目录；cont64 及其 64 张预算不改，旧协议、旧核与历史输出不动。任何失败保留进度与部分证据，不盲目重试。
