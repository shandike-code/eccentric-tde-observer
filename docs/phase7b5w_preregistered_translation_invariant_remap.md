# Phase 7B5w：频率切片平移不变搬移预注册

上游失败：[[phase7b5v_streaming_turning_gate|Phase 7B5v 流式频率块与 turning-ray 算子门]]  
执行报告：[[phase7b5w_translation_invariant_remap_gate|Phase 7B5w 平移不变搬移门]]

## 1. 为什么另立新门

Phase 7B5v 的最终流式固定点与整体解已经一致到 $10^{-12}$ 量级，但预注册的单次
256 核心组映射误差为 $3.93775\times10^{-12}$，严格高于 $10^{-12}$ 门。该失败不能
靠放宽门槛或舍入数字消失，因此 7B5w 在查看新结果前冻结一种数值舍入修正
`[A-preregistered]`。

旧实现先从频率切片左端构造全前缀和。整体数组和局部 halo 的前缀起点不同，因而同一
物理交叠积分会经历不同的浮点加法历史。新候选只对与每个 Doppler 平移目标区间实际
相交的源组，按频率从低到高作直接有序求和：

$$
\int_{\nu_{i-1/2}'}^{\nu_{i+1/2}'} I_{\nu}\,{\rm d}\nu
=
\sum_{j\in\mathcal O_{i}}
I_{j}\,\Delta\nu_{\rm ij},
$$

其中 $\mathcal O_{i}$ 仅包含与目标区间相交的源组，$\Delta\nu_{\rm ij}$ 是真实交叠宽度。
这不改变 9632 个正式全局频率边界，不重归一化谱，也不修改碰撞、Lorentz 或空间输运
方程。

## 2. 冻结门槛

- 合成全数组与切片输入必须低于 $2\times10^{-15}$；
- 正式 9632 组单次 stream256 对整体映射必须低于 $10^{-12}$；
- 收敛固定点的强度、体积平均谱和 H/He/能量标量误差必须低于 $10^{-10}$；
- 新整体科学标量相对保留的 7B5v 整体结果必须低于 $5\times10^{-9}$；
- 每个隔离进程峰值 RSS 必须低于 6144 MiB，强度必须非负；
- 频率组数和活动边界哈希必须不变。

## 3. 权限边界

若全部通过，只授权正式完整深度的单块资源探针；不授权全轨道、物质反馈、Phase 4
替换或 UVOT。7B5v 的正式失败记录继续保留。

机读协议：`outputs/phase7b5w_preregistered_translation_invariant_remap.json`；冻结协议
SHA-256 为
`8bc2abc306eee0797934395d42b4b23a4fa1ff18ac4674acd4b05c79afdec6cb`。
