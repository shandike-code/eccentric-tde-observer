# Phase 7B7f：全局拼接辐射态的正式源项诊断

上游：[[phase7b7e_radiation_direction|Phase 7B7e 块内诊断失败]]

## 问题定位

7B7e 的每个 block-Jacobi 工作进程先更新自己的 128 组核心频带，但邻块 halo 仍读取第 30
次旧强度。这是一次并行 Jacobi 映射所需的正确内部状态，却不是同一个全局新辐射场。
因此可以用它生成下一次拼接强度，但不能在“新核心 + 旧 halo”上提取最终物理源项。`[V]`

7B7f 不执行新的输运或物质更新，而是先拼接 76 个新核心，再让每个块的核心和全部物理
halo 同时读取这个全局新态，重新计算三条路径：

$$
Q_{\rm rate}
=
4\pi\int
\left(\kappa_{\nu}J_{\nu}-\eta_{\nu}\right)\,\mathrm{d}\nu,
$$

$$
Q_{\rm direct}
=
-\int G^{0}_{\nu,{\rm com}}\,\mathrm{d}\nu,
$$

$$
Q_{4}
=
-\gamma\left(G^{0}_{\rm lab}-\beta cG^{1}_{\rm lab}\right).
$$

## 结果

| 诊断 | block-lagged 7B7e | 全局拼接 7B7f | 门 |
|---|---:|---:|---:|
| $Q_{\rm rate}$--$Q_{4}$ 体积 $L_{1}$ | $5.50037\times10^{-3}$ | $7.33758\times10^{-6}$ | $<10^{-3}$ |
| $Q_{\rm rate}$--$Q_{4}$ 柱积分比例 | $3.84317\times10^{-2}$ | $5.23835\times10^{-5}$ | $<10^{-3}$ |
| $Q_{\rm rate}$--$Q_{\rm direct}$ 体积 $L_{1}$ | -- | $1.95423\times10^{-12}$ | $<10^{-8}$ |

旧 7B7e 两个失败量分别以相对误差 $7.88\times10^{-16}$ 和
$7.04\times10^{-15}$ 被重新回收，没有覆写或删除原失败。全局拼接态的三条路径全部通过
冻结门，因此已把原因定位为正式诊断时机，而不是 Lorentz 四力或 Milne 率本身失效。
`[V]`

![Phase 7B7f assembled-state formal diagnostics](../outputs/phase7b7f_assembled_diagnostics.png)

图 (a) 显示逐块有符号差异在阈值附近仍很大；图 (b) 才揭示关键区别：旧 halo 的累积
差异在完整频带末端留下约 3.8%，全局新 halo 则抵消到 $5.24\times10^{-5}$；图 (c)
显示拼接态的深度加热曲线重合；图 (d) 给出三项正式门。`[V]`

## 资源门与结论边界

单个长寿命后处理进程的峰值 RSS 为 $6983.47\,\mathrm{MiB}$，超过 6 GiB，故 7B7f
科学门通过但总门失败。它仍不是辐射固定点或耦合固定点，不授权第二次物质更新、完整轨道
或 Phase 4 替换。资源闭合见[[phase7b7fr_resource_closure|Phase 7B7f-r]]。`[V/O]`
