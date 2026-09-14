# Phase 7B4f：规定加热下的固定密度板层温度平衡

> [!abstract] 阶段结论
> `[V]` 本阶段把 Phase 7B4e 的基态 H/He 连续谱净辐射加热接入逐深度温度方程，完成
> $T(z)$--$J_{\nu}(z)$--基态布居--opacity--发射的静态联立求解，并显式检查温度根、无根、
> 初值独立性和热稳定性。
> `[V]` 零机械加热的受照控制层得到 $4.105\times10^{4}$--$4.436\times10^{4}\ {\rm K}$
> 的稳定辐射平衡；局域和全局能量相对残差分别为 $3.28\times10^{-14}$ 和
> $2.95\times10^{-17}$。
> `[A/V]` 若把 Phase 7B1 近心点单面耗散通量全部均匀沉积在当前
> $10^{-4}\ {\rm g\,cm^{-2}}$ 薄控制层中，则在 $10^{4}$--$3\times10^{6}\ {\rm K}$ 扫描域内
> 没有温度根。该结果只否定这种**极浅沉积闭合**，不等于证明整个静态 ZO 大气无解。
> `[O]` 频率 257 到 513 基点的温度剖面差仍为 $1.15\%$；激发态、线冷却、Compton 交换、
> 压缩功、真实耗散深度和轨道耦合也仍未闭合。因此不能用本阶段谱替换 Phase 4。

