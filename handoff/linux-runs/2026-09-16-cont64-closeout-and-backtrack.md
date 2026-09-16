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

- 新 run：`outputs/hpc/hhe-backtrack-r003125-20260916`。
- 候选定义：`encoded_new = original_encoded_base + 0.03125 * original_direction`。
- 保留原密度、旧物理时间层、相位、dt、能量定义、原 residual baseline 及所有科学门；禁止 floor、裁剪和重归一化。
- 原 run 的最后辐射输出 `state_1.dat`（SHA `bbad1a837889c93104d2f7b47a47fe35d2cf7e1035792247480ed612a6832c1f`）只作数值初值，不能视为新物质态的辐射解。
- 4 workers / 8 CPU / 32G，`qos_stu_cpu_long`，单批最大 8h。8h 是资源时限，不是完成时间预测；预算仍只有 **8 张新 map、每 4 张一轮、最多两轮正式反馈**。
- 所有门通过即停为一个接受的物质步；资源/源码/物理域错误保留证据并停。预算到点仍需 Codex 决定，不由监督模型续交或改阈值。

## 新入口如何复用旧核

`operations/prepare_encoded_backtrack.py` 在 allocation 内验证停止态来源、config/trial SHA、原编码方向恒等式、基准残差和精确物理解码，构造并检查新候选；将原方向、基态所在 NPZ 与新 NPZ 分别固定哈希，写独立声明。

新 trial 在初始化前创建。现有 `pipeline.run --maps-per-job 0 --no-feedback` 只初始化自有辐射槽，检测到已存在的 trial 后不会调用旧 0.0625 迁移。之后调用原诊断 driver，执行 8 张/4 张间隔的独立运行。

额外运行 `audit_native_trial`：经原 `configure_native` 配置后调用实际 `_second_full_material`，逐值核验镜像全柱的密度、温度、H/He 布居确实来自新候选，并验证旧相位与 dt。旧碰撞/转移/正式反馈核不改动；正式反馈适配器仍会验证新 trial 精确编码、SHA 和物理旧时间层。历史 `src/`、`scripts/`、`hpc/`、`diagnostics/` 无修改。

新 worker 消费的是新物质态，存储项仍采用原物理旧时间层；两者不能混为一谈。每个正式反馈对必须由这个候选的新映射端点重算，不复用旧候选的反馈 NPZ。

## 验证与操作

Mac 相关 69 项测试通过，其中新候选 11 项测试覆盖编码/方向、原 dt、基准残差篡改及较小正步长限制；监督新增接口后其与候选共 21 项测试通过。shell 语法检查通过。

Mac 用 Linux 真实 trial 做精确 decode 比较出现架构差异；没有放宽 guard。真实候选和 native 物质注入核验必须在学校 Linux allocation 内通过，失败即退出，不把 Mac 合成测试冒充 Linux 实测。

```bash
TDE_RUN=outputs/hpc/hhe-backtrack-r003125-20260916 \
TDE_SOURCE_RUN=outputs/hpc/hhe-r025-cont64 \
sbatch --parsable operations/encoded_backtrack.sbatch
```

单批直接提交，不创建第二个自动提交者。信号时尽量在现有可恢复边界停止；正式反馈中的超时恢复仍需查实际 manifest，不承诺所有阶段都能在 USR1 后瞬时退出。再次提交同一个 run 前核对队列、声明和输入，准备器验证已有声明，不覆盖旧 run。

平台 Claude watcher 已支持从新 run 配置读取预算及候选，并可直接监督一个 `--science-job JOBID`，保存调度器终态；有界作业结束即交 Codex 审阅，不扩预算。下一次本任务跟进应先读本报告及新 run，cont64 保持归档态。
