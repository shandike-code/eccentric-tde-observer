# Phase 5B3：全局非线性拱点模与 ZO Fig. 6/7 基准门

## 1. 结论先行

Phase 5B3 已经独立求解 ZO Eqs. (34)、(35)、(38) 与双端自由边界 Eq. (43)。三维
Hamiltonian 表、配点 BVP、射击法和 Phase 5B1 线性 Galerkin 极限彼此闭合；但是这条
数学上连续的三维无节点支不能复现 ZO 2020 Fig. 6/7 的已发表数值。[L/V/O]

因此本阶段的判定分成两层：

- [V] **方程内部数值门通过**：表分辨率、边界残差、线性极限和两个全局求解器通过；
- [O] **文献基准门失败**：不能把当前独立本征值转换成正式 $P_{\rm prec}$，也不能开始
  严格域观察者时间图谱。

这不是 ZO 2022 Erratum 的面积修正。Erratum 明确说底层动力学不变；这里审计的是 2020
动力学图的数值可复现性。[L/O]

## 2. 新增实现

- src/eccentric_tde_observer/hamiltonian_table.py：非外推 $G(e,q)$ 双三次表与严格链式求导；
- src/eccentric_tde_observer/nonlinear_apsidal_mode.py：射击和配点 BVP 两个全局求解器；
- scripts/phase5b3_nonlinear_apsidal_benchmark_gate.py：低振幅文献基准、二维控制和出图；
- outputs/phase5b3_nonlinear_apsidal_report.json：阶段门与误差账本；
- outputs/phase5b3_nonlinear_apsidal_convergence.csv：两档表分辨率结果；
- outputs/phase5b3_zo2020_fig6_comparison.csv：published、三维非线性、三维线性和二维控制。

## 3. 方程怎样变成一阶 BVP

定义

$$
x=\frac{a}{a_{\rm in}},\qquad
f=e+a\frac{\mathrm{d}e}{\mathrm{d}a},\qquad
q=\frac{f-e}{1-ef}.
$$

由

$$
x\frac{\mathrm{d}f}{\mathrm{d}x}
=
2x\frac{\mathrm{d}e}{\mathrm{d}x}
+x^{2}\frac{\mathrm{d}^{2}e}{\mathrm{d}x^{2}},
$$

ZO Eq. (38) 严格化成

$$
\frac{\mathrm{d}e}{\mathrm{d}x}
=
\frac{f-e}{x},
$$

$$
\frac{\mathrm{d}f}{\mathrm{d}x}
=
\frac{
F_{e}
-(f-e)F_{\rm ef}
+3F_{f}
-\dfrac{\delta_{\rm GR}e}{x(1-e^{2})^{3/2}}
+\dfrac{\widetilde{\omega}x^{3/2}e}{\sqrt{1-e^{2}}}
}{
xF_{\rm ff}
}.
$$

这里 $F_{e}$ 表示固定 $f$ 的偏导，$F_{f}$ 表示固定 $e$ 的偏导。代码从 $G(e,q)$ 表用完整
链式法则恢复 $F_{e},F_{f},F_{\rm ef},F_{\rm ff}$；它不把 $q$ 导数误当成 $f$ 导数。[L/V]

双端边界为

$$
e(1)=e_{\rm in},\qquad
F_{f}(1)=F_{f}(x_{\rm out})=0.
$$

因 $q_{f}>0$，自由边界也等价于 $G_{q}=0$。代码只接受局部凸根 $G_{\rm qq}>0$，并拒绝表外
查询、$F_{\rm ff}\le0$、$e\le0$ 的非无节点支和非正 Jacobian；没有外推、裁剪或 floor。[V]

## 4. 三重独立闭合

### 4.1 解析链式求导

合成二次 $G(e,q)$ 的全部一、二阶导数与独立有限差分相符；表外查询直接拒绝。[V]

### 4.2 射击法对 Phase 5B1

把表替换为三维二次 Hamiltonian

$$
F=3.5-e^{2}+\frac{1}{4}ef+\frac{5}{16}f^{2},
$$

并取 $e_{\rm in}=10^{-4}$，射击法回收

$$
\widetilde{\omega}=1.8088649,\qquad
\frac{e(1.3)}{e_{\rm in}}=0.6872294.
$$

这与 Phase 5B1 的 P1 Galerkin 及独立强形式积分一致。[V]

### 4.3 配点 BVP 对射击法

完全独立的配点 BVP 解回收相同低振幅结果。它也能在 $a_{\rm out}/a_{\rm in}=3$
时越过无效射击端点，收敛到正的无节点支。[V]

## 5. 真实三维低振幅结果

取论文 Fig. 6 的

$$
e_{\rm in}=0.2\sqrt{0.92}=0.1918332609,\qquad
\delta_{\rm GR}=0.0305649613.
$$

