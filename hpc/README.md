# 中科大 Slurm：起跑、恢复与监督

本页是操作入口。科学任务和验收边界见 [AGENT_TASKS_ZH.md](../handoff/AGENT_TASKS_ZH.md)。
这些脚本在 Mac 上经过组件测试和真实分辨率单块检查；尚未在学校 Linux 节点上实测。

## 平台与资源

官方文档确认使用 Slurm。登录节点/WebShell 负责编辑、安装轻量依赖、提交与查看作业；
实际数值计算须在计算节点运行。默认一般为 `Students`、`qos_stu_default`。
文档中的默认方案为最多 4 CPU、16G 内存、4 小时；这些是动态配置，不是本仓库对账号配额的保证。
CPU 长任务方案 `qos_stu_cpu_long` 的文档示例为 32 CPU、128G、72 小时，需要账号获准后才能用。

- [平台概览](https://107.ustc.edu.cn/docs/overview/)
- [资源与 QOS](https://107.ustc.edu.cn/docs/overview/resources/)
- [提交任务](https://107.ustc.edu.cn/docs/basics/jobs/)
- [Slurm 速查](https://107.ustc.edu.cn/docs/basics/slurm/)
- [文件与数据](https://107.ustc.edu.cn/docs/basics/files/)

用户提供的 WebShell 快照：48 核、总内存 125 GiB、available 34 GiB、swap 8 GiB 基本用尽，
共享 `/home` 显示约 905 T 可用。这些不是单用户配额；不要把缓存重复加到 available，
不要占用全部主机内存，不要把共享盘总剩余量当作个人 quota。正式起跑先记录：

```bash
sinfo
scontrol show part
quota -s
df -h .
```

`quota` 若不可用，去平台页面查限额。这个项目不使用神经网络、HF 模型或 CUDA；无需配置
Hugging Face 镜像，也无需申请 GPU。先使用 2 worker、4 CPU、16G。验证后可分别 benchmark
4 worker/约 28G、8 worker/约 52G，但必须先获得资源，并为这些配置创建独立运行目录。
多核性能受内存带宽、进程启动和共享盘 I/O 限制，不能按核心数线性外推。

## 克隆和环境

私有仓库需要该 GitHub 账号已有的访问权限；不要把 token 放到 URL、脚本或 Git 提交中。
学校端若有 `gh`，用官方设备登录；也可以用已配置的 Git 凭据。GitHub 无法访问时保留报错，
通过平台文件管理器上传从本机下载的仓库与输入包，不修改集群系统代理。

```bash
git clone https://github.com/shandike-code/eccentric-tde-observer.git
cd eccentric-tde-observer
git config --local user.name shandike-code
git config --local user.email 310837749+shandike-code@users.noreply.github.com
git config --local core.autocrlf false
python3.12 -m venv .venv-hpc
.venv-hpc/bin/python -m pip install --upgrade pip
.venv-hpc/bin/python -m pip install -e . pytest
.venv-hpc/bin/python -m pip freeze > environment-linux.txt
```

Git 身份来自本次已验证的 GitHub 账号。其他协作者应使用自己的真实身份。
Python 3.12 是当前参考版本；不要复制 macOS `.venv`、Fortran 二进制或 ARM 库到 Linux。
如果平台只有 conda，可创建 Python 3.12 环境并设置 `TDE_PYTHON` 为该环境的 Python 绝对路径。
国内下载慢时可给**本次 pip 命令**加 `--index-url https://pypi.tuna.tsinghua.edu.cn/simple`；
不用 `--trusted-host` 或关闭 TLS。镜像若缺版本，保留日志后尝试官方源，不伪造成功。

`uv.lock` 是历史锁文件；`hpc/requirements-reference.txt` 记录本次 Mac 实际版本。
若 Linux 上这些版本均可用，可安装该文件做版本对齐；不可用时先记录版本差异、运行 smoke
和数值对照，再决定采用哪个组合。依赖版本不同不能仅靠更新哈希宣称跨平台一致。

## 输入与检查点

Git 保存源码、测试、文档和清单。数据在私有仓库的 `handoff-2026-09-14` Release：

1. `tde-runtime-inputs-2026-09-14.tar.gz`：约 29 MB，正式起跑所需物质参考、频率网格及小型元数据。
2. `tde-small-artifacts-2026-09-14.tar.gz`：约 744 MB，可选，用于查看历史图、完整结果审计和历史测试。
3. 历史完整辐射 `.dat` **不在 Git 或上述包中**。新流水线的 cold 初始化不需要它们。

精确大小、逐文件 SHA-256 及压缩包 SHA-256 在 `handoff/runtime_bundle.json` 和
`handoff/artifact_bundle.json`。只提取到空的新克隆；恢复器会拒绝覆盖已经变化的结果。

```bash
mkdir -p downloads
gh release download handoff-2026-09-14 \
  --repo shandike-code/eccentric-tde-observer \
  --pattern 'tde-runtime-inputs-2026-09-14.tar.gz' --dir downloads
.venv-hpc/bin/python hpc/restore_artifacts.py \
  downloads/tde-runtime-inputs-2026-09-14.tar.gz --profile runtime
```

私有 Release 的下载也需要认证。若 `git clone` 正常但 Release 下载域名受限，用学校文件管理器
上传同一个包，再运行恢复器校验；不要把未经校验的部分下载作为输入。

可选完整小型结果包：下载后以 `--profile historical` 恢复。它仍不包含约 218 GiB 历史辐射态，
因此不能宣称完整恢复了历史检查点库存。各阶段 `.dat` 是强度工作态，不是观测谱或多套物理模型。

### 可选：从 Mac 最新端点 warm start

只需转移 `handoff/checkpoints.files` 中的两个文件，保持项目相对路径。每个
10,099,884,032 bytes，合计 18.8125 GiB。源在 Mac 本项目的 `outputs/checkpoints/`；
`handoff/restart_manifest.json` 保存停止点哈希，传输后在 batch 作业中检查。

若学校提供 SSH 地址，可在 **Mac 项目根目录**使用真实账号和地址：

```bash
rsync -av --partial --files-from=handoff/checkpoints.files ./ \
  SCHOOL_ACCOUNT@SCHOOL_HOST:/ABSOLUTE/PROJECT/PATH/
```

地址不是 `107.ustc.edu.cn` 的默认推断；必须采用平台实际传输入口。没有 SSH 就用文件管理器。
两份工作态要分别传输，避免 Mac 再产生一份 18.8 GiB 大压缩包。
只从最新单态 warm 初始化新流水线也可，但为旧 runner 原位恢复必须具备两态及对应 manifest。

```bash
bash hpc/submit.sh verify
```

`verify` 对**原始交接快照**做完整 SHA 校验。数据发生后续合法变化后，按新运行 manifest
验证，不要继续要求它等于旧快照。旧 manifest 的 `running` 只是可恢复状态，不说明仍有进程。

## 推荐起跑命令：新流水线

先让 agent 完成 Git 身份和环境配置，再提交 smoke：

```bash
bash hpc/submit.sh smoke
squeue -u "$USER"
```

读取 `outputs/hpc/logs/tde-smoke-JOBID.out`，确认测试通过。该 smoke 集合是明确列出的
数据无关物理控制，**不是全部历史测试**。环境和 Slurm 资源写入 `outputs/hpc/environment-JOBID.json`。

接着提交自动单块迁移检查：

```bash
bash hpc/submit.sh block-check
```

它在完整频率网格形状的稀疏文件中初始化一个 `128 × 32 × 4096` 块，逐块对照新旧
辐射 worker，并实际运行一个 H/He 反馈块。输出在 `outputs/hpc/block-check/block_check.json`。
这只是含零邻块的合成控制，不是收敛物理解；报告同时给出逐位相等与相对差异（门为 `1e-11`）。
稀疏文件逻辑大小合计 28.22 GiB，实际写入约 384 MiB；部分平台 quota 按逻辑大小计费，先确认。
该检查不续跑；需要重做时使用 `TDE_RUN=outputs/hpc/block-check-2` 创建新目录。

然后在 WebShell 准备小型配置，真正初始化与计算仍由 batch 执行：

```bash
.venv-hpc/bin/python hpc/pipeline.py prepare \
  --run outputs/hpc/hhe-r025 --workers 2 --threshold 0.00025 \
  --maximum-maps 256 --seed cold
TDE_RUN=outputs/hpc/hhe-r025 TDE_MAPS=1 bash hpc/submit.sh pipeline
```

`cold` 使用既有物理旧时间层的 boosted Planck 场作数值初值，并冻结当前 `0.0625` 物质候选。
它不会把物质背景重算成全盘解。初始化后先跑一次完整映射，记录 CPU 时间、RSS、I/O 和残差；
不能以一次映射未收敛为算法失败。跨平台首次结果要和组件控制、原算子单块对照一起评估。

传入最新端点后，可把 `--seed cold` 换成 `--seed warm`；新流水线复制到自己拥有的工作态，
不覆盖 Mac 快照。新流水线使用三个轮换强度态，约 28.22 GiB；需要至少再留 8 GiB 余量。
三态用于保留两个有独立残差证明的输入端点及其后继态，避免把未经自检的映射输出当作反馈端点。

检查一次 benchmark 后，提交后续批次：

```bash
TDE_RUN=outputs/hpc/hhe-r025 TDE_MAPS=8 bash hpc/submit.sh pipeline
.venv-hpc/bin/python hpc/pipeline.py status --run outputs/hpc/hhe-r025
```

也可让轻量监督器依次提交有限数量的 batch 作业：

```bash
TDE_MAPS=8 .venv-hpc/bin/python hpc/supervise.py \
  --run outputs/hpc/hhe-r025 --max-jobs 32
```

监督器只在 WebShell 调用 Slurm 和读 JSON，不在登录节点做计算。关闭监督器不取消已提交任务；
再次启动会读取持久化 job ID，避免重复提交。若被杀在 sbatch 成功但 job ID 尚未落盘的极短窗口，
先用 `squeue` 确认是否已有同名作业，再恢复。任何非零退出、OOM、超时或未知 accounting 状态都停止
自动续交，交给 agent 检查日志；不无限重试。

自定义资源例子（先确认授权）：

```bash
TDE_PARTITION=Students TDE_QOS=qos_stu_cpu_long \
TDE_CPUS=8 TDE_MEM=52G TDE_WALLTIME=06:00:00 \
TDE_RUN=outputs/hpc/hhe-workers8 bash hpc/submit.sh pipeline
```

此例还要求先以 `--workers 8` 创建那个新运行。只改变 `TDE_CPUS` 不会改变求解器 worker 数。
当前 WebShell available 34 GiB 不支持据此承诺 52G；是否有其他空闲计算节点由 Slurm 决定。

## 自动运行到哪里

`state.json` 会经过以下状态：

| 状态 | 监督动作 |
|---|---|
| `initializing` / `radiation` | 继续有限 batch；检查块进展与残差趋势 |
| `feedback_ready` / `feedback_running` | 自动计算两态 H/He 率、加热及物质响应；可以恢复 |
| `one_material_trial_accepted` | 一个物质试探步通过；停下审查，尚未完成耦合柱 |
| `material_trial_not_accepted` | 读取 `feedback_summary.json` 的具体失败门，不能称为静态解不存在 |
| `budget_exhausted` | 检查收缩率与成本，不自动放宽阈值或无限扩预算 |
| `resource_gate_failed` | 检查 RSS 和并发，建立新资源配置后再验证 |

所有新运行都保留原物理核；`config.json` 记录源哈希、依赖、阈值、并发和预算。
断点恢复校验输入 SHA 和已完成频率块 SHA。每批块原子提交；半完成输出不会作为完整辐射态接受。
Slurm 的提前信号使新流水线在当前 block batch 后停止；反馈阶段沿用自己的逐块恢复。
即使发生强制超时，仍需由 agent 检查退出原因再恢复，不能保证所有异常都自动修复。

默认 `2.5e-4` 只是新的内层精度试验。两态都必须过该门和两个 `1e-3` 边界门；
H/He 反馈稳定性、物理域、内层噪声/试步信号和三种物质残差收缩门没有放宽。
比较 `2e-4`、`1e-4` 时创建不同目录，禁止改已运行的 `config.json`。
反馈调用继承了历史 runner 的图与诊断，新驱动会重新要求所有显式 gate 为真，不仅依赖
旧报告中较宽泛的 `formal_h_he_feedback_pair_passed` 标签。

## 严格历史恢复与测试边界

`hpc/resume.py` / `bash hpc/submit.sh resume` 是另一条入口，原样恢复 7B9du 的 **严格 `1e-4`**
双缓冲方案。需两份外部 `.dat`；默认只续一张完整映射。它不是上述放宽门槛的新流水线。

本次首次全历史测试为 1118 通过、13 失败：11 个讲义迁移路径，1 个 Markdown 规范测试，
1 个库存数量过期（10048 对 10051）。这些问题在交接时明列，不用改数值阈值让测试变绿。
`normalize_markdown_math.py --write` 的候选 diff 会错误波及部分讲义链接/正文，不能盲目执行。
只有 runtime 包时，许多历史 artifact 测试本来就缺数据；需要它们时下载 historical 包。
全检查点库存测试还需要完整历史大数据，因此缺失不等于物理计算失败。

已有测试不能证明新的完整 Linux 流水线已经完成。先做 smoke、真实单块、完整映射、可恢复性
和两态反馈验证，再把结果提升到对应的科学等级。
