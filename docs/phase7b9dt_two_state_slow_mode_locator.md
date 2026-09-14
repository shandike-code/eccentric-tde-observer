# Phase 7B9dt 两态慢模定位

阶段关系见
[[eccentric_tde_observer/docs/phase7_checkpoint_inventory|Phase 7 辐射检查点清单]]。

## 1. 诊断目的与边界

Phase 7B9dt 比较 Phase 7B9dp 结束时最后一张纯 Picard 映射的输入态与输出态，按自然频率块
复算 original-operator residual，并定位控制残差分子的数组元素。它回答“当前两态之间最慢变化
出现在哪里”，不改变固定点方程、收敛阈值或任何辐射态。[V]

这是一项只读诊断，而不是新的迭代、单块修补或收敛加速。诊断没有授权 material feedback，
也没有授权 radiation update；它不能单独证明固定物质辐射场已经收敛。[O]

## 2. 复算定义

对输入辐射态和一次原算子映射态，使用的全局残差为

$$
R_{\rm op}
=
\frac{
\max_{g,\mu,k}
\left|
I^{\rm mapped}_{g,\mu,k}
-
I^{\rm input}_{g,\mu,k}
\right|
}{
\max\left[
\max_{g,\mu,k}\left|I^{\rm input}_{g,\mu,k}\right|,
\max_{g,\mu,k}\left|I^{\rm mapped}_{g,\mu,k}\right|
\right]
}.
$$

其中 $g$、$\mu$ 和 $k$ 分别是频率组、角度和深度数组索引。这里的 angle 0 和 depth 2304
首先是数组位置；若没有同时读取坐标映射，不能把它们直接解释成某个连续角度或几何高度。[O]

76 个自然频率块无重叠、无遗漏地覆盖 9632 个频率组，每块 128 组。复算得到

$$
\max\left|\Delta I\right|
=9.236059125353191\times10^{-6},
$$

$$
I_{\rm scale}
=4.111427191865178\times10^{-2},
$$

以及

$$
R_{\rm op}
=2.2464362602912075\times10^{-4}.
$$

该值与结束态 summary 保存的 reference residual 逐位相同，绝对差为 0；这是 residual exact
reproduction。[V] 它仍高于固定目标 $10^{-4}$，因此该两态不能通过目标门。[V]

## 3. 慢模定位结果

控制全局残差分子的元素位于：

- frequency group 3011；
- natural-frequency block 23；
- angle index 0；
- depth index 2304；
- 几何中心能量 9.096785069214262 eV，报告时记为 9.10 eV；
- 输入值 0.02615044555027702，映射值 0.026159681609402373。[V]

全局归一化尺度并不在同一个元素上。它来自 mapped state 的 frequency group 3308、angle
index 0、depth index 2048，对应 13.64024098840678 eV，报告时记为 13.64 eV。[V]
因此，block 23 自己的局域比值 $3.062505158403034\times10^{-4}$ 不等于全局
$R_{\rm op}$：前者使用本块尺度，后者使用全部频率、角度和深度上的统一最大尺度。[V]

9.10 eV 的分子控制点和 13.64 eV 的全局尺度点给出了后续物理排查的精确坐标，但能量位置
接近某条原子阈值本身不能证明原子过程就是慢模成因；要建立因果解释仍需独立的算子分解或受控
扰动实验。[O]

## 4. 图像与逐面板分析

![Phase 7B9dt two-state slow-mode locator](../outputs/phase7b9dt_two_state_slow_mode_locator.png)

### 面板 (a)：逐块分子与尺度

蓝线是每个自然频率块的 maximum absolute change，橙线是相应 maximum state scale；纵轴采用
对数尺度。[V] 蓝线在 block 23 达到全局最大，对应 9.10 eV 的 group 3011。橙线则在 block
25 达到块级最大；逐元素审计进一步把全局尺度定位到 group 3308 的 13.64 eV。[V]

高频端两条曲线跨越许多数量级下降，说明某些块虽然有较大的“块内相对残差”，绝对强度和绝对
变化却极小。因此不能把面板 (b) 高频端最大的块内比值直接当作控制全局 residual 的证据。[V]

### 面板 (b)：按控制频率定位块内相对残差

蓝线给出各块的局域相对残差，灰色虚线只标记全局目标 $10^{-4}$，红点标出控制全局分子的
block 23。[V] 红点并不是蓝线的最高点：数百 eV 以上的稀薄高频尾部可因本块尺度极小而出现
更大的局域比值。全局验收必须使用第 2 节的统一分母，不能改成逐块分母后取最大值。[V]

图中的英文标题、坐标轴、图例和标记均为图像产物的正式标签；中文文档只解释其物理和数值
含义。[V]

## 5. 初次接线的安全拒绝

7B9dt 第一次连接真实 7B9dp 结束态时安全拒绝：结束态协议使用
`diagnostic_frequency_block`，而定位器初版只读取 `core_frequency_groups`。兼容读取修复后，
相关测试在当时得到 28 passed，随后才允许真实只读诊断运行。[V]

这次拒绝没有通过猜测字段、跳过协议检查或更改阈值来绕开。修复只统一协议字段接口，残差定义、
频率分块和 $10^{-4}$ 目标均保持不变。[V]

## 6. 产物与可复核范围

- `outputs/phase7b9dt_two_state_slow_mode_summary.json`：全局残差、控制索引、哈希和判决；
- `outputs/phase7b9dt_two_state_slow_mode_blocks.json`：76 块完整机器可读记录；
- `outputs/phase7b9dt_two_state_slow_mode_blocks.csv`：同一逐块记录的表格视图；
- `outputs/phase7b9dt_two_state_slow_mode_locator.png`：英文双面板诊断图。[V]

summary 明确记录 `diagnostic_only=true`、`convergence_proven=false`、
`material_feedback_authorized=false` 和 `radiation_update_authorized=false`。[V] 因而该结果只把
残差定位到具体频率、角度和深度索引；它既不授权材料反馈，也不替代后续 fresh-map 收敛判决。[O]
