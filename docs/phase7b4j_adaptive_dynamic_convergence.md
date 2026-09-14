# Phase 7B4j：自适应拉格朗日深度与高时间分辨率审计

证据标记：`[V]` 代码验证；`[A]` 工作假设；`[A-classification]` 数值分类阈值；`[O]`
未解决问题。

关联文档：

- [[eccentric_tde_observer/docs/phase7b4i_periodic_dynamic_energy|Phase 7B4i 周期动态能量柱]]；
- [[eccentric_tde_observer/docs/phase7b4k_error_estimated_dynamic_convergence|Phase 7B4k 双网格误差与 2048 相位审计]]；
- [[eccentric_tde_observer/docs/phase7b4h_hydrostatic_table_gate|Phase 7B4h 静力大气表准入门]]；
- [[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]；
- [[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]。

## 1. 本阶段回答什么

Phase 7B4i 已通过周期能量、电荷、粒子数和初态独立性，但固定深度网格对 He 电离前沿的
人口误差不收敛，128 个轨道相位点也不能解析近心点附近的快速变化。7B4j 因此只回答两个
数值问题：

1. 一个不随相位移动的自适应拉格朗日质量网格，能否比原固定网格更有效地解析温度、
   Rosseland opacity 和 He III 前沿？
2. 把轨道时间网格提高到 1024 个相位点后，512 点解是否达到生产目标？

本阶段不增加新原子物理，不把局域 $J_{\nu}=B_{\nu}(T)$ 升级成非局域转移，也不生成新的
观察者谱。`[A/O]`

## 2. 显式质量边界接口

半柱继续使用从表面到中面的拉格朗日质量分数

$$
x=\frac{m}{m_{0}},\qquad 0\le x\le1.
$$

原固定网格的边界是

$$
x_{j}=\left(\frac{j}{N}\right)^{2},
$$

它只按预设幂律加密表面。7B4j 为 `build_zo_constrained_n3_column` 和
`build_periodic_dynamic_half_column` 增加显式 `mass_fraction_edges` 接口；边界必须有限、
严格递增、数目为 $N+1$，并精确覆盖 $[0,1]$。密度仍由每个单元的 $\Delta m/\Delta z$
直接构造，因此没有事后质量重归一化。`[V]`

同一组边界用于完整轨道的全部相位，所以每个单元始终代表同一批物质；这不是随时间重映射
的 Eulerian 网格。`[V]`

## 3. 轨道全局监视函数

先用 12 个固定半柱单元、64 个轨道相位求 pilot 解。对任一 pilot 场 $y(t,x)$，定义轨道
最大梯度包络

$$
g_{y}(x)=\max_{t}\left|\frac{\partial y}{\partial x}\right|,
$$

并分别归一化为

$$
G_{y}(x)=\frac{g_{y}(x)}{\int_{0}^{1}g_{y}(x')\,{\rm d}x'}.
$$

正式监视函数为

$$
M(x)=1+G_{\ln T}(x)+G_{\ln\kappa_{\rm R}}(x)+G_{X_{\rm HeIII}}(x).
$$

三个物理分量各自具有单位积分，常数基线和每个分量具有相同总贡献；没有可调权重，也没有
为了改善结果而挑选某个相位。常数项防止网格全部塌缩到表面电离前沿。`[A/V]`

新边界满足等监视量条件

$$
\frac{\int_{0}^{x_{j}}M(x)\,{\rm d}x}
{\int_{0}^{1}M(x)\,{\rm d}x}
=\frac{j}{N}.
$$

24 单元网格的最小和最大质量分数宽度分别为 $2.7223\times10^{-3}$ 和 $0.15821$，等分残差
为 $2.78\times10^{-17}$。这证明网格构造正确，不等于物理解已经收敛。`[V]`

## 4. 比较量与失败状态

深度审计以自适应 24 单元解为当前有限分辨率参考，并比较固定和自适应 8、12、16 单元解。
这个 24 单元解只是共同参考，不被称为连续极限。`[A]`

误差分为四组：

- 表面出射能流的最大相对误差；
- 257 个共同质量坐标上的温度、opacity 最大相对误差，以及 H II、He III 最大绝对误差；
- 以 $\Delta m$ 加权的柱平均温度、opacity 和人口误差；
- $X_{\rm HeIII}=0.5$ 前沿的位置与状态。

前沿状态保留为 `all_above_half`、`all_below_half`、`unique_crossing`、
`non_unique_crossing` 或 `flat_half_plateau`。非唯一或不存在的前沿不会被删除，也不会伪造
位置。`[V]`

时间审计固定为 4 个半柱单元，只隔离轨道时间误差；分别计算 128、256、512 和 1024 个
相位点，并把 1024 点作为当前参考。比较量覆盖表层与深层温度、表面能流，以及表层 H II、
He III。它不是联合深度--时间生产解。`[A/V]`

预先采用 $10^{-3}$ 作为温度/能流相对误差和人口绝对误差的生产目标。`[A-classification]`

## 5. 深度收敛结果

| 网格 | $N$ | 表面能流相对误差 | 逐点 $T/\kappa_{\rm R}$ 相对误差 | 逐点人口绝对误差 | 柱平均 $T/\kappa_{\rm R}$ 相对误差 | 柱平均人口绝对误差 |
|---|---:|---:|---:|---:|---:|---:|
| fixed | 8 | $2.113\times10^{-3}$ | $4.663\times10^{-2}$ | $0.3151$ | $4.016\times10^{-3}$ | $7.163\times10^{-3}$ |
| adaptive | 8 | $1.138\times10^{-3}$ | $2.703\times10^{-2}$ | $0.1913$ | $1.060\times10^{-2}$ | $2.138\times10^{-2}$ |
| fixed | 12 | $6.275\times10^{-4}$ | $3.657\times10^{-2}$ | $0.2062$ | $1.016\times10^{-3}$ | $2.832\times10^{-3}$ |
| adaptive | 12 | $4.672\times10^{-4}$ | $1.511\times10^{-2}$ | $0.1220$ | $4.111\times10^{-3}$ | $8.545\times10^{-3}$ |
| fixed | 16 | $4.620\times10^{-4}$ | $2.523\times10^{-2}$ | $0.1608$ | $1.747\times10^{-4}$ | $1.394\times10^{-3}$ |
| adaptive | 16 | $2.025\times10^{-4}$ | $5.989\times10^{-3}$ | $0.05576$ | $1.731\times10^{-3}$ | $3.639\times10^{-3}$ |

`[V]` 自适应网格在三个共同分辨率上都同时改善了两项逐点误差；16 单元人口误差降为固定
网格的 $0.3467$。但是它在三个共同分辨率上都恶化了两项柱平均误差。原因是当前监视函数
把更多单元放在表面梯度和 He 前沿，牺牲了深部积分量的求积精度。不能把“逐点改善”写成
“所有指标改善”。

自适应 16 对 24 单元的逐点人口误差仍为 $0.05576$，温度/opacity/能流联合相对误差仍为
$5.989\times10^{-3}$；两者都没有通过生产门。29 个具有唯一 He III 半电离前沿的相位中，
16 与 24 单元的状态完全一致，最大前沿质量分数误差为 $2.121\times10^{-3}$。`[V/O]`

## 6. 时间收敛结果

| 相位点 | 温度或能流最大相对误差 | 人口最大绝对误差 |
|---:|---:|---:|
| 128 | $9.730\times10^{-3}$ | $1.622\times10^{-2}$ |
| 256 | $2.716\times10^{-3}$ | $4.743\times10^{-3}$ |
| 512 | $7.313\times10^{-4}$ | $1.281\times10^{-3}$ |
| 1024 | 当前参考 | 当前参考 |

512 点的温度/能流已经低于 $10^{-3}$，但人口误差高出阈值约 $28%$，所以联合时间门仍失败。
误差序列连续下降，没有用单个坏 bin 解释失败。1024 点还需与 2048 点或更高阶自适应时间
积分比较，才能被称为通过，而不能因为它是当前最高分辨率就自动接受。`[V/O]`

全部解的周期残差为 $6.65\times10^{-9}$--$9.79\times10^{-8}$，周期能量账本相对残差为
$5.81\times10^{-14}$--$3.02\times10^{-11}$。守恒求解继续成立；当前失败来自离散收敛，
不是能量账本破坏。`[V]`

## 7. 自适应深度图逐面解释

![Phase 7B4j adaptive depth audit](../outputs/phase7b4j_adaptive_depth.png)

- `(a)` 三个梯度包络都在表面最强，He III 在中浅层仍提供额外结构；黑线中的常数基线使
  中面附近监视密度保持为正。`[A/V]`
- `(b)` 共享边界明显聚集在小 $x$ 处，同时在完整 $[0,1]$ 保留单元；每条横线对应一个
  分辨率，边界不随轨道相位移动。`[V]`
- `(c)` 自适应逐点误差低于固定网格，但自适应柱平均误差更高。图中两类曲线不能合并成
  单一“自适应更好”的结论。`[V]`
- `(d)` 人口量呈相同权衡；虽然自适应 16 单元显著降低逐点误差，它仍远高于 $10^{-3}$。
  `[V/O]`

## 8. 高时间分辨率图逐面解释

![Phase 7B4j orbital-time audit](../outputs/phase7b4j_time_convergence.png)

- `(a)` 动态出射/瞬时 ZO 能流在近心点两侧包含窄结构；128 点解可以看见总体变化，却偏移
  或抹平局部极值。`[V]`
- `(b)` 柱平均 He III 曲线目视几乎重合，但最大范数仍能测出局部人口误差；不能以画线重合
  代替数值收敛。`[V]`
- `(c)` 温度/能流误差随相位点加密近似单调下降，512 对 1024 已达到 $7.313\times10^{-4}$。
- `(d)` 人口误差也单调下降，但 512 对 1024 的 $1.281\times10^{-3}$ 仍略高于目标。`[V/O]`

## 9. 阶段结论

1. `[V]` 显式共享拉格朗日质量网格接口和等监视量构造通过，未修改 ZO 的 $H$、$\Sigma$、
   $Q$ 或耗散总量。
2. `[V]` 当前等权梯度监视函数确实改善局部前沿解析，但牺牲柱积分量；它是有价值的诊断，
   还不是生产网格算法。
3. `[V/O]` 16 对 24 单元的逐点人口误差为 $5.576\times10^{-2}$，深度生产门失败。
4. `[V/O]` 512 对 1024 相位的人口误差为 $1.281\times10^{-3}$，时间生产门也未完全通过。
5. `[V/O]` 后续 [[eccentric_tde_observer/docs/phase7b4k_error_estimated_dynamic_convergence|Phase 7B4k]]
   已完成双网格误差估计和 2048 相位审计：1024 对 2048 相位通过，但嵌套深度网格仍不能
   同时收敛逐点前沿与柱积分。下一步改为保守单元内微物理重构，而不是继续调整监视权重。
6. `[O]` Phase 4 atmosphere 替换、UVOT、物理 X-ray 谱和真实线形成继续不获准。

本阶段没有使用 `nan_to_num`、任意 `clip`、任意 floor、删除失败相位或事后物理
重归一化。显式边界、监视量归一化和动态柱针对性测试为 `21 passed`；合入后的全项目现场
回归为 `306 passed in 31.62s`。`[V]`

## 10. 产物

- `src/eccentric_tde_observer/hydrostatic_atmosphere.py`；
- `src/eccentric_tde_observer/periodic_dynamic_atmosphere.py`；
- `tests/test_hydrostatic_atmosphere.py`；
- `tests/test_periodic_dynamic_atmosphere.py`；
- `scripts/phase7b4j_adaptive_dynamic_convergence.py`；
- `outputs/phase7b4j_adaptive_convergence_report.json`；
- `outputs/phase7b4j_adaptive_mass_edges.csv`；
- `outputs/phase7b4j_adaptive_monitor.csv`；
- `outputs/phase7b4j_depth_convergence.csv`；
- `outputs/phase7b4j_time_convergence.csv`；
- `outputs/phase7b4j_adaptive_depth.png`；
- `outputs/phase7b4j_time_convergence.png`。
