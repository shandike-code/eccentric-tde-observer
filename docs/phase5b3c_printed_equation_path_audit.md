# Phase 5B3c：ZO 2020 印刷方程路径与边界切线审计

## 1. 结论先行

本阶段找到并数值检验了 ZO 2020 源文件中的两项字面不一致：[L/V]

1. 主文 Eq. (38) 写

$$
-
\left(
2ae_{a}+a^{2}e_{\rm aa}
\right)
F_{\rm ff},
$$

而附录自由边界推导在同一位置写

$$
-
\left(
2ae_{a}-a^{2}e_{\rm aa}
\right)
F_{\rm ff}.
$$

2. Fig. 6 caption 开头正确写 $a_{\rm out}=1.3a_{\rm in}$ 和
   $a_{\rm out}=3a_{\rm in}$，后面的频率说明却把它们倒写成
   $a_{\rm in}=1.3a_{\rm out}$ 和 $a_{\rm in}=3a_{\rm out}$。

字面不一致是真实存在的，但不能解释 published 分支：

- [V] 将附录减号当作完整方程求解后，得到
  $\widetilde{\omega}=-1.6386321,-1.2467438$；
- [V] 它与 published 的 $-0.7170616,+0.13$ 最大仍差 $1.3767$，宽盘模形最大差为
  $0.3274e_{\rm in}$；
- [V/A] Fig. 6 矢量路径的 2--4 点端点切线与声明的三维内自由边界不相容，但最外一段
  切线接近三维外自由边界；
- [O] 因此当前证据指向“已发表曲线与字面方程/边界并非完整一致”，却仍不能恢复未公开
  数值代码的实际路径；
- [O] 正式 ZO 源没有修改，$\Phi\mapsto t$ 继续关闭。

## 2. 为什么主文加号是正式基线

定义

$$
f=e+ae_{a}.
$$

则恒等地有

$$
a\frac{{\rm d}f}{{\rm d}a}
=
2ae_{a}+a^{2}e_{\rm aa}.
$$

因此主文 Eq. (38) 的加号组合正是 $af_{a}$，也与
[[markdown_papers/1812.05942v1|Ogilvie & Lynch 2019]] 的无扭曲模方程一致。[L]
项目正式求解器继续使用这条路径。

附录减号不能由同一变量变换得到。为检验它是否只是印刷公式与实际 published 代码之间的
线索，本阶段把它字面改写成独立一阶系统，但明确标为 [A-diagnostic]，没有写回正式模块。

## 3. 两条印刷路径怎样比较

两条路径使用完全相同的：

- 三维周期呼吸 Hamiltonian；
- $(e,q)$ 完整矩形表；
- 双端 $F_{f}=0$ 自由边界；
- $e(1)=0.2\sqrt{0.92}$；
- $\delta_{\rm GR}=0.0305649613$；
- 正无节点初形和配点 BVP。

只有 $a^{2}e_{\rm aa}$ 前的印刷符号不同。[A/V]

| 方程路径 | $a_{\rm out}/a_{\rm in}$ | 计算频率 | published | 模形最大差除以 $e_{\rm in}$ |
|---|---:|---:|---:|---:|
| main Eq. (38) | 1.3 | $+1.7336724$ | $-0.7170616$ | $0.09514$ |
| main Eq. (38) | 3.0 | $+1.4764670$ | $+0.1300000$ | $0.31979$ |
| appendix literal | 1.3 | $-1.6386321$ | $-0.7170616$ | $0.09474$ |
| appendix literal | 3.0 | $-1.2467438$ | $+0.1300000$ | $0.32744$ |

两档 $31\times61$ 与 $41\times81$ Hamiltonian 表的最大频率相对变化为
$2.09\times10^{-6}$，最大绝对边界残差为 $2.03\times10^{-10}$。[V] 因此附录路径
失败不是未收敛造成。

## 4. published 矢量路径的边界切线

Fig. 6 独立图由 Matplotlib 3.0.3 生成，曲线在 PDF 中保存为折线路径。Phase 5B3 已把
$\lambda_{e}=0.2$ 的黑色路径映射回 $(a/a_{\rm in},e)$。本阶段不再读取像素，而在内、
外端分别用相邻 2、3、4 个矢量点做局部线性拟合。[L/V/A]

