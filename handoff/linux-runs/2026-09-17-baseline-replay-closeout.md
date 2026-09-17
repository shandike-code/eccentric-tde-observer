# 基态同尺度重放收尾与下次接手

用户因额度不足要求收尾。停止新实验、自动续交和 Claude 调用；自动跟进 `ustc-hhe` 已暂停。收尾时核查队列为空，学校工作树干净。没有在后台继续运行的本轮作业。

## 本轮实际完成

- 新代码 `operations/replay_equation_baseline.py`、对应 sbatch、测试、输入清单及事前声明已提交 `216a1fe`，推送 GitHub 分支 `ustc-hpc-diagnostics` 并快进同步到学校。
- 42 项相关测试在 Mac 和 Linux 均通过；它们验证组件和合成控制，不能代替真实历史工件重放。
- 14 个历史小工件上传到学校独立目录 `outputs/baseline-audit-inputs-20260917/`，没有覆盖历史结果，没有传输 `.dat`。压缩包 17,698,450 字节，SHA256 `f27e42e510258aab208a39e470c07cbb3ad3ca595682b53c3a28a10c5441c1f6`。逐文件清单：`handoff/evidence/ustc-baseline-input-package-20260917.json`。
- 默认 4 CPU / 16G 作业 **71878** 在 2026-09-17 14:39:52 启动、14:39:57 以 **FAILED / 1:0** 退出，耗时 5 秒。run：`outputs/hpc/equation-baseline-replay-20260917`。
- 报错 `legacy response replay parity failed`：在基态最后反馈的物质响应重放与归档旧 encoded 残差比较处失败。预设 `rtol=1e-11, atol=3e-13` 未通过。未修改容差，未提交重试。

证据：`handoff/evidence/ustc-baseline-replay-failure-20260917.json` 保存 scheduler 原文、stderr、应用状态、Git SHA 和空队列；学校 run 内另存 `scheduler-closeout.json`。

## 能说与不能说

代码在上述报错前已走过包清单/哈希、历史频率源码精确重建及合成正路径迁移检查、旧物理时间层身份检查和基态响应调用。旧协议源码差异没有被静默绕过。

但是，失败处没有写出数值差异向量；目前不知道最大差异、所在分量和单元，也不能判断是跨平台舍入、布居求解、历史来源或实现问题。不能将此次失败称为“只有舍入误差”，也不能据此判定隐式物理解不存在。

本次未生成 `baseline_comparison.json`，尚未进入候选比较。没有同尺度基态/候选收缩率的新结论，没有新方向，没有新 map，没有接受物质步。此前 71816 关于加热相消减弱的定位结果保留。

## 用户恢复工作后按此顺序继续

1. 核对 Git、队列和 SSH；不要重跑已经完成的 71816 定位，也不要恢复旧 map 监督器。
2. 在独立 `operations/` 调试入口中补齐失败诊断：保存重放和归档的旧残差数组、两者差值、最差分量/单元、逐分量绝对及相对差异、非有限检查；记录 NumPy/SciPy/BLAS 和相关源 SHA。先输出证据，再执行原一致性判定，避免失败时丢失诊断。
3. 使用同一小工件包，在新的默认 4 CPU allocation 内重放；对照原 `frozen_radiation_material_response`、新账本和 codec 的运算路径，检查原基态、旧时间层、布居率及 stored target 与 residual 的相互身份。不要提前认定是平台误差，不直接扩大容差。
4. 解释并解决差异后，才完成同尺度基态/候选比较；同时报告 L2、质量加权、最差单元及基态和候选各自相邻漂移。相邻漂移不是到收敛解的误差上界，不能替代原噪声门。
5. 依据结果再选择有界内层精度实验或新方向诊断。任何新物质候选必须重新计算对应辐射和反馈；禁止冻结旧 Q 冒充真实 Jacobian，禁止改 dt、floor、clip 或丢弃失败层。

继续暂停自动跟进，直到用户明确恢复。无需在此期间循环检查空队列。
