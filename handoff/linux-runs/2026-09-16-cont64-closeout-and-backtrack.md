# cont64 结束：单候选有界回溯

Codex 于 2026-09-16 22:28 经 SSH 验证：`hhe-r025-cont64` 已结束，64 张 map、16 轮反馈全部落地，`status=diagnostic_round_complete`，无 pending、队列空。它是预算完成，不是候选验收通过。

## 最后两轮真实指标

| 指标 | 第 15 轮 | 第 16 轮 |
| --- | ---: | ---: |
| atomic heating 相邻变化 | 0.0032688487 | 0.0031339972 |
| 内层噪声/试步信号 | 0.01147812 | 0.00873658 |
| L2 residual candidate/base | 1.133515 | 1.128888 |
| 质量加权 residual candidate/base | 2.191939 | 2.193645 |
| 最差单元 residual candidate/base | 1.092535 | 1.002210 |
| previous/final 负热能层数 | 0 / 0 | 0 / 0 |

最终 map 辐射残差 `1.2589261183894017e-4`、边界 L1 `2.627007847041482e-6`。第 16 轮 final 最小剩余气体热能为旧气体热能的 3.0756%，在 cell64。

物理域和噪声门通过，但 3 类加热稳定性及 3 类物质收缩门仍未过。尤其质量加权残差在最近两轮略回升，不能因最差单元比接近 1 就圆整为通过。加热尚不稳定，也不能证明此方向在完全收敛辐射下必然无效。

## 决策与新边界

不机械追加旧候选 64 张。进行一次**探索性的有界回溯**：从原 `base_encoded_state` 沿原 `finite_direction`，把绝对步长 0.0625 减至 **0.03125**。这不是在旧候选上再走半步，也不是插值其反馈，更不是减小物理 dt。新候选不预设会改善。

- 新 run：`outputs/hpc/hhe-backtrack-r003125-20260916-v2`。
- 候选定义：`encoded_new = original_encoded_base + 0.03125 * original_direction`。
- 保留原密度、旧物理时间层、相位、dt、能量定义、原 residual baseline 及所有科学门；禁止 floor、裁剪和重归一化。
- 原 run 的最后辐射输出 `state_1.dat`（SHA `bbad1a837889c93104d2f7b47a47fe35d2cf7e1035792247480ed612a6832c1f`）只作数值初值，不能视为新物质态的辐射解。
- 4 workers / 8 CPU / 32G，`qos_stu_cpu_long`，单批最大 8h。8h 是资源时限，不是完成时间预测；预算仍只有 **8 张新 map、每 4 张一轮、最多两轮正式反馈**。
- 所有门通过即停为一个接受的物质步；资源/源码/物理域错误保留证据并停。预算到点仍需 Codex 决定，不由监督模型续交或改阈值。

## 新入口如何复用旧核

`operations/prepare_encoded_backtrack.py` 在 allocation 内验证停止态来源、config/trial SHA、原编码方向恒等式、基准残差和精确物理解码，构造并检查新候选；将原方向、基态所在 NPZ 与新 NPZ 分别固定哈希，写独立声明。

新 trial 在初始化前创建。专用 `--initialize-only` 入口调用现有 Python API `pipeline.run_pipeline(run, maps_per_job=0, do_feedback=False)`，只初始化自有辐射槽，检测到已存在的 trial 后不会调用旧 0.0625 迁移。之后调用原诊断 driver，执行 8 张/4 张间隔的独立运行。

额外运行 `audit_native_trial`：经原 `configure_native` 配置后调用实际 `_second_full_material`，逐值核验镜像全柱的密度、温度、H/He 布居确实来自新候选，并验证旧相位与 dt。旧碰撞/转移/正式反馈核不改动；正式反馈适配器仍会验证新 trial 精确编码、SHA 和物理旧时间层。历史 `src/`、`scripts/`、`hpc/`、`diagnostics/` 无修改。

新 worker 消费的是新物质态，存储项仍采用原物理旧时间层；两者不能混为一谈。每个正式反馈对必须由这个候选的新映射端点重算，不复用旧候选的反馈 NPZ。

