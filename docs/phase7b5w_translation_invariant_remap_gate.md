# Phase 7B5w：频率切片平移不变搬移门

预注册：[[phase7b5w_preregistered_translation_invariant_remap|Phase 7B5w 预注册]]  
保留失败：[[phase7b5v_streaming_turning_gate|Phase 7B5v 算子门]]

## 1. 正式结论

`phase7b5w_gate_passed=true`，仅授权下一步完整深度单块资源探针。

- `[V]` 合成切片不变性和正式 9632 组单次 stream256--整体映射均为逐位相同，最大相对
  误差为 0；
- `[V]` 两条路径都在 35 次迭代收敛，末次固定点变化为
  $5.24332\times10^{-11}$；最终强度哈希相同，强度、体积平均谱以及 H I、He I、
  He II 和辐射能标量误差全部为 0；
- `[V]` 新整体解相对保留的 7B5v 整体科学标量最大变化为
  $2.53\times10^{-15}$，说明修正的是加法历史，不是物理结果；
- `[V]` stream256 的峰值 RSS 为 392.08 MiB，而整体路径为 1251.75 MiB；运行时间分别
  为 53.10 s 和 51.98 s。当前实现以约 $2.1\%$ 的单单元时间代价，把峰值内存降至
  整体路径的 $31.3\%$。

Phase 7B5v 的 $3.93775\times10^{-12}$ 单次映射失败仍保留在历史报告中；本阶段没有
改旧结果或旧阈值，而是在新协议下复算。[V]

## 2. 修正为什么有效

频率守恒搬移需要计算 Doppler 平移目标组与源组的交叠积分。前缀和在数学上等价，但
局部 halo 和整体数组从不同频率起点累加，浮点舍入路径不同。局域交叠法使某个目标组
永远只对同一组相交项、按同一顺序求和，因此结果不依赖传入源切片之前还有多少无关频率
组。[A-computational/V]

它没有使用 `nan_to_num`、任意 `clip`、floor、删除失败点或事后重归一化；全局频率边界、
角方向和 turning-ray 处理均保持不变。[V]

## 3. 图像逐图解释

![Phase 7B5w translation-invariant remap gate](../outputs/phase7b5w_translation_invariant_remap_gate.png)

- **(a) Frequency-slice invariance repair**：红柱保留 7B5v 单次映射误差相对旧门为
  3.94；7B5w 局域交叠结果为 0，落在横轴上。虚线 1 是冻结门。
- **(b) Streamed fixed-point equivalence**：最终强度、体积平均谱和最坏标量误差相对门
  均为 0，故柱位于横轴；这不是缺测，而是逐位相同。
- **(c) Recomputed one-cell cost**：蓝柱显示整体与 stream256 的时间接近；红柱显示流式
  路径显著降低峰值 RSS。
- **(d) New monolithic vs Phase 7B5v**：五个科学积分量的变化都远低于历史一致性门，
  说明数值修正没有移动物理解。

## 4. 当前边界

- `[V]` 有界内存频率流式算子已在正式单单元分辨率通过严格等价性门；
- `[V]` turning-ray 算子已由 7B5v 的独立稠密系统、联立残差和能量账本验证；
- `[O]` 尚未实测 4096 辐射深度单块的真实微物理临时量和峰值 RSS；
- `[O]` 尚未授权完整柱固定点、全轨道、物质反馈或 Phase 4 连续谱替换。

机读结果：`outputs/phase7b5w_translation_invariant_remap_summary.json`；隔离状态：
`outputs/phase7b5w_monolithic_state.npz` 与 `outputs/phase7b5w_stream256_state.npz`。
