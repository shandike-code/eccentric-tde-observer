# Phase 5B3b：完整二维非线性 Hamiltonian 分支诊断

## 1. 结论先行

本阶段从 [[markdown_papers/1812.05942v1|Ogilvie & Lynch 2019]] Eqs. (33)、(B4)
和 (40) 恢复了完整二维、绝热、无扭曲 Hamiltonian，并把它接入与 Phase 5B3 相同的
自由边界 BVP。[L/V]

结果清楚排除了一个候选解释：

- [V] 二维公式的圆盘极限、二阶展开、轨道求积、表偏导和全局 BVP 内部门全部通过；
- [V] 完整二维非线性频率只比二维线性控制改变最多
  $2.13\times10^{-3}$；
- [V] 在 $a_{\rm out}/a_{\rm in}=1.3,2,3,4$ 上，完整二维频率仍全为负，
  没有回收到 published 分支的跨零行为；
- [V] published 频率的最小绝对差仍为 $0.2167$，最大差为 $0.5022$；
- [O] 因而“Phase 5B3 只少算了二维非线性修正”不是 published 差异的原因；
- [O] 这仍不能唯一定位原作者未公开实现中的具体差异，正式相位到时间映射继续关闭。

该二维分支是 [A-diagnostic] 对照，不替换 ZO 三维动力学源，也没有修改任何连续谱或线核
的源场。

## 2. 恢复的原始公式

对无扭曲盘，定义

$$
f=e+a\frac{{\rm d}e}{{\rm d}a},
$$

$$
j(e,f,E)
=
\frac{
1-ef-(f-e)\cos E
}{
\sqrt{1-e^{2}}
}.
$$

Ogilvie--Lynch 的二维几何 Hamiltonian 为

$$
F^{(\mathrm{2D})}(e,f)
=
\frac{1}{\gamma-1}
\frac{1}{2\pi}
\int_{0}^{2\pi}
(1-e\cos E)
j^{-(\gamma-1)}
\,{\rm d}E.
$$

这里的 $1-e\cos E$ 必须保留，因为尖括号是对平均异常角的轨道平均，而不是对偏心异常角
的裸平均。[L] 本项目采用与 ZO 源一致的 $\gamma=4/3$。

非交叉参数为

$$
q
=
\frac{f-e}{1-ef},
\qquad
|q|<1.
$$

程序对 $|e|\ge0.99$、$1-ef\le0$、$|q|\ge1$ 或任一非正 $j$ 直接拒绝；没有
clip、floor、nan_to_num 或事后归一化。[V]

## 3. 二阶极限

文献 Eq. (40) 在无扭曲变量中写成

$$
F^{(\mathrm{2D})}_{\rm lin}
=
\frac{1}{\gamma-1}
+
\frac{1}{2}ef
+
\frac{\gamma}{4}(f-e)^{2}.
$$

因此在 $(e,f)=(0,0)$ 应有

$$
F_{\rm ee}=\frac{\gamma}{2}=\frac{2}{3},
\qquad
F_{\rm ef}=\frac{1-\gamma}{2}=-\frac{1}{6},
\qquad
F_{\rm ff}=\frac{\gamma}{2}=\frac{2}{3}.
$$

把中心差分步长从 $10^{-2}$ 降到 $3\times10^{-4}$ 后，完整公式 Hessian 相对误差从
$3.86\times10^{-5}$ 降到 $3.17\times10^{-8}$。[V] 这证明恢复的轨道平均和现有
Phase 5B3 二维线性控制属于同一公式的两个振幅层级。

## 4. 数值门

### 4.1 轨道异常角

在 $(e,f)=(0.191833,0.08),(0.30,-0.10),(0.65,0.25)$ 三个状态上，将周期求积从
64 点加密到 512 点。相邻分辨率最大相对变化为 $3.33\times10^{-16}$。[V]

### 4.2 Hamiltonian 表与全局 BVP

使用两档完整矩形表：

| $N_{e}\times N_{q}$ | 异常角点数 |
|---:|---:|
| $21\times41$ | 256 |
| $29\times65$ | 512 |

