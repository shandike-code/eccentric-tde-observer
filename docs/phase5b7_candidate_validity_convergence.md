# Phase 5B7：候选有效域收敛门

上游：[[phase5b6_equation_self_consistent_candidate_source|Phase 5B6 方程自洽候选源]]  
对照：[[phase1h_validity_domain|Phase 1H 常偏心有效域]]

> `[V]` 两条方程自洽候选在径向、偏近心点的 $E$ 网格和显式表面三角网格加密后，
> 都稳定通过 Phase 1H 的 $1\%$ 工作阈值。`[A-domain]` 该阈值仍是局域薄柱工作判据，
> 不是文献定理。`[O]` 通过本门不会把候选变成 published benchmark。

## 1. 收敛问题与判据

本阶段继续使用 corrected ZO 面积

$$
{\rm d}A_{\rm corr}
=
a\,j(a,E)\left(1-e(a)\cos E\right){\rm d}a\,{\rm d}E.
$$

对两种垂向闭合分别计算

$$
f_{0.3}
=
\frac{
\int_{z_{\rm ph}/r\geq0.3}{\rm d}A_{\rm corr}
}{
\int {\rm d}A_{\rm corr}
}.
$$

沿用 Phase 1H 的显式工作门：Gaussian 和 $n=3$ polytrope 两种闭合都必须满足

$$
f_{0.3}\leq0.01.
$$

为避免只看最细网格，最终还要求保守上界

$$
f_{0.3}^{\rm fine}
+
\max\left(
|\Delta f_{0.3}^{\rm radial}|,
|\Delta f_{0.3}^{E}|
\right)
\leq0.01,
$$

其中两个差值都来自各自最后两级分辨率。这个保守加法是
`[A-convergence]`，不是统计置信区间。`[V/A-domain]`

## 2. 三类分辨率控制

### 2.1 径向节点

从冻结的 $256$ 点 $e(a),q(a)$ 剖面中只抽取原生节点，不插值、不重新拟合：
$N_{a}=33,65,129,256$。每一级保留内外边界和原始 $e,q,f$ 数值。因此这是 quadrature/
mesh 收敛源，不是另造四条候选剖面。`[V]`

### 2.2 偏心近点角和近心点

使用 $N_{\rm E}=64,128,256,512$ 的周期均匀网格。对应间距从
$9.82\times10^{-2}\,{\rm rad}$ 降到 $1.23\times10^{-2}\,{\rm rad}$；
在 $|E|\leq0.2$ 的近心点窗口中，采样节点由 $5$ 增加到 $33$。每一级都重新求解
局域 ZO Eq. (35)，而不是把粗网格 $h(E)$ 插值到细网格。`[V]`

### 2.3 显式表面三角网格

`audit_local_vertical_domain` 在每个周期 $(a,E)$ 四边形上使用两个三角形。
$E$ 加密和径向加密因此同时把显式光球表面从粗网格推进到最细
$256\times512$ 顶点、$261120$ 个三角形。这里没有另设 ray-tracing 式自适应三角深度；
收敛证据来自真实顶点与三角面数的增加，报告中明确保存
`separate_adaptive_triangle_subdivision=false`。`[V]`

## 3. 最终判定

| 候选 | 闭合 | 最细 $f_{0.3}$ | 最后两级最大绝对变化 | 保守 $f_{0.3}+|\Delta f|$ | $1\%$ 门 |
|---|---|---:|---:|---:|---:|
| $e_{\rm in}=0.60$ | Gaussian | $0$ | $0$ | $0$ | 通过 |
| $e_{\rm in}=0.60$ | $n=3$ polytrope | $0$ | $0$ | $0$ | 通过 |
| $e_{\rm in}=0.65$ | Gaussian | $8.1109\times10^{-3}$ | $8.5606\times10^{-5}$ | $8.1965\times10^{-3}$ | 通过 |
| $e_{\rm in}=0.65$ | $n=3$ polytrope | $0$ | $0$ | $0$ | 通过 |

