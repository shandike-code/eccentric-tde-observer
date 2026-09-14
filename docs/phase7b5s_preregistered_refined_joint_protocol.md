# Phase 7B5s：更细 9632 组单单元联合参考预注册

> [!summary] 协议结论
> `[A-preregistered/O]` 7B5r 已否决 16×16，本阶段只在同一已授权单单元范围内加密为
> 24/32/48 方向和 32/64 辐射子单元。32×32 候选必须同时通过角度、子网格、联合连续量
> 与 6 GiB 单进程资源门，才可接受；下游授权保持关闭。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5r_joint_convergence|Phase 7B5r]] ·
[[eccentric_tde_observer/docs/phase7b5s_refined_joint_convergence|Phase 7B5s 结果]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]

## 1. 为什么继续加密

7B5r 中 16 对 24 方向、16 对 32 子单元和联合门分别失败到
$5.448\times10^{-3}$、$1.482\times10^{-2}$、$9.589\times10^{-3}$。误差随加密下降，
但 24×32 尚未被证明自身足够细，因此不能把它直接升级为生产配置。`[V/O]`

## 2. 冻结配置

本阶段运行五个全新进程：24×32、32×32、48×32、32×64、48×64。三个生产比较为：

- 角度门：32×32 对 48×32；
- 子网格门：32×32 对 32×64；
- 联合门：32×32 对 48×64。

24×32 只作为较粗角度控制。所有配置都使用 9632 个相同频率组、同一暴露压力单元和算子
默认初值；不使用跨角度或跨深度插值 warm start。`[A-preregistered]`

## 3. 连续量与误差

比较量和误差定义与 7B5r 完全相同：频率积分体积平均共动强度、H I/He I/He II
光致电离率、末态辐射面密度、双侧逸出通量、积分物质加热和体积平均共动谱 L1 差。每项
都必须严格低于 $10^{-3}$；不能只挑已通过的量。`[A-preregistered]`

## 4. 资源门

主机物理内存为 16 GiB，预注册前的系统可用比例为 $59\%$。7B5r 的 24×32 实测峰值为
$1046.47\,\mathrm{MiB}$；48×64 的活跃未知量恰为其四倍。为避免把系统换页误当作科学
运行可行性，本阶段预先要求每个新进程峰值严格低于 $6144\,\mathrm{MiB}$。超过上限就保留
结果并判失败，不继续到全柱。`[A-preregistered/V]`

## 5. 不变的物理与授权边界

子单元仍只增加辐射深度自由度，不重定义父单元速度、温度、密度或 H/He 布居。9632 频率
预算保持已授权；全柱、全轨道、物质反馈、Phase 4 替换和 UVOT 均未授权。`[A/O]`

机器协议写入 `outputs/phase7b5s_preregistered_refined_joint_protocol.json`；冻结 SHA-256
为 `ac1d65d0d7b66b03545dd7cfc3e93e6e43bd3aa9fe66af71f9853eae7cbd75a2`。`[V]`
