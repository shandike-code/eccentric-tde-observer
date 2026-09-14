# Phase 7B7k：朴素 Picard 非线性成本决策

上游：[[phase7b7j_second_assembled_feedback|Phase 7B7j 正式反馈与残差]]

## 这是成本外推，不是收敛定理

若暂时把实测收缩因子 $q$ 视为不变，从当前残差 $r$ 到目标
$r_{\rm target}=10^{-3}$ 所需的剩余循环数为

$$
N_{\rm remain}
=
\left\lceil
\frac{\ln\left(r_{\rm target}/r\right)}{\ln q}
\right\rceil.
$$

这个外推不假定 $q$ 真的恒定，也不是运行时保证；它只用于判断是否值得机械地
继续当前算法。`[A-diagnostic]`

## 实测成本

一个完整耦合循环的实测墙钟为

$$
t_{\rm cycle}
=
395.24\,\mathrm{s}
+
283.55\,\mathrm{s}
=
678.79\,\mathrm{s}.
$$

| 残差指标 | 实测 $q$ | 外推剩余循环 | 外推墙钟 |
|---|---:|---:|---:|
| 质量加权 | $0.927365$ | $70$ | $13.2\,\mathrm{h}$ |
| 原最差单元 | $0.998500$ | $4601$ | $36.1\,\mathrm{d}$ |

![Phase 7B7k nonlinear cost decision](../outputs/phase7b7k_nonlinear_cost_decision.png)

图 (a) 显示两个残差指标都小于 $1$，因此当前方向并非数值发散；但最差单元几乎
不动。图 (b) 将恒定收缩外推与 20 循环的资源策略上限比较；图 (c) 列出目前
残差、实测单循环耗时和算法决策。`[V/A]`

## 决策

1. 当前点不是耦合固定点。`[V]`
2. 不授权第三次相同的 $5\%$ 信赖域朴素 Picard 更新。`[A-resource-policy/V]`
3. 下一阶段必须先设计受保护的非线性加速，并使用新的全局辐射映射检验其残差；
   不能只用冻结辐射候选的漂亮温度曲线代替验证。`[O]`
4. 全轨道、Phase 4 替换、UVOT 和真实线形成仍未授权。`[O]`