四个半径比的最大频率相对变化为 $1.12\times10^{-7}$，最大外缘偏心率相对变化为
$2.36\times10^{-7}$。六个不参与表构造的直接五点偏导留出状态，最大偏导向量误差为
$5.74\times10^{-5}$；最大绝对外边界残差为 $2.87\times10^{-12}$。[V]

## 5. 与二维线性和 published 分支的对照

固定

$$
e_{\rm in}
=
0.2\sqrt{0.92}
=
0.1918332609,
\qquad
\delta_{\rm GR}=0.0305649613.
$$

| $a_{\rm out}/a_{\rm in}$ | published | 二维线性 | 完整二维非线性 | 非线性 $-$ 线性 |
|---:|---:|---:|---:|---:|
| 1.3 | $-0.717062$ | $-0.502447$ | $-0.500322$ | $+0.002125$ |
| 2.0 | $+0.054826$ | $-0.415508$ | $-0.414832$ | $+0.000675$ |
| 3.0 | $+0.130000$ | $-0.372092$ | $-0.372205$ | $-0.000113$ |
| 4.0 | $+0.133728$ | $-0.351056$ | $-0.351573$ | $-0.000517$ |

[V] 非线性修正比 published 差异小约两个数量级，而且没有改变频率符号。对 Fig. 6
模形，半径比 1.3 的最大误差为 $0.0349e_{\rm in}$，半径比 3 的最大误差为
$0.1219e_{\rm in}$；频率和宽盘模形门均失败。

## 6. 图像与逐图解释

![Full 2D nonlinear branch diagnostic](../outputs/phase5b3b_full_2d_nonlinear_diagnostic.png)

**怎么看。** 左上把 published、二维线性、完整二维非线性和完整三维非线性频率放在
同一半径比轴上；右上和左下比较 Fig. 6 的两条模形；右下只画完整二维减二维线性的
频率差。图内文字全部为英文。

**验证了什么。** [V] 绿色完整二维曲线在频率图上几乎与橙色二维线性曲线重合；右下纵轴
只有约 $10^{-3}$ 的量级。二维非线性不能产生 published 的顺逆行转换。窄环模形虽然较
接近 published 点，频率仍差 $0.2167$；宽盘模形与频率同时不符。

**不能证明什么。** [O] 该图不能说明 published 数值一定使用了错误 Hamiltonian，也不能
在三维方程内部定位到符号、单位、偏导或分支索引中的某一项。二维控制只是排除实验，
不得被提升为新的正式源模型。

## 7. 阶段判定

- [L/V] OL 二维完整公式已恢复并回收其二阶极限；
- [V] 二维公式、插值偏导和全局 BVP 内部门通过；
- [V] 完整二维非线性修正不足以复现 ZO 2020 Figs. 6--7；
- [O] published benchmark 仍失败；
- [O] Phase 5B4 的候选周期仍只能称为方程自洽候选；
- [O] 现有常偏心 atlas 的 $\Phi\mapsto t$ 继续不授权。

下一项安全的内部诊断应转向 Eq. (38) 到已发表无量纲频率的符号和归一化账本，以及
published 矢量数据之间的一致性；在缺少原作者代码时，不允许通过拟合曲线改写方程。

## 8. 复现

    uv run python scripts/phase5b3b_full_2d_nonlinear_diagnostic.py
    uv run pytest -q tests/test_planar_hamiltonian.py
    uv run pytest -q tests/test_phase5b3b_full_2d_nonlinear_diagnostic.py
    uv run pytest -q

本轮最终完整回归为 `601 passed in 64.16s`。`[V]`

阶段关系见
[[eccentric_tde_observer/docs/phase5b3_nonlinear_apsidal_benchmark_gate|Phase 5B3]]、
[[eccentric_tde_observer/docs/phase5b3a_published_branch_inverse_audit|Phase 5B3a]]、
[[eccentric_tde_observer/docs/phase5b4_strict_domain_candidate_timescale_gate|Phase 5B4]]
和 [[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]。
