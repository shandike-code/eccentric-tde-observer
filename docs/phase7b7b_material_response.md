# Phase 7B7b：一次冻结辐射物质响应为何被拒绝

上游：[[phase7b7ar_resource_closure|Phase 7B7a-r 资源闭合]]

## 不双算辐射能的物质账本

正式输运已经显式保存辐射能，因此物质比能只取

$$
e_{\rm mat}=e_{\rm gas}+e_{\rm ion},
$$

而不再加入局域 $aT^{4}/\rho$。一次冻结辐射响应使用实际相位时长
$\Delta t=889.4199\,\mathrm{s}$：

$$
e^{n+1}_{\rm mat}
=
e^{n}_{\rm mat}
+
\frac{\Delta t}{\rho}Q_{\rm rate}.
$$

H/He 布居用电荷中性后向 Euler 推进；碰撞电离和三体复合保持关闭，与上游基态 Milne
闭合一致。没有温度 floor、布居裁剪、删点或事后归一化。`[A-preregistered]`

## 结果

| 量 | 结果 |
|---|---:|
| 最大电荷残差 | $2.187\times10^{-16}$ |
| 最大粒子守恒残差 | $2.220\times10^{-16}$ |
| 最大物质能量残差 | $2.125\times10^{-16}$ |
| 最大布居变化 | $2.329\times10^{-6}$ |
| 最大局域能量增量/初始物质能 | $9.4669$ |
| 最大相对温变 | $36.1415$ |
| 候选最高温度 | $7.513\times10^{5}\,\mathrm{K}$ |

守恒和物理域均通过，但预注册的 10% 信赖域严重失败。因此保存的文件明确命名为
`phase7b7b_unaccepted_material_candidate.npz`，不得作为新物质态回写辐射场。`[V]`

![Phase 7B7b material response](../outputs/phase7b7b_material_response.png)

图 (a) 比较原温度与未接受候选；图 (b) 显示靠表面单元的温变远超 10% 门；图 (c) 说明
基态布居几乎不动，所以失败主要是热能响应；图 (d) 定位同一表层区域的物质能强迫高达数倍。
这不是求解器发散，而是冻结辐射近似在完整相位步上不再是小扰动。`[V/O]`

进一步定位见[[phase7b7c_timescale_diagnosis|Phase 7B7c]]。

