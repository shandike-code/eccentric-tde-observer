# 从 GitHub 取得 warm 检查点

本次将一份完整检查点通过**私有 GitHub Release 附件**交接。`git pull` 更新下载脚本、
清单和说明；大数据通过 Release 下载，不进入 Git 历史。

- 仓库：`shandike-code/eccentric-tde-observer`
- Release：`warm-seed-2026-09-15`
- 共 10 个未压缩分片：前 9 个各 1 GiB，最后一个 416 MiB。
- 完整文件：`outputs/checkpoints/phase7b9k_retained_trial_map3.dat`
- 大小：10,099,884,032 bytes（9.40625 GiB）。
- SHA-256：`5999be906b78e5478c34868e210eb3a135a579df9ff7d203badc31b37ae03e6b`

GitHub 每个 Release 附件需小于 2 GiB，因此采用上述分片。
参见 [GitHub 官方说明](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)。
`warm_seed_github.json` 附件在全部分片上传并核验后**最后上传**，作为完成标记。
缺少该标记时不能把部分上传当成完整交接；下载脚本会拒绝继续。

## 1. 更新与认证

先检查本地变更，不用 reset、覆盖或丢弃学校端结果：

```bash
git status --short
git pull --ff-only
gh auth status
```

私有 Release 需要 GitHub 访问权限。GitHub 认证与学校 SSH 密码无关。
已有 Git 凭据不保证 `gh` 已登录；若需要，使用 `gh auth login` 的官方登录流程。
不要把 token 写到命令 URL、脚本或提交中。没有 `gh` 时，可以从浏览器下载全部原名分片，
放入 `downloads/warm-seed/`，然后直接运行第 3 步。

脚本位于 `handoff/`，不会被既有 pipeline 的 `src/scripts/hpc` Python 源清单收录，
因此单独加入这些文件不会改变已冻结 cold 运行的数值源哈希。本次没有修改生产求解器。
若远端还有其他代码更新，仍应核对 diff，不要假定任意 git pull 都不会影响正在运行的作业。

## 2. 下载分片

在平台允许联网和传输文件的节点执行：

```bash
python3 handoff/fetch_warm_seed.py download
```

脚本先核验 GitHub 的完成标记和逐片 size/digest，再下载和本地校验。已通过校验的分片会跳过；
失败后重跑同一条命令即可。恢复粒度是完整分片，未完成的当前分片重新下载。
不会把未校验的临时下载发布为完整分片。

网络受限时也可用平台文件管理器上传这 10 个分片到 `downloads/warm-seed/`，
拼接程序仍依据清单顺序与 SHA 验证。不要用可能混入旧文件的通配符直接 cat。

## 3. 拼接与全文件校验

下载分片加生成完整文件需额外约 18.8 GiB 空间；之后新 warm 运行另需约 28.2 GiB 工作态与余量。
已有 cold 工作态原样保留，容量要另外计算，不能把共享文件系统剩余量当个人 quota。

建议在 batch 中执行拼接/校验。例如从项目根目录提交（分区和 QOS 以实际权限为准）：

```bash
mkdir -p outputs/hpc/logs
sbatch --job-name=tde-warm-assemble --nodes=1 --ntasks=1 \
  --partition=Students --qos=qos_stu_default --cpus-per-task=1 \
  --mem=2G --time=01:00:00 \
  --output=outputs/hpc/logs/warm-assemble-%j.out \
  --wrap='python3 handoff/fetch_warm_seed.py assemble'
```

程序逐片核验，同时计算完整字节流 SHA，写入临时文件并同步到磁盘后，才原子建立正式文件名。
已有正式文件若哈希不同会拒绝覆盖。拼接中断后可以重跑，正式文件不会暴露半成品。
需要独立重读核验时执行 `python3 handoff/fetch_warm_seed.py verify`（同样建议 batch）。
分片默认保留，方便审计或重试；不要清理已有研究检查点。

## 4. 在独立运行中使用

确认拼接作业成功，并且完整 SHA 与上面一致，再准备不存在的新目录：

```bash
.venv-hpc/bin/python hpc/pipeline.py prepare \
  --run outputs/hpc/hhe-r025-warm --workers 2 --threshold 0.00025 \
  --maximum-maps 4 --seed warm
TDE_RUN=outputs/hpc/hhe-r025-warm TDE_MAPS=1 bash hpc/submit.sh pipeline
```

先查看第一张映射的残差、边界指标、频率完整性和资源，再提交第二张。
继承的历史残差不是该文件在 Linux 上已经通过自检的证明；只有两次新的连续映射分别满足
既有条件，才允许现有流水线进入正式 H/He 反馈。“两张一定进入反馈”不是保证。

不要同时无预算地运行 cold 与 warm；先核对已有作业，按已授权资源安排。
不能把 warm seed、一次物质试步通过或纯传输校验当成耦合柱/全盘大气已完成。

## 验证范围

`tests/test_warm_seed_transfer.py` 使用小型二进制夹具验证正常拼接、重复执行、坏分片拒绝、
失败后恢复、旧结果保护、偏移/命名检查和全文件 SHA 门。大检查点的每个分片还在发布时对照
原文件哈希及 GitHub 服务端 SHA；下载和拼接阶段再次检查。
