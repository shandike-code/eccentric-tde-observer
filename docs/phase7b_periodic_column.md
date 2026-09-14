# Phase 7B1：规定 ZO 背景的周期柱与守恒布居控制核

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7a_static_annulus|Phase 7A 静态环带审计]] ·
[[eccentric_tde_observer/docs/phase4a_annulus_bridge|Phase 4A 动态柱接口]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

## 1. 本阶段已经完成什么

Phase 7A 证明 TLUSTY 208 的官方 H/He LTE/NLTE 控制可以工作，但 12 个实际低 $Q$ 代表柱
没有一个通过静态大气谱验收。Phase 7B1 因而不再把整条轨道拼成一串静态 annulus，而是先
建立下面四项基础：

1. 一个实际 ZO 半长轴柱的精确开普勒时间轴；
2. 规定的 $\Sigma(E),H(E),T_{\rm eff}(E),Q(E)$、同源密度和垂向速度背景；
3. 保持非负与粒子数守恒的周期率方程推进器；
4. 有连续解析周期解的两态控制和独立时间/垂向网格收敛。`[A/V]`

本阶段**没有**给出物理原子跃迁率，没有求频率--角度辐射转移，没有选择物理耗散深度剖面，
也没有输出 NLTE 连续谱。这里的“两态”只是数值控制，不代表 H I/H II 或任何真实能级。
`[A-control/O]`

时间依赖非灰 NLTE 转移本身是成熟的问题类型，例如 Jack、Hauschildt 与 Baron 的
[PHOENIX 时间依赖扩展](https://arxiv.org/abs/0907.1441)和 Hillier 与 Dessart 的
[CMFGEN 时间依赖工作](https://arxiv.org/abs/1204.0527)都同时强调时间项、NLTE 与能量
守恒；这些文献支持方程结构和验收思想，不表示其超新星代码可直接移植到 ZO 柱。`[L]`

## 2. 轨道时间轴不是均匀偏近点角

对固定半长轴 $a$ 与偏心率 $e$，平均运动和周期为

$$
n=\sqrt{\frac{GM_{\bullet}}{a^{3}}},\qquad
P=\frac{2\pi}{n}.
$$

偏近点角 $E$ 到时间的精确映射是

$$
M=E-e\sin E=nt,\qquad
\frac{\mathrm dt}{\mathrm dE}=\frac{1-e\cos E}{n}.
$$

代码直接计算每个网格点的 $M(E)$，再用相邻 $M$ 的差构造周期时间步；最后一个网格点到
$2\pi$ 的尾步也显式保留。1024 点主网格上的所有 $\Delta t_{k}$ 都为正，并满足

$$
\left|\frac{\sum_{k}\Delta t_{k}}{P}-1\right|
=2.22\times10^{-16}.
$$

这个映射中的 $1-e\cos E$ 与 Erratum corrected 面积元中的同形因子有共同的开普勒几何
来源，但这里是局域柱的时间坐标，不是面积积分。Phase 7B1 没有调用 pre-Erratum 面积；
代表柱仍来自 Phase 7A 的 corrected 面积加权抽样。`[L/V]`

## 3. 规定背景与同源垂向速度

本阶段选择 Phase 7A 代表柱 03 所在的径向网格点，即 $a=3.87457\times10^{14}\ \mathrm{cm}$、
$e=0.6$，轨道周期为 $4.15961\times10^{6}\ \mathrm{s}$。这里只沿该半长轴走完整轨道；
代表柱在 $E=0$ 被选中并不意味着整条轨道都准静态。`[V]`

采用已有的有限支撑 $n=3$ 垂向闭合，固定同源坐标

$$
\zeta=\frac{z}{H(E)}.
$$

密度和速度为

$$
\rho(E,\zeta)
=\frac{\Sigma(E)}{H(E)}f(\zeta),\qquad
v_{z}(E,\zeta)
=\zeta H(E)\frac{\mathrm d\ln H}{\mathrm dt}.
$$

这两个关系只把既有 ZO 的 $\Sigma$、$H$ 和呼吸率写成一维柱背景，不反向修改源动力学。
用 4001 个 $\zeta\in[-3,3]$ 点重新积分密度，回收 $\Sigma$ 的最大相对残差为
$9.33\times10^{-15}$。`[L/A/V]`

该柱一周内的实际范围为：

| 量 | 最小值 | 最大值 | 解释 |
|---|---:|---:|---|
| $T_{\rm eff}$ | $1.0871\times10^{4}\ \mathrm K$ | $3.6496\times10^{4}\ \mathrm K$ | ZO 规定源场 |
| $H$ | $1.3579\times10^{12}\ \mathrm{cm}$ | $5.1383\times10^{13}\ \mathrm{cm}$ | 变化因子 37.84 |
| $Q_{\rm pressure}$ | $3.4900\times10^{-13}\ \mathrm{s^{-2}}$ | $1.6777\times10^{-9}\ \mathrm{s^{-2}}$ | 变化因子 4807 |
| $\epsilon_{\rm dyn}$ | 0 | 1.9999 | 大部分轨道不能假定静态跟随 |
| $\tau_{\rm es,0}$ | 199.10 | 199.10 | 常偏心参考柱的单侧散射深度 |

特别要注意，$E=0$ 是呼吸运动的转向点，所以该瞬间
$\mathrm dH/\mathrm dt=0$、$\epsilon_{\rm dyn}=0$。这只说明瞬时速度为零，不说明其后加速度
或整条轨道的动态项很小。`[V]`

## 4. 目前能够计算和不能升级的时标

已直接计算三个时标诊断：

$$
t_{\rm lc}=\frac{H}{c},\qquad
t_{\rm es,\rm proxy}=\tau_{\rm es,0}\frac{H}{c},\qquad
t_{\rm Q}=\frac{1}{\sqrt{Q_{\rm pressure}}}.
$$

其中 $t_{\rm lc}/P$ 的范围是 $1.09\times10^{-5}$--$4.12\times10^{-4}$；
$t_{\rm Q}/P$ 最高约为 0.41。散射代理 $t_{\rm es,\rm proxy}/P$ 为
0.00217--0.0820，但它忽略频率依赖吸收、真实光子产生和有限剖面系数，只是
`[A-proxy]`，不能称为已求出的辐射扩散时间。`[A/V]`

目前不能计算可信的复合、光致电离或碰撞跃迁时标，因为这些量需要局域气体温度、电子密度、
辐射场和真实原子率。把 $T_{\rm gas}=T_{\rm eff}$ 或完全电离状态未经检验地代入只会把未知
物理伪装成结果，因此本阶段没有这样做。`[O]`

## 5. 守恒周期率方程核

布居采用列向量约定

$$
\frac{\mathrm d\boldsymbol n}{\mathrm dt}
=\mathbf R(t)\boldsymbol n.
$$

每个输入生成元必须满足

$$
R_{i j}\ge0\quad(i\ne j),\qquad
\sum_{i}R_{i j}=0.
$$

第一项保证真实跃迁率非负，第二项保证总粒子数守恒。代码对负跃迁、正对角损失项和列和不为
零的矩阵直接报错，不用 `clip` 修复。一个时间区间内采用相邻生成元的平均

$$
\overline{\mathbf R}_{k+1/2}
=\frac{\mathbf R_{k}+\mathbf R_{k+1}}{2},\qquad
\boldsymbol n_{k+1}
=\exp\left(\Delta t_{k}\overline{\mathbf R}_{k+1/2}\right)\boldsymbol n_{k}.
$$

平均矩阵仍是合法生成元；矩阵指数适合刚性线性率方程，并在这个平滑控制问题上给出二阶时间
收敛。程序逐周期迭代，直到起点与终点的最大布居差除以总丰度低于 $10^{-11}$。整个过程不
加入 population floor、不裁剪负值、不逐步重归一化；若出现负布居或守恒超限就失败。`[A/V]`

## 6. 两态解析周期控制

为了把“看起来有滞后”变成解析可检验的问题，定义

$$
x_{\rm eq}(M)=0.5+0.4\cos M,\qquad
\frac{\mathrm dx}{\mathrm dt}
=\frac{x_{\rm eq}(t)-x}{\tau_{\rm rel}}.
$$

连续周期解为

$$
x(t)=0.5
+0.4\,A\cos\left(M-\delta\right),\qquad
A=\frac{1}{\sqrt{1+\left(2\pi\tau_{\rm rel}/P\right)^{2}}},\qquad
\delta=\arctan\left(\frac{2\pi\tau_{\rm rel}}{P}\right).
$$

四档完整敏感性结果为：

| $\tau_{\rm rel}/P$ | 数值/解析振幅比 | 数值/解析相位滞后 | 最大绝对误差 | 周期迭代数 |
|---:|---:|---:|---:|---:|
| 0.01 | 0.997940 / 0.998032 | $3.6618^\circ/3.5953^\circ$ | $6.65\times10^{-4}$ | 2 |
| 0.1 | 0.846660 / 0.846733 | $32.1486^\circ/32.1419^\circ$ | $8.86\times10^{-5}$ | 4 |
| 1 | 0.157163 / 0.157177 | $80.9576^\circ/80.9569^\circ$ | $2.47\times10^{-5}$ | 22 |
| 10 | 0.0159121 / 0.0159135 | $89.0882^\circ/89.0882^\circ$ | $1.89\times10^{-5}$ | 141 |

最大粒子守恒残差为 $6.22\times10^{-15}$，最小布居为 0.1008，最大周期边界残差为
$9.46\times10^{-12}$。快速响应控制 $\tau_{\rm rel}/P=0.01$ 最难解析，因为 1024 点
pericentre-clustered 网格的最大时间步仍为 $0.00778P$；它的误差被保留并在下一节单独收敛。
`[A-control/V]`

新增的 8 项单元测试覆盖轨道周期闭合、圆盘时间极限、垂向质量、耗散输入拒绝、非法率矩阵、
解析周期解、二阶收敛和初值遗忘；本轮完整项目回归为 `195 passed`。`[V]`

## 7. 分层收敛

### 7.1 轨道时间网格

以 2048 点为背景积分对照，1024 点的时间平均 $H$ 与表面能流相对差分别为
$1.21\times10^{-5}$ 和 $2.71\times10^{-5}$。最快两态控制的最大解析误差随
128、256、512、1024、2048 点依次为

$$
3.14\times10^{-2},\quad
9.73\times10^{-3},\quad
2.61\times10^{-3},\quad
6.65\times10^{-4},\quad
1.67\times10^{-4}.
$$

后三级每次加倍网格约把误差缩小 4，符合二阶收敛。主产物仍使用与 Phase 4/7A 一致的
1024 点背景，并如实报告其 $6.65\times10^{-4}$ 控制误差。`[V]`

### 7.2 垂向网格

在有限支撑 $\zeta\in[-3,3]$ 上，17、33、65、129、257 点回收 $\Sigma$ 的最大相对误差为

$$
3.54\times10^{-5},\quad
2.22\times10^{-6},\quad
1.39\times10^{-7},\quad
8.69\times10^{-9},\quad
5.43\times10^{-10}.
$$

这只验证规定剖面的质量积分；频率、角度、柱质量上的辐射转移收敛要等对应算子实现后才能
测试，不能写成已通过。`[V/O]`

## 8. 四面板图怎样读

![Phase 7B1 周期柱与守恒布居控制](../outputs/phase7b_periodic_column_control.png)

**(a) 实际 ZO 规定背景。** 三条曲线都按真实轨道时间平均归一化。近心点附近
$T_{\rm eff}$ 和 $F_{\rm surf}=\sigma_{\rm SB}T_{\rm eff}^{4}$ 集中升高，而 $H$ 被强烈压缩；
横轴是 $t/P$，不是把非均匀 $E$ 当均匀时间。`[V]`

**(b) 输运与垂向响应时标。** $H/c$ 始终很短，但这不等于辐射场能立即达到 NLTE 平衡；
散射代理最高约 $0.082P$，$1/\sqrt{Q_{\rm pressure}}$ 最高约 $0.41P$。这个面板说明必须把
“光传播快”“散射随机游走”和“柱结构响应”分开。`[A/V]`

**(c) 周期跟随控制。** 虚线是瞬时平衡。$\tau_{\rm rel}\ll P$ 时布居几乎跟随；
$\tau_{\rm rel}\sim P$ 时振幅受抑并明显滞后；$\tau_{\rm rel}\gg P$ 时只剩很小的周期响应。
这些曲线验证求解器行为，不是氢电离分数。`[A-control/V]`

**(d) 解析与数值对照。** 实线是解析振幅和相位滞后，点是数值拟合。四档结果落在解析曲线
上，说明周期边界、非均匀轨道时间和率方程推进是一致的。`[V]`

## 9. 耗散和上边界为何仍是开放项

ZO 的 $T_{\rm eff}(E)$ 给出单面总能流

$$
F_{\rm surf}(E)=\sigma_{\rm SB}T_{\rm eff}^{4}(E),
$$

却没有唯一给出耗散随单侧柱质量 $m\in[0,m_{0}]$ 的分配。未来输入必须明确提供

$$
q(m,E)\ge0,\qquad
\int_{0}^{m_{0}}q(m,E)\,\mathrm dm=F_{\rm surf}(E).
$$

`DepthDissipationProfile` 已建立“积分必须等于 1”的无量纲接口，未闭合输入会被拒绝，代码
不会事后重归一化。但 Phase 7B1 没有从若干任意剖面中挑一条作为物理结果。Hubeny 与 Hubeny
的[静态 NLTE 盘垂向结构](https://arxiv.org/abs/astro-ph/9804288)也明确显示垂向耗散/黏性
参数会影响结构和谱，因此这不是纯数值细节。`[L/O]`

上边界目前只登记“无外部入射”的真空边界契约；因为转移方程尚未实现，它并不产生强度。
未来若加入入射场，必须来自独立 seed SED，而不能为了得到 X-ray 或某条线任意添加。
`[A/O]`

## 10. 阶段结论与下一门

> `[V]` Phase 7B1 已把 Phase 7A 的一个实际半长轴柱扩展成完整、守恒、可收敛的一维周期
> 背景，并回收两态解析周期解。它验证了“动态布居求解器的数值底座”，没有验证真实原子
> 布居或局域谱。

> `[O]` modified-blackbody 尚未被替代。完成替代至少还要加入可追溯的 H/He 原子率、
> 频率--角度辐射转移、耗散深度闭合、粒子/电荷/辐射能守恒和相应网格收敛。

后续状态：Phase 7B2 已在规定背景旁建立并通过真空传播、纯吸收、保守纯散射和时间解趋近
静态解的转移控制，详见
[[eccentric_tde_observer/docs/phase7b2_transfer_controls|Phase 7B2 报告]]。Phase 7B3 随后
加入可追溯 H/He 基态光致电离、总辐射复合和静态 opacity 耦合，见
[[eccentric_tde_observer/docs/phase7b3_atomic_continuum|Phase 7B3 报告]]；速度频率耦合、
耗散深度、激发态和能量方程仍未闭合，因而尚无候选 NLTE 输出谱。`[A/V/O]`

机器可读证据位于：

- `outputs/phase7b_periodic_column_report.json`；
- `outputs/phase7b_periodic_column_background.csv`；
- `outputs/phase7b_kinetics_sensitivity.csv`；
- `outputs/phase7b_time_grid_convergence.csv`；
- `outputs/phase7b_vertical_grid_convergence.csv`。
