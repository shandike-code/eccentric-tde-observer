# Phase 7B5t：特征分区角求积与精确单元特征输运预注册

> [!summary] 协议结论
> `[A-preregistered/O]` 7B5s 已证明全区间角求积和一阶迎风深度离散都未达到
> $10^{-3}$。本阶段只替换数值角求积与空间形式解，不改变 ZO 状态、9632 组频率表示、
> 连续碰撞系数或固定点容差。候选必须同时通过解析阶数、守恒、非负性、实际压力单元
> 角度/深度/联合连续量和 $6\,\mathrm{GiB}$ 资源门。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5s_refined_joint_convergence|Phase 7B5s]] ·
[[eccentric_tde_observer/docs/phase7b5t_characteristic_transport_gate|Phase 7B5t 结果]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]

## 1. 冻结假设

角求积在移动网格入射特征分界

$$
\mu_{\rm split}
=
\frac{w_{\rm left}+w_{\rm right}}{2c}
$$

两侧分别使用 Gauss--Legendre 节点。该分界由已冻结的 ALE 网格速度唯一确定，不是通过
结果拟合的自由参数。`[A-preregistered]`

空间候选在每个单元内把消光、发射率和旧时刻平均强度视为常数，把网格速度视为线性函数，
精确积分后向 Euler 特征方程。相邻单元共享同一个界面强度，因此能量通量仍保持有限体积
守恒；不使用负值裁剪、floor 或事后重归一化。`[A-preregistered]`

## 2. 解析门

- 线性源吸收板层：一阶迎风观测阶必须位于 $0.8$--$1.2$，特征积分观测阶必须高于
  $1.8$；
- 常源后向 Euler 板层：特征积分最大误差必须低于 $10^{-11}$；
- 线性移动网格：全局残差和能量账本必须低于 $10^{-10}$；
- 所有强度必须非负，禁止数值修补。`[A-preregistered]`

## 3. 实际压力单元门

冻结七个配置：旧迎风的 32×32、32×64、48×32，以及特征积分的 32×16、32×32、
32×64、48×32。全部使用特征分区角求积。生产候选为特征积分 32×16，联合参考为
特征积分 48×32。

以下比较的八个连续量都必须严格低于 $10^{-3}$：

- 特征分区角度：32×32 对 48×32；
- 特征积分深度候选：32×16 对 32×32；
- 特征积分深度确认：32×32 对 32×64；
- 联合候选：特征积分 32×16 对 48×32。

旧迎风 32×32 对 32×64 只用于确认 7B5s 慢深度误差是否仍在，不参与放宽候选门。
`[A-preregistered]`

## 4. 授权边界

本阶段通过时只接受一个单单元辐射生产离散。全柱、全轨道、温度--布居反馈、Phase 4
替换和 UVOT 仍需后续独立门，不由本协议自动打开。`[O]`

机器协议写入
`outputs/phase7b5t_preregistered_characteristic_transport_protocol.json`；生成后冻结其
SHA-256。`[V]`

冻结 SHA-256 为
`bd07fa6bc3007f3dd668baa2e205cb655364f6fa7e2af1959046f0c5cefc8400`。`[V]`
