# Phase 7B5r：9632 组单单元角度--辐射子网格联合门预注册

> [!summary] 协议结论
> `[A-preregistered/O]` 用户已明确批准把 9632 组作为新频率预算，并批准下一步只做单单元
> 角度--辐射子网格门。本协议不授权全柱、全轨道、物质反馈、Phase 4 替换或 UVOT。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5q_converged_fixed_point_resource|Phase 7B5q]] ·
[[eccentric_tde_observer/docs/phase7b5r_joint_convergence|Phase 7B5r 结果]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]

## 1. 冻结输入与定位

本阶段固定使用 Phase 7B5o 已通过能量及 H/He 光致电离率门的 9632 组 master，以及
Phase 7B5p/7B5q 已暴露的 `signed width change q80` 单单元压力状态。它不是新的独立科学
留出，而是生产配置的数值收敛门。`[A-preregistered/V]`

7B5q 的输入实际包含 8 个覆盖 $[-1,1]$ 的 Gauss--Legendre 方向；旧文档把它写成 S16 是
标签错误，不是 16 方向计算。本阶段把这一事实显式冻结，并比较 8、16、24 个方向。`[V]`

## 2. 预声明配置

角度路径固定为：

- 8、16、24 方向，均使用 1 个父单元；
- 16 对 24 是角度生产门，8 对 24 是较粗控制。

辐射深度路径固定为：

- 每个父物质单元使用 8、16、32 个辐射子单元，均使用 16 个方向；
- 16 对 32 是辐射子网格生产门，8 对 32 是较粗控制。

联合门固定比较 16 方向×16 子单元候选与 24 方向×32 子单元参考。每个配置都从算子默认
辐射场开始，不插值角度或深度 warm start。`[A-preregistered]`

## 3. 子网格保持了什么

父单元的新旧边界都按同一仿射坐标细分；每个子单元重复父单元的速度、温度、密度和 H/He
布居。因此新增的只是辐射强度和散射源函数的深度自由度，不重定义物质场，也不平滑真实
梯度。`[A/V]`

## 4. 比较量和门槛

每个比较同时覆盖：频率积分的体积平均共动强度、H I/He I/He II 光致电离率、末态辐射
面密度、双侧逸出通量、积分物质加热以及体积平均共动谱的加权 L1 差。角度、子网格和联合
三个生产比较中的每一项都必须严格低于 $10^{-3}$。`[A-preregistered]`

标量差异在运行前定义为

$$
\epsilon(q)
=
\frac{|q_{\rm c}-q_{\rm r}|}
{\max(|q_{\rm c}|,|q_{\rm r}|)},
$$

若两者都为零则直接使用绝对差。谱差定义为

$$
\epsilon_{\rm J,1}
=
\frac{\int |J_{\nu,\rm c}-J_{\nu,\rm r}|\,\mathrm{d}\nu}
{\max\!\left(\int |J_{\nu,\rm c}|\,\mathrm{d}\nu,
\int |J_{\nu,\rm r}|\,\mathrm{d}\nu\right)}.
$$

这里没有事后选择只通过的量，也没有对接近零的结果添加任意 floor。`[A-preregistered]`

每个独立固定点还必须满足：

- 固定点容差为 $10^{-10}$，最多 8192 次迭代；
- 全局联立残差和绝对能量账本残差严格低于 $10^{-9}$；
- 最小强度不低于 0；
- 物理频率组必须恰为 9632，边界哈希不得改变；
- 不使用 `nan_to_num`、无物理理由的 `clip`、floor、失败点删除或事后重归一化。

## 5. 授权边界

本协议明确设置 `frequency_budget_changed=true`、`frequency_group_budget=9632` 和
`angle_or_radiation_subgrid_gate_authorized=true`。全柱、全轨道、物质反馈、Phase 4 替换和
UVOT 仍全部为 `false`。即使单单元门通过，也不能直接外推这些下游阶段。`[O]`

## 6. 机器协议

机器协议写入
`outputs/phase7b5r_preregistered_joint_convergence_protocol.json`，冻结 SHA-256 为
`ff7a39925d5819d0267594a4221467ed211a634f3e5761b0575698d2c6675c0f`。结果脚本必须逐项
复核协议及全部源文件哈希。`[V]`