$e_{\rm in}=0.65$ 的 Gaussian 是唯一接近边界的组合。它的径向最后两级变化为
$8.56\times10^{-5}$，$E$/表面最后两级变化为 $3.27\times10^{-5}$；即使取较大者
向不利方向相加，仍低于 $0.01$。所有最细网格的
$z_{\rm ph}/r\geq1$ corrected 面积分数都为 $0$。因此 $e_{\rm in}=0.60$ 和 $0.65$
候选均稳定通过当前工作门，后者应继续标为边界敏感性案例。`[V]`

## 4. 其他量的实际误差

末两级中最大的变化为：

- surface/projected area ratio：相对变化不超过 $9.29\times10^{-7}$；
- projected mesh/Cartesian quadrature area ratio：相对变化不超过
  $7.53\times10^{-5}$；
- 最小总垂向光深：两条候选均无可分辨变化，分别保持 $42.21$ 和 $40.87$；
- $j_{\min}$ 与 $j_{\max}$：无可分辨变化，且所有层级严格为正；
- $h_{\min}$：无可分辨变化；$e_{\rm in}=0.65$ 的 $h_{\max}$ 径向相对变化为
  $4.45\times10^{-7}$；
- 最大光球表面斜率的最慢径向相对变化为 $3.25\times10^{-3}$，发生在
  $e_{\rm in}=0.60$ Gaussian；该量不是 $1\%$ 面积分数门本身，实际数值和误差均保留，
  没有假装达到 $10^{-3}$。

所有计算均未使用 `nan_to_num`、无物理理由的 `clip`、floor、删点或事后重归一化。
Windows 3.11.9 的真实收敛运行墙钟约 $303\,{\rm s}$。`[V/V-resource]`

## 5. 图像与逐图解释

![Phase 5B7 candidate validity convergence](../outputs/phase5b7_candidate_validity_convergence.png)

**(a) $z_{\rm ph}/r\geq0.3$ corrected area fraction.** 黑点线是 $1\%$ 工作阈值。
只有 $e_{\rm in}=0.65$ Gaussian 给出非零值；径向实线和 $E$/表面虚线都收敛到约
$0.811\%$，没有跨越阈值。其余三种组合保持为 $0$。`[V]`

**(b) Triangular surface geometry.** 四组 surface/projected area ratio 随加密趋于平台。
两种闭合的差异是真实光球高度差，而同一闭合中实线和虚线重合显示径向与方位三角网格
给出一致极限。`[V]`

**(c) Vertical optical-depth floor.** 最小总光深由源柱密度决定，两种闭合共享同一条值；
图中方块和圆点重叠。两个候选都保持总光深远大于 $1$。`[V]`

**(d) Photosphere slope.** 粗径向网格对最大局域斜率最敏感，尤其是
$e_{\rm in}=0.60$ Gaussian；加密后实线趋向 $E$/表面虚线。最细最大斜率约
$0.492$ 和 $0.542$，没有达到单位斜率。`[V]`

## 6. 证据边界与下一步

- `[V]` 两条候选的局域有效域收敛门关闭；
- `[A-domain]` $0.3$、$1\%$ 和“最细值加最后两级差”是透明工作判据；
- `[A-candidate]` $e_{\rm in}=0.65$ 可作为边界敏感性候选，不能替换所有旧结果；
- `[O]` published ZO Fig. 6/7 benchmark 仍未关闭；
- `[O]` 本阶段未验证候选连续谱、倾斜观察者、自遮挡和线核的收敛。

因此下一步可以在这两条有效候选源上重算 corrected 连续谱；旧常偏心控制必须同时保留，
不能把候选结果反标为论文 benchmark。

## 7. 复现

    .venv/bin/python scripts/phase5b7_candidate_validity_convergence.py
    .venv/bin/python -m pytest -q \
      tests/test_phase5b7_candidate_validity_convergence.py \
      tests/test_zo_candidate_source.py

机器可读报告位于 `outputs/phase5b7_candidate_validity_convergence_report.json`，全部网格点
位于 `outputs/phase5b7_candidate_validity_convergence.csv`。
