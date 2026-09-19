# 同时使用 cpu_long 与默认资源：共同初值的相邻候选对照

用户明确要求使用已授权的 32 核 cpu_long。2026-09-19 实查 QOS：`MaxTRESPU=cpu=32,gres/gpu=0,mem=128G`、`MaxWall=3-00:00:00`。当时 cpu_long 空闲，默认方案作业 73238 在运行。

## 执行安排

| 作业 | 物质候选 alpha | QOS | 申请资源 | 重型 worker | run |
|---|---:|---|---|---:|---|
| 73238 | 0.00390625 | qos_stu_default | 4 CPU / 16G | 2 | common-seed-a00390625-20260919 |
| 73241 | 0.0078125 | qos_stu_cpu_long | 32 CPU / 128G | 16 | common-seed-a0078125-long-20260919 |

两者均在 `outputs/hpc/` 下，使用同一份历史基态辐射文件作为初值、原物理步长与各自原有物质候选，最多两张 map、两个状态反馈，墙钟上限 3.5 h，无自动续交。两个 QOS 的配额分别核对；不将 WebShell 整机资源视作 allocation。

32 个申请 CPU 不等于 32 个重型进程。现有保护为每 worker 6 GiB 加主进程 2 GiB；32 worker 需 194 GiB，超过 128G。本次保留保护，运行 16 worker，BLAS/OMP 单线程；不声称 32 CPU 会持续全部占满。9 月 17 日同输入测速已验证 16 worker 比 4 worker 快 2.57 倍且输出哈希相同；此历史结果支持使用 16 worker，但本次加速比仍需重新从运行墙钟测量，不能直接移植。

## 代码、备份和检查

新代码 `f3d1d39`：`operations/cpu_long_common_seed_control.py/.sbatch` 及对应测试。从已启动的共同初值控制派生独立文件，不改被 73238 钉住的脚本。新候选从 `small-step-a078125-cont24-20260918/trial_material.npz` 复制，全部物质字段逐位保留，验证 base/direction/alpha/encoded 与解码温度/布居/比能，再核验 native 消费身份。

改动前 Git 备份 `outputs/review-20260919/pre-cpu-long-2baea96.bundle`；增量部署 bundle 在 Mac 与学校各保留。Mac/Linux 相关测试各 19 passed，包括 16 worker 通过 128G 资源保护、32 worker 被拒绝的测试。测试不代替实际资源监测或科学验收。

73241 提交已获 Slurm job ID，第一次队列观测 PENDING；实际起跑以调度器回执及 `control_status.json` 为准。所有准备、配置、声明与小输入快照由独立 run 保存。

## 结果如何使用

零位移对照 73070 已完成且基本复现历史反馈，见 `2026-09-19-baseline-zero-result.md`。新两组比较“同一辐射初值、不同有限物质位移”的短程反应。两张 map 不建立完整内层误差界；即使两个候选皆有正目标热能，也不能立即接受物质步。不同 worker 数的历史一致性验证不是本次两个不同候选输出应相同的要求。

完成后备份小工件并比较每个输入的真实算子残差、率/加热变化、目标热能分布、三个同尺度方程残差范数以及旧候选路径。有限差分必须用完整向量并控制基态与候选两侧误差，不能只比较向量长度，不能用旧无效步长建议。若运行异常保留目录并查因，不盲重交。
