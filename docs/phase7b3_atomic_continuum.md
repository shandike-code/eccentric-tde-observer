# Phase 7B3：可追溯 H/He 连续谱原子率与静态耦合控制

> [!abstract] 阶段结论
> `[L/V]` 本阶段接入 Verner 等（1996）的 H I、He I、He II 基态光致电离截面和
> Verner & Ferland（1996）的总辐射复合率，并验证阈值分段积分、粒子数、电荷、构造型
> LTE 详细平衡及带真实频率依赖 opacity 的静态纯吸收转移。
> `[A]` 稀释 Planck 辐射场、等温控制板层和 ZO 柱的灰 Eddington 温度剖面仍是工作假设。
> `[O]` 本阶段没有激发能级、bound--bound、碰撞过程、金属、能量方程或轨道时间耦合，
> 因此没有产生可替代 modified-blackbody 的物理 NLTE 连续谱。

导航：[[eccentric_tde_observer/README|项目 README]] ·
[[eccentric_tde_observer/docs/phase7b2_transfer_controls|Phase 7B2 转移控制]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

---

## 1. 本阶段到底补上了什么

Phase 7B2 只证明了给定 $\chi_{\nu}$、$\epsilon_{\nu}$ 和 $B_{\nu}$ 时转移核能正确工作，
没有说明这些量从哪里来。Phase 7B3 补上的是第一层可追溯微观输入：

1. H I、He I、He II 基态 bound--free 截面；
2. H II $\rightarrow$ H I、He II $\rightarrow$ He I、He III $\rightarrow$ He II 总辐射
   复合系数；
3. 给定辐射场时，最小 H/He 光致电离--辐射复合稳态；
4. LTE 下 free--free、bound--free 和电子散射 opacity；
5. 把该 opacity 接入 Phase 7B2 静态频率--角度转移核的控制题；
6. 在真实 ZO 代表柱上重新计算频率分辨有效光深。

这仍不是完整原子。没有激发态、线跃迁、碰撞电离、三体复合、金属线空白和气体能量方程，
也没有把率放回轨道周期推进器。`[L/A/O]`

## 2. 光致电离截面的来源和公式

采用 [Verner 等 1996](https://arxiv.org/abs/astro-ph/9601009) 的基态总光致电离拟合，参数
逐项来自作者发布的 [photo.dat](https://www.pa.uky.edu/~verner/dima/photo/photo.dat)。拟合为

$$
\sigma(E)=\sigma_{0}F(y)\ {\rm Mb},
$$

$$
x=\frac{E}{E_{0}}-y_{0},
\qquad
y=\sqrt{x^{2}+y_{1}^{2}},
$$

$$
F(y)=
\left[(x-1)^{2}+y_{\rm w}^{2}\right]
y^{P/2-11/2}
\left(1+\sqrt{\frac{y}{y_{\rm a}}}\right)^{-P}.
$$

其中 $1\ {\rm Mb}=10^{-18}\ {\rm cm^{2}}$。阈值以下截面严格为零；H/He 表给出的上限是
$50\ {\rm keV}$，代码遇到更高能量会拒绝外推。`[L/V]`

| 离子 | $E_{\rm th}$ (eV) | $E_{0}$ (eV) | $\sigma_{0}$ (Mb) | $y_{\rm a}$ | $P$ | $y_{\rm w}$ | $y_{0}$ | $y_{1}$ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| H I | 13.60 | 0.4298 | $5.475\times10^{4}$ | 32.88 | 2.963 | 0 | 0 | 0 |
| He I | 24.59 | 13.61 | 949.2 | 1.469 | 3.188 | 2.039 | 0.4434 | 2.136 |
| He II | 54.42 | 1.720 | $1.369\times10^{4}$ | 32.88 | 2.963 | 0 | 0 | 0 |

阈值处代码得到

$$
\sigma_{\rm H\,\rm I}=6.3463\times10^{-18}\ {\rm cm^{2}},
$$

$$
\sigma_{\rm He\,\rm I}=7.4347\times10^{-18}\ {\rm cm^{2}},
\qquad
\sigma_{\rm He\,\rm II}=1.5873\times10^{-18}\ {\rm cm^{2}}.
$$

这些数值由拟合参数直接复算，不是硬编码验收答案。旧 `non_gray.py` 中 He I 的氢样
$\nu^{-3}$ 敏感性路径没有被改写；新正式 Phase 7B3 路径改用可追溯的 He I 拟合，并保留旧
路径供历史回归。`[V]`

## 3. 辐射复合率和 He I 分支

采用 [Verner & Ferland 1996](https://arxiv.org/abs/astro-ph/9509083) 的总辐射复合拟合：

$$
\alpha_{\rm r}(T)=a
\left[
\sqrt{\frac{T}{T_{0}}}
\left(1+\sqrt{\frac{T}{T_{0}}}\right)^{1-b}
\left(1+\sqrt{\frac{T}{T_{1}}}\right)^{1+b}
\right]^{-1}.
$$

参数来自作者发布的 [table1.dat](https://www.pa.uky.edu/~verner/dima/rec/table1.dat)。He I 有
两个分支：低温分支在 $3\ {\rm K}<T<10^{6}\ {\rm K}$ 内的均方根拟合误差为 $2.5\%$；宽
温度分支可到 $10^{10}\ {\rm K}$，但均方根误差为 $4.7\%$。本阶段气体控制温度低于
$10^{6}\ {\rm K}$，因此正式路径使用前者，超出范围直接报错。`[L/V]`

在 $T=10^{4}\ {\rm K}$ 时：

| 复合过程 | $\alpha_{\rm r}$ ($\mathrm{cm^{3}\,s^{-1}}$) |
|---|---:|
| H II $\rightarrow$ H I | $4.19232\times10^{-13}$ |
| He II $\rightarrow$ He I | $4.59543\times10^{-13}$ |
| He III $\rightarrow$ He II | $2.18799\times10^{-12}$ |

这里的“总复合”包括向多个束缚态的总贡献，但当前模块没有保留复合后落入哪个激发态，故
不能据此计算 H$\alpha$ 或 He II 单线光度。`[L/O]`

## 4. 光致电离率、阈值分段和稳态

给定角平均强度 $J_{\nu}$，每个靶粒子的光致电离率为

$$
\Gamma=
4\pi\int_{\nu_{0}}^{\infty}
\frac{\sigma_{\nu}J_{\nu}}{h\nu}\,\mathrm d\nu.
$$

离化边是不连续点。若把阈值以下的零截面与阈值处非零截面放在同一条梯形边上，会人为增加
一个三角形面积。代码现在显式从每个离子的阈值点开始积分；2049 个基础对数网格点相对
8193 点参考的最大率误差为 $2.02\times10^{-4}$。`[V]`

独立解析控制取

$$
\sigma_{\nu}=\sigma_{0}\left(\frac{\nu_{0}}{\nu}\right)^{3},
\qquad
J_{\nu}=J_{0}\left(\frac{\nu_{0}}{\nu}\right)^{p},
$$

则

$$
\Gamma=
\frac{4\pi\sigma_{0}J_{0}}{h(3+p)}.
$$

数值积分以 $2.1\times10^{-8}$ 的相对误差回收该结果。`[A-control/V]`

当前最小稳态只包含相邻电离态的光致电离和辐射复合，例如

$$
n_{\rm H\,\rm I}\Gamma_{\rm H\,\rm I}
=n_{\rm e}n_{\rm H\,\rm II}\alpha_{\rm H\,\rm I},
$$

并同时解电荷中性：

$$
n_{\rm e}=n_{\rm H\,\rm II}+n_{\rm He\,\rm II}+2n_{\rm He\,\rm III}.
$$

二分解保持 H、He 粒子数和电荷，不对负布居做裁剪。稀释 Planck 控制采用
$T_{\rm rad}=6\times10^{4}\ {\rm K}$、$T_{\rm gas}=2\times10^{4}\ {\rm K}$、
$n_{\rm H}=10^{10}\ {\rm cm^{-3}}$、$n_{\rm He}=10^{9}\ {\rm cm^{-3}}$，只用来展示率核随
稀释因子 $W$ 的连续响应，不是任何 ZO 面元的自洽辐射场。最大相对电荷残差为
$3.18\times10^{-16}$。`[A-control/V]`

## 5. 为什么 LTE 详细平衡要单独构造

Saha 关系写成

$$
\frac{n_{i+1}n_{\rm e}}{n_{i}}=S_{i}(T).
$$

若要求一个控制率对严格满足同一组 Saha 因子，则必须令

$$
\alpha_{i}^{\rm DB}=\frac{\Gamma_{i}}{S_{i}(T)}.
$$

使用这组构造型逆率，代码回收 H/He Saha 分数的最大绝对误差为
$1.11\times10^{-16}$，电子密度相对误差为 $4.44\times10^{-16}$。`[A-control/V]`

这不能被误读为“Verner--Ferland 总辐射复合率加任意 Planck 场必然恢复 LTE”。严格 LTE
还涉及受激复合、碰撞过程、配分函数和一致的微观逆过程。构造型
$\alpha_{i}^{\rm DB}$ 只验证方程方向、统计权重和电荷求根，没有替换文献物理率。`[L/A/O]`

## 6. LTE opacity 怎样接入转移核

在 LTE 控制中，真实吸收写成

$$
\kappa_{\nu}^{\rm abs}
=\kappa_{\nu}^{\rm ff}
+\kappa_{\nu}^{\rm H\,I}
+\kappa_{\nu}^{\rm He\,I}
+\kappa_{\nu}^{\rm He\,II},
$$

电子散射为

$$
\kappa_{\nu}^{\rm es}
=\frac{n_{\rm e}\sigma_{\rm T}}{\rho}.
$$

bound--free 和 free--free 都含 LTE 受激辐射修正
$1-\exp[-h\nu/(kT)]$。纯吸收等温控制取
$T=2\times10^{4}\ {\rm K}$、$\rho=10^{-10}\ {\rm g\,cm^{-3}}$、
$m=10^{-3}\ {\rm g\,cm^{-2}}$，并把 Verner 截面算出的 $\tau_{\nu}$ 直接送入 Phase 7B2：

$$
F_{\nu}^{\rm out}
=2\pi B_{\nu}
\left[\frac{1}{2}-E_{3}(\tau_{\nu})\right].
$$

64 阶角求积的最大归一化能流绝对误差为 $1.98\times10^{-4}$，逐频率能量平衡最大相对
残差为 $9.21\times10^{-11}$。最薄频段的相对能流误差可达 $4.56\times10^{-3}$，原因是
分母本身很小；因此报告同时保留绝对归一化误差和相对误差，不隐藏小量。`[A-control/V]`

该板层由人为指定的等温状态构成，目标是检查 opacity--transfer 接口和离化边，不是输出
盘谱。没有对出射能流做事后重归一化。`[A/O]`

## 7. ZO 代表柱 opacity 审计

代表柱 03 的实际坐标为径向索引 8、异常角索引 0：

$$
\Sigma=1171.171\ {\rm g\,cm^{-2}},
\qquad
H=1.35788\times10^{12}\ {\rm cm},
$$

$$
T_{\rm eff}=3.64961\times10^{4}\ {\rm K}.
$$

密度仍用 Phase 7A 的有限 $n=3$ 多项式闭合；温度仍暂用灰 Eddington 初值：

$$
T^{4}(\zeta)=\frac{3}{4}T_{\rm eff}^{4}
\left[\tau_{\rm gray}(\zeta)+\frac{2}{3}\right].
$$

随后用新 H/He opacity 积分到中面的有效光深：

$$
\tau_{\rm eff}(\nu)=
\int_{z_{\rm surf}}^{0}
\rho
\sqrt{3\kappa_{\nu}^{\rm abs}
\left(\kappa_{\nu}^{\rm abs}+\kappa_{\nu}^{\rm es}\right)}
\,\mathrm dz.
$$

在图示 $1$--$1000\ {\rm eV}$ 范围内，该控制柱的 $\tau_{\rm eff}$ 全部大于 1；257 与
513 个垂向点的整条曲线 $L_{2}$ 相对误差为 $3.02\times10^{-7}$。`[A/V]`

这只说明在所采用 LTE 布居和灰温度初值下，H/He 连续吸收足以产生很大的有效光深。它不
说明真实非 LTE 表层必然热化，也不决定能量从哪一柱深释放；因此仍不能把
$B_{\nu}[T(\zeta)]$ 积分成正式 ZO 输出谱。`[O]`

## 8. 六面板图逐一解释

![Phase 7B3 H/He 原子率与静态耦合控制](../outputs/phase7b3_atomic_continuum_controls.png)

### 面板 (a)：基态光致电离截面

三条曲线从各自阈值出现，并随能量下降。He I 不再用任意氢样阈值截面，而是使用实验约束
的 Verner 拟合。曲线终止于本图的 $1\ {\rm keV}$ 展示上限；代码拟合域上限为
$50\ {\rm keV}$。`[L/V]`

### 面板 (b)：总辐射复合率

三条曲线随温度降低而增大。图只画到 $10^{6}\ {\rm K}$，因为正式 He I 低温分支在此结束。
H I 和 He II 拟合本身有更宽温度域。`[L/V]`

### 面板 (c)：规定辐射场下的电离稳态

横轴 $W$ 只缩放外加 Planck 场。H 在这组选定控制密度下很快保持 H II；He 随 $W$ 增大从
He I 经 He II 过渡到 He III。曲线验证耦合求根连续且守恒，不代表 ZO 轨道上的实际相位
演化。`[A-control/V]`

### 面板 (d)：带物理 opacity 的等温纯吸收板层

纵轴为 $F_{\nu}^{\rm out}/(\pi B_{\nu})$。离化边使 $\tau_{\nu}$ 跳变，从而产生突变；数值
曲线和解析曲线重合，说明变化来自 opacity 而不是转移伪影。这仍是控制输入谱，不是
modified-blackbody 的替代输出。`[A-control/V/O]`

### 面板 (e)：真实 ZO 代表柱的有效光深

H I、He I、He II 边在 $\tau_{\rm eff}$ 曲线上留下清楚结构；虚线是
$\tau_{\rm eff}=1$。整条控制曲线位于虚线上方，但温度和布居仍依赖 LTE/灰初值。`[A/V/O]`

### 面板 (f)：三个独立收敛轴

蓝线为 He I 光致电离率的频率网格误差，橙线为转移角求积误差，绿线为 ZO 有效光深的垂向
网格误差。2049 点频率、64 阶角求积和 257 点垂向网格都低于 $10^{-3}$；三条轴没有用一个
总误差相互掩盖。`[V]`

## 9. 产物、测试与复现

```bash
cd /Users/shandike/Downloads/A_USTCer/8.3/eccentric_tde_observer
uv run python scripts/phase7b3_atomic_continuum_controls.py --output-dir outputs
uv run pytest -q
```

- `src/eccentric_tde_observer/atomic_continuum.py`：原子数据、率积分、电离稳态和 LTE opacity；
- `tests/test_atomic_continuum.py`：12 个原子率、守恒、解析积分和转移耦合测试；
- `outputs/phase7b3_atomic_continuum_report.json`：假设、数据来源、接受门和开放问题；
- `outputs/phase7b3_photoionization_cross_sections.csv`：逐能量 H/He 基态截面；
- `outputs/phase7b3_recombination_rates.csv`：逐温度总辐射复合率；
- `outputs/phase7b3_photoionization_equilibrium.csv`：逐稀释因子的最小稳态；
- `outputs/phase7b3_static_transfer_spectrum.csv`：带真实 opacity 的数值/解析板层控制；
- `outputs/phase7b3_zo_effective_depth.csv`：真实代表柱频率分辨有效光深；
- `outputs/phase7b3_convergence.csv`：频率、角度和垂向三条收敛轴；
- `outputs/phase7b3_atomic_continuum_controls.png`：六面板总图。

本阶段新增 13 个原子数据、率积分、守恒、解析转移和非法输入测试；合入后的全项目现场
回归在 Phase 7B4b 合入后为 `242 passed`。以后复现仍以当次测试输出为准。`[V]`

## 10. 当前允许与禁止的结论

> `[L/V]` 可以说：项目已经有可追溯的最小 H/He 基态连续谱截面、总辐射复合率、守恒
> 光致电离稳态和静态 opacity--transfer 接口；旧 He I 任意近似不再是 Phase 7B3 正式路径。

> `[O]` 不能说：项目已经完成 NLTE 大气或得到比 modified-blackbody 更可信的最终 ZO
> 连续谱。当前 Planck 场、等温板层和灰温度剖面都是输入，能量方程与耗散深度尚未闭合。

后续已选择“先补碰撞电离与三体详细平衡，再做轨道推进”的最小顺序；第一步已由
[[eccentric_tde_observer/docs/phase7b4a_collisional_kinetics|Phase 7B4a]] 完成。以下问题中，
第 2 项的碰撞分支已经关闭，其余仍开放：

1. ZO 的总表面耗散如何分配到柱质量深度；
2. H/He 碰撞电离和三体详细平衡已经通过；激发态与 bound--bound 仍未加入；
3. 如何把 $J_{\nu}$、布居和气体温度联立，而不是外加 Planck 场；
4. 如何在轨道周期上加入 $v_{z}/c$ 频率--角度项和辐射能量反馈；
5. 高光深散射正式求解器如何替换当前稠密 $\Lambda$ 控制路径。

Phase 7B4b 已关闭第 4 项中的基态轨道周期推进部分；Phase 7B4c 又完成第 3 项的规定场接口；
[[eccentric_tde_observer/docs/phase7b4d_coupled_slab|Phase 7B4d]] 已在固定 $T,\rho$ 板层闭合
$J_{\nu}$--基态布居--opacity 固定点；
[[eccentric_tde_observer/docs/phase7b4e_continuum_emission|Phase 7B4e]] 又完成同截面基态 Milne
连续发射与固定温度能量账本，但还没有气体温度方程、激发态总复合级联或 $v_{z}/c$ 项。
其余选择会 materially 改变后续方程和计算成本，应逐阶段讨论再执行。
`[O]`
