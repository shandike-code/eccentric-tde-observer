# Phase 7B9e--7B9e2：基准辐射科学泛函续算

上游：[[phase7b9d_inner_gate_audit|Phase 7B9d 基准辐射内迭代门审计]]

## 冻结的收敛定义

固定物质态的第 $k$ 次源映射写为 $\mathcal{M}[I^{(k)}]$。本阶段记录全局尺度变化

$$
r_{k}
=
\frac{\left\|\mathcal{M}[I^{(k)}]-I^{(k)}\right\|}
{\left\|I^{(k)}\right\|},
$$

以及相邻正式边界谱的归一化 $L_{1}$ 变化和 bolometric 相对变化。准入要求 $r_{k}<10^{-4}$，
两个边界量均小于 $10^{-3}$，并且至少连续两轮通过；只允许在偶数附加映射编号停止。
`[A-preregistered]`

源、微物理、$9632$ 个物理频率组、32 个角方向、4096 个辐射深度单元和松弛
$\omega=1$ 全部冻结。这里没有物质反馈、裁剪、floor、删点或事后重归一化。`[V]`

## 原预算与最小扩展

![Phase 7B9e science-functional continuation](../outputs/phase7b9e_science_functional_continuation.png)

图 (a) 显示附加映射 1--8 的源变化从 $4.99547\times10^{-4}$ 单调降到
$8.32757\times10^{-5}$；图 (b) 显示边界谱和 bolometric 量始终低于各自门槛；
图 (c) 保留但不再使用旧块内账本；图 (d) 给出每轮进程峰值，最高
$4063.69\,\mathrm{MiB}$，低于 $6144\,\mathrm{MiB}$ 门。第 8 轮只是第一次通过源门，
所以原预算按规则失败，不能把单点通过解释成收敛。`[V]`

![Phase 7B9e2 minimal extension](../outputs/phase7b9e2_science_functional_extension.png)

7B9e2 在独立缓冲区中只增加附加映射 9--10，不覆盖 7B9e 终态。图中横轴是“当前物质态
上的总源映射次数”，所以附加映射 9--10 对应总次数 10--11。最终三次连续源变化为
$8.32757\times10^{-5}$、$6.75538\times10^{-5}$ 和 $5.53863\times10^{-5}$；最终边界
谱 $L_{1}$ 与 bolometric 变化分别为 $2.09312\times10^{-4}$ 和
$1.06225\times10^{-4}$。蓝色区标出两轮最小扩展。`[V]`

## 决策

固定物质基准辐射态通过科学泛函内收敛门，允许比较最后两个完整辐射态的正式 H/He 率与
加热，并由此构造基准物质残差。它仍不是耦合动态 NLTE 解，也不授权 Phase 4 替换、UVOT、
全轨道或真实线形成。`[V/O]`