## 验证与操作

Mac 相关 69 项测试通过，其中新候选 11 项测试覆盖编码/方向、原 dt、基准残差篡改及较小正步长限制；监督新增接口后其与候选共 21 项测试通过。shell 语法检查通过。

Mac 用 Linux 真实 trial 做精确 decode 比较出现架构差异；没有放宽 guard。真实候选和 native 物质注入核验必须在学校 Linux allocation 内通过，失败即退出，不把 Mac 合成测试冒充 Linux 实测。

```bash
TDE_RUN=outputs/hpc/hhe-backtrack-r003125-20260916-v2 \
TDE_SOURCE_RUN=outputs/hpc/hhe-r025-cont64 \
sbatch --parsable operations/encoded_backtrack.sbatch
```

单批直接提交，不创建第二个自动提交者。信号时尽量在现有可恢复边界停止；正式反馈中的超时恢复仍需查实际 manifest，不承诺所有阶段都能在 USR1 后瞬时退出。再次提交同一个 run 前核对队列、声明和输入，准备器验证已有声明，不覆盖旧 run。

平台 Claude watcher 已支持从新 run 配置读取预算及候选，并可直接监督一个 `--science-job JOBID`，保存调度器终态；有界作业结束即交 Codex 审阅，不扩预算。下一次本任务跟进应先读本报告及新 run，cont64 保持归档态。

## 准备阶段实测与两次接口修复

- 作业 64598 在准备阶段因历史 state 没有 `trial_sha256` 失败；未创建候选、未算 map。改用最后一轮已完成正式反馈协议及其 trial 的 SHA 作为身份锚，协议本身也与 state 中的声明 SHA 核对，不绕过完整性验证。
- 作业 64607 已在 Linux allocation 通过真实候选检查及 native 注入核验：镜像全柱密度、温度、H/He 布居逐值一致，原相位与 dt 一致。新候选 trial SHA 为 `f0c35fff1f47aaf6189cfc2d90a8db398a654939d3cff7fa0f11875d756c66e7`。随后旧 CLI 拒绝零 map 参数（只允许 1..20），未开始辐射初始化或新 map。
- 第二项修复通过专用入口直接调用支持零 map 的既有 API，缺少自有新 trial 就拒绝，避免回退到旧候选迁移或多算预算外 map。准备脚本与 batch 脚本已变更，旧 run 声明保留，新建 `-v2` run，不篡改旧声明。
- 增加历史协议身份与零 map 初始化的回归测试；当前候选与监督相关测试合计 23 项通过。测试不能替代下一次真实初始化及 worker 开始的验证。

## v2 已进入实际计算

2026-09-16T22:49:23.654597+08:00 实测：作业 **64633** 为 RUNNING，`-v2` run 完成新候选及 native 注入审计、9.41 GiB 初值复制与哈希验证，进入第 1 张 map，已有 **16 个块**提交。部署提交为 `89519f4`；Mac 与 Linux 各自 23 项相关测试通过。GitHub 远端分支 HEAD 已通过 `ls-remote` 核对为同一完整提交。

两个旧失败的调度器终态均已在过期前留档：64598 为 FAILED / 1:0 / 11 秒，64607 为 FAILED / 2:0 / 8 秒。二者是准备接口缺陷，不是新候选的物理失败。原始查询、首块记录、native 核验及提交参数见 `handoff/evidence/ustc-backtrack-v2-start-20260916.json`。

平台 tmux 会话 `tde-backtrack-v2-watch`、监督目录 `outputs/hpc/codex-backtrack-watch-20260916-v2` 已启动并产生两次只读简报。Claude Code 实际配置后端为 `deepseek-v4-flash`，不把客户端名当模型身份。监督模型不提交作业、不改代码或门槛；Codex 的 30 分钟跟进已切换至这个 run/job。

监督模型曾从性能基准的 512 秒/图推测新候选总用时；该外推不可采纳：候选物质与离不动点距离均已变化，正式反馈也另有成本。这里不报告新候选完成时间，只承诺已声明的资源与映射预算。当前仍没有新候选的正式反馈结果，更没有最终发射率。
