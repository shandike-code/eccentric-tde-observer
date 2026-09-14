# Phase 7B7h：第二条固定物理时间层 Picard 方向

上游：[[phase7b7g_assembled_atomic_rates|Phase 7B7g 全局原子率]]

## 固定时间层，而不是重复走一次 $\Delta t$

后向 Euler 完整候选始终从同一个物理旧时间层构造：

$$
e_{\star}^{(n+1)}
=
e^{0}
+
\Delta t\,
\frac{Q^{(n)}}{\rho}.
$$

数值迭代则从当前非线性状态沿这个候选方向阻尼：

$$
e^{(n+1)}
=
e^{(n)}
+
\lambda_{n}
\left(e_{\star}^{(n+1)}-e^{(n)}\right).
$$

因此程序没有把同一个 $889.4199\,\mathrm{s}$ 再累加一次。`[V]`

## 结果

| 量 | 结果 |
|---|---:|
| 求解器阻尼 $\lambda_{2}$ | $1.46058\times10^{-3}$ |
| 最大相对温度改变 | $0.05$ |
| 最大物质能增量比 | $1.35868\times10^{-2}$ |
| 最大布居改变 | $2.77\times10^{-9}$ |
| 物质能回算残差 | $1.64\times10^{-16}$ |
| 粒子数残差 | $2.22\times10^{-16}$ |

![Phase 7B7h second fixed-time-level Picard direction](../outputs/phase7b7h_second_picard_direction.png)

图 (a) 将物理旧时间层、当前迭代、完整候选和接受后状态分开；图 (b)
显示温度改变在表层恰好到达 $5\%$ 信赖域；图 (c) 使用 symlog 同时显示远大于
信赖域的完整能量方向与已接受阻尼方向，没有对数据加 floor；图 (d) 直接验证
旧时间层和 $e^{0}+\Delta t Q/\rho$ 的基准未改变。`[V]`

## 授权边界

本阶段通过物质信赖域和守恒门，只授权
[[phase7b7i_second_radiation_map|Phase 7B7i]] 做一次全频辐射方向映射。它还不是耦合
固定点。`[O]`