导航：[[eccentric_tde_observer/README|项目 README]] ·
[[eccentric_tde_observer/docs/phase7b4e_continuum_emission|Phase 7B4e 基态连续发射]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

---

## 1. 7B4f 关闭的缺口

Phase 7B4e 在规定温度下计算

$$
q_{\rm rad}(z)
=4\pi\int
\left[
\chi_{\nu}^{\rm abs}J_{\nu}
-\eta_{\nu}^{\rm th}
\right]\,\mathrm d\nu,
$$

但只能把 $-q_{\rm rad}$ 记为“维持恒温所需的 thermostat”，并不知道温度本身。7B4f 改为
求解

$$
q_{\rm net}(z)
=q_{\rm heat}(z)
+q_{\rm rad}
\left[
T(z),\boldsymbol{x}(z),J_{\nu}(z)
\right]
=0.
$$

每次温度试探都会完整重算 Milne 连续系数、辐射转移、光致电离/复合率和电荷自洽布居；
稳定性有限差分也不冻结 $J_{\nu}$ 或布居。`[A/V]`

温度以 $y=\ln T$ 为数值未知量，在声明温度域中求根。温度边界只定义当前原子闭合的适用域；
若最小二乘解停在边界或残差不为零，代码抛出 `TemperatureBalanceConvergenceError`，不会把边界
值裁成一个“解”。`[V]`

## 2. 可追溯的规定加热

一面 ZO 耗散通量由

$$
F_{\rm diss}=\sigma_{\rm SB}T_{\rm eff}^{4}
$$

给出。在固定密度、厚度 $L$ 的控制板层中，均匀几何深度沉积定义为

$$
q_{\rm heat}=\frac{F_{\rm diss}}{L}.
$$

这只是 `[A-deposition]`，不是 ZO 已给出的垂向耗散剖面。正式压力测试直接读取
`outputs/phase7b_periodic_column_background.csv` 的近心点行：

- $T_{\rm eff}=36496.09\ {\rm K}$；
- $F_{\rm diss}=1.0060\times10^{14}\ {\rm erg\,s^{-1}\,cm^{-2}}$；
- Phase 7B1 的真实单面柱质量为 $585.59\ {\rm g\,cm^{-2}}$；
- 本阶段薄控制层只有 $10^{-4}\ {\rm g\,cm^{-2}}$。

因此“全部通量沉积到薄层”故意是最浅沉积压力测试。它不能代表完整单面柱，也不能据此宣布
静态大气近似整体失败。`[A/V]`

## 3. 根与热稳定性

### 3.1 等温总能量曲线

先扫描均匀温度下的面积分净加热

$$
Q_{\rm net}(T)
=F_{\rm heat}
+\int q_{\rm rad}(T,z)\,\mathrm dz.
$$

每一对相邻有效采样点若异号，就形成独立括区间；失败点被显式记录，代码不跨越失败点连接
根。当前采样曲线在整个声明温度域单调下降，没有发现多个根。`[V]`

标量根的等容稳定性判据为

$$
\left.\frac{\mathrm dQ_{\rm net}}{\mathrm dT}\right|_{T_{\rm eq}}<0.
$$

### 3.2 逐深度稳定性

对逐深度解构造完整矩阵

$$
\mathsf{J}_{\rm ij}
=\frac{\partial q_{{\rm net},i}}{\partial T_{j}}.
$$

当前控制用正的单原子平动热容

$$
C_{\rm V,i}
=\frac{3}{2}k_{\rm B}
\left(n_{\rm H}+n_{\rm He}+n_{{\rm e},i}\right)
$$

构造温度增长矩阵 $\mathsf{C}_{\rm V}^{-1}\mathsf{J}$。全部特征值实部为负才标记为稳定。这里未
加入电离/激发内能，因此增长率大小是 `[A-control]`；稳定性符号仍是当前闭合的代码验证。

## 4. 正式控制参数

| 量 | 数值 |
|---|---:|
| 密度 | $10^{-10}\ {\rm g\,cm^{-3}}$ |
| 控制层柱质量 | $10^{-4}\ {\rm g\,cm^{-2}}$ |
| 入射辐射温度 | $1.5\times10^{5}\ {\rm K}$ |
| 入射稀释因子 | $10^{-6}$ |
| 光子能量域 | $0.1$--$5000\ {\rm eV}$ |
| 温度扫描域 | $10^{4}$--$3\times10^{6}\ {\rm K}$ |
| 主频率基点/边分辨后 | $257/263$ |
| 主深度单元 | $8$ |
| 主半区间角阶数 | $8$ |

该控制延续 7B4e 的受照薄板层，目的是隔离温度方程，不是选择真实 ZO 光球的密度和柱质量。
`[A-control]`

## 5. 数值结果

### 5.1 零机械加热辐射平衡

逐深度解为

$$
4.105\times10^{4}\ {\rm K}
\le T(z)\le
4.436\times10^{4}\ {\rm K}.
$$

最大局域能量相对残差为 $3.28\times10^{-14}$，全层相对残差为
$2.95\times10^{-17}$；从 $45000\ {\rm K}$ 与 $80000\ {\rm K}$ 初温出发，温度剖面的最大相对
差为 $5.31\times10^{-15}$。最大热增长率为 $-1.474\ {\rm s^{-1}}$，在三组差分步长下均为
负。`[V]`

该解严格是**外部照明下、零机械耗散的辐射平衡**。它不能被称为 ZO 耗散大气。`[A/V]`

### 5.2 规定加热根

| 沉积通量/$F_{\rm ZO,\rm peri}$ | 根温度 | 稳定性 |
|---:|---:|---|
| $0$ | $4.1903\times10^{4}\ {\rm K}$ | 稳定 |
| $10^{-6}$ | $4.5455\times10^{4}\ {\rm K}$ | 稳定 |
| $10^{-5}$ | $9.2107\times10^{4}\ {\rm K}$ | 稳定 |
| $3\times10^{-5}$ | $3.8312\times10^{5}\ {\rm K}$ | 稳定 |
| $10^{-4}$ | 无根 | -- |
| $1$ | 无根 | -- |

在上界 $3\times10^{6}\ {\rm K}$，当前有限能段基态连续冷却最多只能平衡约
$7.67\times10^{-5}F_{\rm ZO,\rm peri}$。完整 ZO 通量压力测试的最小净加热仍为
$1.0059\times10^{14}\ {\rm erg\,s^{-1}\,cm^{-2}}$，因此无根结论比当前百分级频率误差大约
四个数量级，根拓扑结论稳健。`[V]`

这里的“无根”可能由过浅沉积、缺失激发态/线冷却、缺失 Compton 交换或固定密度近似引起；
本阶段不能从中选择唯一原因。`[O]`

### 5.3 与固定 $40000\ {\rm K}$ 连续谱的差异

零机械加热温度闭合与固定 $40000\ {\rm K}$ 控制的总出射有限能段通量相差约 $0.200\%$；
逐频差的积分绝对值约为平衡谱积分的 $0.734\%$，峰值归一化最大绝对差约为 $3.80\%$。
这说明在**这个零耗散受照控制**中，温度闭合对连续谱改变较小；它不能外推为“包含 ZO 耗散
后 modified-blackbody 已经足够”。`[V/O]`

## 6. 图件逐一解释

![Phase 7B4f 温度平衡主图](../outputs/phase7b4f_temperature_balance.png)

### (a) Isothermal root topology

纵轴是相对 ZO 近心点单面通量的全层净加热。零机械加热到 $3\times10^{-5}$ 沉积分数各有
一条由正变负的稳定根；$10^{-4}$ 与完整通量曲线在扫描域始终为正。图中的对数对称纵轴只
改变显示，不修改数据。`[V]`

### (b) Depth-resolved radiative equilibrium

从受照顶面向下，温度先轻微下降，再向底部升高到约 $4.44\times10^{4}\ {\rm K}$。8 到16
深度单元的最大相对差只有 $2.04\times10^{-4}$，因此该弯曲不是粗深度网格产生的单点异常。
`[V]`

### (c) Ground-state ionization at equilibrium

氢几乎完全电离；氦以 He III 为主，He II 由顶面约 $0.04$ 增至底部约 $0.06$。这只是基态
H/He 网络，不能用于真实金属离子或谱线诊断。`[A/V]`

### (d) Continuum response to the temperature closure

平衡 $T(z)$ 与固定 $40000\ {\rm K}$ 的总出射连续谱在图上大体重合，差异主要集中在连续边
附近。两条曲线均为受照薄层控制谱，不是 Phase 4 的替换表。`[V/O]`

![Phase 7B4f 收敛与失败门](../outputs/phase7b4f_temperature_convergence.png)

### (a) Temperature-profile refinement

深度 8 到16 已达到 $2.04\times10^{-4}$；角度 8 到16 为 $3.93\times10^{-3}$；频率 257 到
513 仍为 $1.15\times10^{-2}$。初温差消失到双精度水平。频率因此是当前误差预算的主项。
`[V]`

### (b) Emergent-flux refinement

底面出射能流在三条加密轴上均优于 $4\times10^{-4}$；顶部能流的频率加密误差仍为
$7.75\times10^{-3}$，角度和深度误差分别约 $5.06\times10^{-4}$ 与
$2.38\times10^{-4}$。`[V]`

### (c) Thermal-stability derivative sensitivity

相对差分步长从 $5\times10^{-4}$ 到 $2\times10^{-3}$ 时，最大增长率相对 $10^{-3}$ 控制
只变化亚 ppm，符号始终为负。`[V]`

### (d) Root survival under prescribed heating

在采样的受控沉积分数中，根从一条直接变为零条，没有出现两条或更多根。横轴最左点把零
机械加热放在 $10^{-7}$ 仅用于对数坐标显示，CSV/JSON 中仍严格记录为零。`[A-plot/V]`

## 7. 收敛与当前精度

| 加密轴 | 温度剖面最大相对差 | 顶面出射能流相对差 | 等温根温度相对差 |
|---|---:|---:|---:|
| 257 到 513 频率基点 | $1.153\times10^{-2}$ | $7.747\times10^{-3}$ | $1.070\times10^{-2}$ |
| 8 到16 深度单元 | $2.039\times10^{-4}$ | $2.381\times10^{-4}$ | $3.693\times10^{-5}$ |
| 8 到16 半区间角阶数 | $3.926\times10^{-3}$ | $5.063\times10^{-4}$ | $1.808\times10^{-3}$ |

能量方程残差远小于离散化差，不应把二者混为一谈。当前根拓扑和完整通量无根门已稳健；
零加热温度与细谱差异只能按百分级频率精度使用。`[V]`

## 8. 文件、测试与复现

核心文件：

- `src/eccentric_tde_observer/continuum_emission.py`：温度输入扩展为逐深度剖面；
- `src/eccentric_tde_observer/thermal_balance.py`：规定加热、根扫描、逐深度温度解与稳定性矩阵；
- `tests/test_thermal_balance.py`：Kirchhoff、加热积分、多根区间、稳定根、无根和制造解；
- `scripts/phase7b4f_temperature_balance.py`：正式计算、直接加密、报告与英文图件。

机器可读产物：

- `outputs/phase7b4f_temperature_balance_report.json`：假设、根、稳定性、收敛和阶段边界；
- `outputs/phase7b4f_temperature_profile.csv`：逐深度温度、布居和能量项；
- `outputs/phase7b4f_isothermal_scan.csv`：各规定加热下的温度扫描；
- `outputs/phase7b4f_temperature_convergence.csv`：温度剖面与出射谱直接加密；
- `outputs/phase7b4f_isothermal_root_convergence.csv`：等温根的三轴直接加密；
- `outputs/phase7b4f_stability_sensitivity.csv`：稳定性差分步长；
- `outputs/phase7b4f_emergent_continuum.csv`：温度闭合与固定温度连续谱；
- `outputs/phase7b4f_temperature_balance.png`：主结果图；
- `outputs/phase7b4f_temperature_convergence.png`：收敛与失败门。

复现命令：

```bash
cd /Users/shandike/Downloads/A_USTCer/8.3/eccentric_tde_observer
uv run python scripts/phase7b4f_temperature_balance.py --output-dir outputs
uv run pytest -q
```

代码不使用 `nan_to_num`、无物理理由的 `clip`、任意 floor、失败点删除或事后重归一化。
本阶段新增 7 项温度平衡专项测试；全项目现场回归为 `272 passed`。`[V]`

## 9. 路线决策

> `[V]` 当前不能进入 UVOT 仪器层：温度闭合在零机械加热控制中对谱的影响虽小，但真实 ZO
> 耗散尚不能在当前薄层中达到能量平衡。

> `[V/O]` 当前也不能据此直接宣布静态近似失败并跳到周期动态 NLTE：无根压力测试把完整
> 单面耗散压入远小于真实单面柱质量的薄层，尚未扫描物理耗散深度。

该门现已由
[[eccentric_tde_observer/docs/phase7b4g_finite_deposition_column|Phase 7B4g 有限沉积柱静态门]]
完成：有限柱得到稳定根，故不进入周期动态 NLTE；但连续谱相对局域黑体差异大，下一步建立
带静力密度、物理耗散结构和中面对称边界的有限大气表。`[A/V/O]`