由拟合斜率得到

$$
q_{\rm path}
=
\frac{
a\,{\rm d}e/{\rm d}a
}{
1-e\left(e+a\,{\rm d}e/{\rm d}a\right)
}.
$$

主要结果为：

| 半径比 | 边界 | published 路径的 $q$ 范围 | 三维 $F_{f}=0$ 所需 $q$ | 二维 $F_{f}=0$ 所需 $q$ |
|---:|---|---:|---:|---:|
| 1.3 | inner | $-0.1364$ 至 $-0.1245$ | $-0.2584$ | $-0.1475$ |
| 1.3 | outer | $-0.2036$ 至 $-0.1861$ | $-0.2060$ | $-0.1148$ |
| 3.0 | inner | $-0.1124$ 至 $-0.1003$ | $-0.2584$ | $-0.1475$ |
| 3.0 | outer | $-0.1162$ 至 $-0.1069$ | $-0.1054$ | $-0.0570$ |

[V] 两个最外一段的切线与三维自由根分别只差 $0.00239$ 和 $0.00154$；两个内端切线
则与三维自由根至少差 $0.122$ 和 $0.146$。这个内外差异比“所有边界都用了二维
Hamiltonian”更复杂。

### 4.1 这项切线审计的限制

矢量折线经过 Matplotlib 的路径简化，端点首段覆盖有限而非无穷小的径向区间。因此
$q_{\rm path}$ 是 [A-vector-tangent] 的有限区间估计，不是原始未简化数组中的精确
导数。[A/O]

不过 2--4 点拟合的结论同向，而且三维内自由根远在全部估计之外，所以它构成值得保留的
实现线索。它不能单独宣布论文违反边界条件。

## 5. 图像与逐图解释

![Printed equation and boundary audit](../outputs/phase5b3c_printed_equation_path_audit.png)

**怎么看。** 左上比较 published、主文 Eq. (38)、附录减号字面路径和完整二维非线性
频率；右上和左下比较两个 Fig. 6 模形；右下的蓝色误差棒是 2--4 点矢量切线范围，三角和
方块分别是三维、二维自由边界根。图内文字全部为英文。

**验证了什么。** [V] 附录减号确实把频率从顺行改成逆行，但两个半径比都没有回到
published 值，模形也没有改善。右下显示 published 外端切线接近三维自由根，而两个内端
明显偏离；这说明不能用单一的“二维取代三维”解释整条曲线。

**不能证明什么。** [A/O] 该图不能确定原作者代码实际采用了附录符号、有限 taper
边界、不同偏导表或其他未公开路径。尤其不能根据两条 published 曲线拟合一个新边界条件，
再把它写回正式 ZO 模型。

## 6. 阶段判定

- [L] 主文与附录确有二阶径向项符号不一致；
- [L] Fig. 6 caption 确有半径比倒写；
- [V] 两条字面方程路径都数值收敛；
- [V] 附录减号路径不解释 published 频率或模形；
- [V/A] published 矢量内端切线不满足声明的三维内自由根，外端则近似满足；
- [O] 未公开实现差异仍未唯一定位；
- [O] 正式时间映射继续不授权。

不改变基准还能进行的内部审计已经接近穷尽。最有判别力的下一证据是原作者数值代码或
未简化的 $e(a)$ 数组；若没有外部证据，继续枚举任意符号和边界变体会变成事后拟合，不应
继续。[O]

## 7. 复现

    uv run python scripts/phase5b3c_printed_equation_path_audit.py
    uv run pytest -q tests/test_phase5b3c_printed_equation_path_audit.py
    uv run pytest -q

本轮最终完整回归为 `601 passed in 64.16s`。`[V]`

阶段关系见
[[eccentric_tde_observer/docs/phase5b3_nonlinear_apsidal_benchmark_gate|Phase 5B3]]、
[[eccentric_tde_observer/docs/phase5b3a_published_branch_inverse_audit|Phase 5B3a]]、
[[eccentric_tde_observer/docs/phase5b3b_full_2d_nonlinear_diagnostic|Phase 5B3b]]、
[[eccentric_tde_observer/docs/phase5b4_strict_domain_candidate_timescale_gate|Phase 5B4]]
和 [[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]。