正式结果为：

| $a_{\rm out}/a_{\rm in}$ | ZO Fig. 6 | 三维非线性 Eq. (34)/(38) | 三维线性极限 | 二维线性控制 |
|---:|---:|---:|---:|---:|
| 1.3 | $-0.71$ | $1.733672303$ | $1.808864890$ | $-0.502446962$ |
| 3.0 | $0.13$ | $1.476466895$ | $1.534257749$ | $-0.372091809$ |

三维非线性值向 $e\to0$ 的三维线性值连续，而 published 值没有落在这条连续支上。二维
控制在本征函数形状上更接近 published 曲线，但频率仍不能同时复现，所以不能把
“论文实际用了二维 Hamiltonian”写成结论。[V/A/O]

## 6. 收敛结果

表分辨率从 $17\times33$、128 异常角点提高到 $25\times49$、192 点后：

- 最大本征频率相对变化为 $4.094735\times10^{-8}$；
- 最大外边界偏心率相对变化为 $4.841664\times10^{-7}$；
- 最大绝对外边界残差为 $2.144153\times10^{-10}$。
- 六个独立内、中、外留出状态上，样条偏导向量相对直接五点呼吸偏导的最大差为
  $6.597846\times10^{-5}<10^{-3}$。

这排除了“粗二维样条二阶导数造成符号翻转”的解释。[V]

## 7. 图像与逐图解释

### 7.1 Fig. 6 本征函数审计

![ZO Fig. 6 profile audit](../outputs/phase5b3_fig6_profile_audit.png)

**怎么看。** 黑线是从 arXiv 源包中的原始矢量 Fig. 6 路径直接读出的
$\lambda_{e}=0.2$ 曲线；蓝线是三维 Eqs. (34)/(38) 解；橙色虚线是二维线性控制。

**验证了什么。** [V] 在窄盘中，published 曲线接近二维控制；在扩展盘中仍位于二维
和三维之间。蓝线不是随机跑偏：它同时满足自由边界、三维线性极限和表收敛。

**不能证明什么。** [O] 只凭曲线位置不能反推出原作者代码使用了哪个 Hamiltonian 或
哪种差分步长；arXiv 源包没有附数值代码。

### 7.2 低振幅频率基准

![Low-amplitude apsidal benchmark](../outputs/phase5b3_frequency_benchmark.png)

**怎么看。** 两组柱分别比较 published、三维非线性、三维线性和二维线性频率。正负号
表示相反的拱点进动方向。

**验证了什么。** [V] 三维非线性和三维线性同号且只相差约 $3.8\%$--$4.2\%$；published
值不只是小幅归一化差，而在 $a_{\rm out}/a_{\rm in}=1.3$ 时连符号也不同。

**不能证明什么。** [O] 这张图不解决 Eq. (48) 的十倍物理时标印刷差，也不能据此给出
天单位周期。

### 7.3 原始 Fig. 7 分支行为

![ZO 2020 original Fig. 7 reference](../outputs/zo2020_original_fig7_reference.png)

**怎么看。** 左图横轴为 $1-e_{\rm in}$；向右即 $e_{\rm in}\to0$。中图向左是
$a_{\rm out}/a_{\rm in}-1\to0$。

**验证了什么。** [L/V] published 曲线在圆盘端和窄环端都出现发散。可是 Eq. (44)
的无节点自由边界支在两个极限均保持有限；发散的是更高径向节点支。原审稿意见也质疑了
这两个发散，公开回复只解释了窄环，没有关闭圆盘极限。

**不能证明什么。** [O] 图本身不能区分错误的分支跟踪、有限差分偏导误差或未公开代码
中的其他实现差异。

## 8. 阶段判定

- [V] 三维 Eq. (34)/(38) 方程内部门通过；
- [V] 圆盘极限连续，不能为匹配 Fig. 7 而破坏；
- [O] ZO Fig. 6/7 文献基准门失败；
- [O] $\Phi$ 仍只能是无量纲相位，不能映射成 day；
- [O] 下一步只获准做 Phase 5B3a 的 published 分支反演审计或取得原作者数值代码；
- [O] 不授权用 published 柱值硬编码本征频率，不授权开始新的时间域 atlas。

## 9. 复现

    uv run python scripts/phase5b3_nonlinear_apsidal_benchmark_gate.py
    uv run pytest -q tests/test_hamiltonian_table.py tests/test_nonlinear_apsidal_mode.py

阶段关系见[[eccentric_tde_observer/docs/phase5b1_linear_apsidal_mode_gate|Phase 5B1]]、
[[eccentric_tde_observer/docs/phase5b2_nonlinear_hamiltonian_gate|Phase 5B2]]和
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]。
