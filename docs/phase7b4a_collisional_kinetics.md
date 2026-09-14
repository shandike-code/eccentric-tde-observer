# Phase 7B4a：H/He 碰撞动力学与固定背景松弛控制

> [!abstract] 阶段结论
> `[L/V]` 本阶段接入 Voronov（1997）的 H I、He I、He II 电子碰撞电离总率拟合，建立
> 守恒 H/He 率矩阵，并回收固定率两态解析松弛、电荷中性和高密度 LTE 极限。
> `[A-control]` 三体复合系数暂由同一组基态 Saha 因子按详细平衡构造，不是独立原子数据；
> ZO 轨道中面时标仍使用灰 Eddington 温度和 LTE 电子密度作为规定背景。
> `[O]` 当前没有激发态、能量方程、$J_{\nu}$--布居迭代、轨道时间推进或速度频率耦合，
> 因而仍未产生可替代 modified-blackbody 的 NLTE 输出谱。

导航：[[eccentric_tde_observer/README|项目 README]] ·
[[eccentric_tde_observer/docs/phase7b3_atomic_continuum|Phase 7B3 原子连续谱控制]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

---

## 1. 为什么把 Phase 7B4 拆成 7B4a

Phase 7B3 已有光致电离和辐射复合，但尚不能回答两个基本问题：

1. 在无外部辐照时，电子碰撞能否推动 H/He 电离；
2. 加入对应逆过程后，率方程是否连续回到 LTE 高密度极限。

若直接把不完整碰撞率放入整轨道推进器，周期结果可能只是错误微观率的放大。因此本阶段只
完成三件事：核定碰撞率、建立详细平衡控制、验证固定背景松弛。轨道时间耦合留给 Phase
7B4b。这个拆分不修改 ZO 的 $\Sigma(a,E)$、$H(a,E)$ 或 $T_{\rm eff}(a,E)$。`[A/V]`

## 2. Voronov 碰撞电离率

采用 [Voronov 1997](https://doi.org/10.1006/adnd.1997.0732) 的总电子碰撞电离率拟合，参数
逐项来自作者发布的 [cfit.dat](https://www.pa.uky.edu/~verner/dima/col/cfit.dat)，公式与
作者的 [cfit.f](https://www.pa.uky.edu/~verner/dima/col/cfit.f) 对照。每个靶粒子的率系数为

$$
C_{i}(T)=
A_{i}
\frac{1+P_{i}U_{i}^{1/2}}{X_{i}+U_{i}}
U_{i}^{K_{i}}\exp(-U_{i}),
$$

$$
U_{i}=\frac{\Delta E_{i}}{k_{\rm B}T}.
$$

参数和有效域为：

| 靶离子 | $\Delta E_{i}$ (eV) | $P_{i}$ | $A_{i}$ ($\mathrm{cm^{3}\,s^{-1}}$) | $X_{i}$ | $K_{i}$ | $k_{\rm B}T$ 有效域 |
|---|---:|---:|---:|---:|---:|---:|
| H I | 13.6 | 0 | $2.91\times10^{-8}$ | 0.2320 | 0.39 | $1\ \mathrm{eV}$--$20\ \mathrm{keV}$ |
| He I | 24.6 | 0 | $1.75\times10^{-8}$ | 0.1800 | 0.35 | $1\ \mathrm{eV}$--$20\ \mathrm{keV}$ |
| He II | 54.4 | 1 | $2.05\times10^{-9}$ | 0.2650 | 0.25 | $3\ \mathrm{eV}$--$20\ \mathrm{keV}$ |

代码在有效域外直接拒绝输入。作者旧 Fortran 为避免指数下溢使用了 $U>80$ 时置零的数值
分支；本项目没有复制该硬置零。H/He 表的有效域内最大 $U$ 远小于 80，可直接计算原拟合，
不需要 floor 或裁剪。`[L/V]`

在 $T=10^{5}\ \mathrm{K}$ 时，代码直接复算得到

$$
C_{\rm H\,\rm I}=3.96317495\times10^{-9}\ \mathrm{cm^{3}\,s^{-1}},
$$

$$
C_{\rm He\,\rm I}=4.79281837\times10^{-10}\ \mathrm{cm^{3}\,s^{-1}},
$$

$$
C_{\rm He\,\rm II}=3.14575734\times10^{-12}\ \mathrm{cm^{3}\,s^{-1}}.
$$

这些值来自公式和表参数，不是硬编码验收答案。`[V]`

## 3. 三体复合为什么只能先做详细平衡控制

碰撞电离和三体复合的体积率分别为

$$
R_{i\rightarrow i+1}^{\rm coll}=n_{i}n_{\rm e}C_{i},
$$

$$
R_{i+1\rightarrow i}^{\rm 3b}=n_{i+1}n_{\rm e}^{2}\beta_{i}.
$$

若要求这一对过程在 LTE 中满足同一组基态 Saha 关系

$$
\frac{n_{i+1}n_{\rm e}}{n_{i}}=S_{i}(T),
$$

则逆率必须满足

$$
\beta_{i}^{\rm DB}(T)=\frac{C_{i}(T)}{S_{i}(T)}.
$$

因此 $\beta_{i}^{\rm DB}$ 的单位是 $\mathrm{cm^{6}\,s^{-1}}$。代码用它验证方程方向、单位、
统计权重和 LTE 极限；它没有被称为独立高精度三体复合拟合。完整 NLTE 原子以后需要一致的
能级分辨碰撞强度、配分函数和逆过程，而不能永久停在基态总率。`[A-control/O]`

在 $10^{5}\ \mathrm{K}$ 的 $n_{\rm H}=10^{8}$--$10^{30}\ \mathrm{cm^{-3}}$ 密度扫描中，
只保留碰撞电离和该三体逆率时，三条 Saha 比值的最大相对误差为
$4.44\times10^{-16}$。`[V]`

## 4. 加入辐射复合后的最小稳态

相邻电离态的每粒子向上和向下率写成

$$
u_{i}=\Gamma_{i}+n_{\rm e}C_{i},
$$

$$
d_{i}=n_{\rm e}\alpha_{i}^{\rm RR}+n_{\rm e}^{2}\beta_{i}^{\rm DB}.
$$

稳态满足

$$
\frac{n_{i+1}}{n_{i}}=\frac{u_{i}}{d_{i}},
$$

并联立电荷中性

$$
n_{\rm e}=n_{\rm H\,\rm II}+n_{\rm He\,\rm II}+2n_{\rm He\,\rm III}.
$$

本阶段的无辐照密度控制取 $\Gamma_{i}=0$、$T=10^{5}\ \mathrm{K}$、
$n_{\rm He}=0.1n_{\rm H}$，并保留 Phase 7B3 的 Verner--Ferland 总辐射复合率。二分求根的
最大相对电荷残差为 $2.15\times10^{-16}$。`[A-control/V]`

辐射复合与三体复合下降率相等的电子密度是

$$
n_{{\rm e},i}^{\rm cross}=\frac{\alpha_{i}^{\rm RR}}{\beta_{i}^{\rm DB}}.
$$

在 $10^{5}\ \mathrm{K}$ 时分别为：

| 过渡 | $n_{{\rm e},i}^{\rm cross}$ ($\mathrm{cm^{-3}}$) |
|---|---:|
| H II $\rightarrow$ H I | $5.5072\times10^{17}$ |
| He II $\rightarrow$ He I | $1.7790\times10^{18}$ |
| He III $\rightarrow$ He II | $3.7511\times10^{19}$ |

因此低密度时总辐射复合破坏“碰撞电离--三体复合单独达到的 Saha 平衡”；随着密度升高，
$n_{\rm e}^{2}\beta_{i}$ 压过 $n_{\rm e}\alpha_{i}$，解才渐近回到 Saha。在扫描最低密度处，
最大离子分数差为 0.11956；在 $n_{\rm H}=10^{30}\ \mathrm{cm^{-3}}$ 时降到
$4.04\times10^{-13}$。后者是极限测试，不是 ZO 盘实际密度。`[L/A/V]`

## 5. 守恒率矩阵与固定状态松弛

采用列向量约定

$$
\frac{\mathrm d\boldsymbol n}{\mathrm dt}=\mathbf R\boldsymbol n.
$$

氢的率矩阵为

$$
\mathbf R_{\rm H}=
\begin{pmatrix}
-u_{\rm H} & d_{\rm H}\\
u_{\rm H} & -d_{\rm H}
\end{pmatrix}.
$$

氦的三态矩阵为

$$
\mathbf R_{\rm He}=
\begin{pmatrix}
-u_{1} & d_{1} & 0\\
u_{1} & -(d_{1}+u_{2}) & d_{2}\\
0 & u_{2} & -d_{2}
\end{pmatrix}.
$$

每一列严格求和为零，非对角元非负。固定背景的解析传播是

$$
\boldsymbol n(t)=\exp(\mathbf R t)\boldsymbol n(0).
$$

代码直接使用矩阵指数，没有负布居裁剪或每步重归一化。两态氢控制从全中性初态出发，解析
电离分数为

$$
x_{\rm H\,\rm II}(t)=x_{\rm H\,\rm II}^{\rm eq}
\left\{1-\exp[-(u_{\rm H}+d_{\rm H})t]\right\}.
$$

在选定刚性控制中，数值与解析解的最大绝对误差为 $3.12\times10^{-13}$，H/He 粒子数的
最大相对残差也是 $3.12\times10^{-13}$。氦演化画到 10 个最慢松弛时间，末点距平衡尚有
$4.03\times10^{-5}$；这是有限演化时间的指数余量，不是求解器误差。`[A-control/V]`

固定电子密度只用于隔离验证线性率网络。真实时间推进时，$n_{\rm e}$ 必须随布居重新满足
电荷中性，并与 $J_{\nu}$ 和温度共同更新。`[O]`

## 6. ZO 代表轨道的中面时标审计

对严格参考源径向索引 8，沿既有完整 ZO 轨道只构造中面控制状态：

$$
\rho_{0}(E)=\frac{\Sigma(E)}{H(E)}f(0),
$$

$$
T_{0}^{4}(E)=\frac{3}{4}T_{\rm eff}^{4}(E)
\left[\frac{\kappa_{\rm gray}\Sigma(E)}{2}+\frac{2}{3}\right].
$$

电子密度暂取同一 H/He 基态 LTE 解。该规定背景给出

$$
3.8033\times10^{4}\ \mathrm{K}
\le T_{0}\le
1.2769\times10^{5}\ \mathrm{K},
$$

$$
4.1727\times10^{12}\ \mathrm{cm^{-3}}
\le n_{\rm e}\le
1.5792\times10^{14}\ \mathrm{cm^{-3}}.
$$

整个轨道都处于三条 Voronov 拟合的共同有效温度域。由非零率矩阵本征值定义的局域松弛
时间相对轨道周期 $P=4.15961\times10^{6}\ \mathrm{s}$ 为

$$
2.43\times10^{-13}
\le \frac{t_{\rm relax,\rm H}}{P}\le
3.16\times10^{-10},
$$

$$
1.10\times10^{-10}
\le \frac{t_{\rm relax,\rm He}}{P}\le
6.62\times10^{-8}.
$$

这说明在**灰温度与 LTE 中面电子密度假设下**，中面局域 H/He 基态碰撞率比轨道变化快。
它不能推出表层 LTE：表层密度更低、辐射场直接参与布居，而且温度本身尚未由能量方程求出。
ZO 中面 $n_{\rm e}$ 也远低于上节三体复合交叉密度，所以三体过程对该控制中面并不占主导。
`[A/V/O]`

## 7. 收敛验收

### 7.1 电荷求根

以 128 次二分为参考，48 次二分的电子密度相对误差为
$1.78\times10^{-15}$；52 次与参考在双精度下相同。报告保留零误差记录，作图时不把零值
替换为任意 floor。`[V]`

### 7.2 ZO 轨道相位网格

以 2048 个源相位点为参考，把局域时标曲线周期插值到共同轨道时间网格。1024 点结果的
$\log_{10}t_{\rm relax}$ 均方根误差为

$$
\epsilon_{\rm H}=1.45\times10^{-5}\ \mathrm{dex},
\qquad
\epsilon_{\rm He}=1.59\times10^{-5}\ \mathrm{dex}.
$$

256、512、1024 点误差逐级约缩小四倍，说明该规定背景诊断已经进入平滑二阶收敛区。`[V]`

## 8. 主控制图逐面解释

![Phase 7B4a 碰撞动力学控制](../outputs/phase7b4a_collisional_kinetics_controls.png)

### (a) Voronov collisional ionization fits

三条曲线是 H I、He I、He II 总碰撞电离率。低温端由阈值指数压低，高温端在达到宽峰后
缓慢下降。He II 的较高阈值使其在低温端最慢。`[L/V]`

### (b) Constructed three-body inverse rates

曲线是 $\beta_{i}^{\rm DB}=C_{i}/S_{i}$。它们用于回收同一基态 Saha 极限；图题明确写成
constructed inverse rates，避免把它误认为独立测量或更完整的原子表。`[A-control/V]`

### (c) Collision + RR + three-body equilibrium

在固定 $10^{5}\ \mathrm{K}$ 下，低密度端 H 几乎全电离，He 主要为 He III；进入高密度后，
三体复合和 Saha 密度依赖推动布居向较低电离态移动，He II 在中间密度出现峰值。`[A/V]`

### (d) High-density LTE asymptote

蓝线是五个离子分数相对“碰撞--三体 Saha 控制”的最大绝对差，橙线是电子密度相对差。
两者随密度升高趋零，证明加入总辐射复合后仍连续回到高密度 LTE 极限。`[V]`

### (e) Fixed-state rate-network relaxation

从全中性 H/He 初态出发，H 在氦最慢时标的横轴上几乎瞬间达到 H II；氦则由 He I 经 He II
连续转向 He III。曲线由同一守恒矩阵指数产生，没有删除负点或重归一化。`[A-control/V]`

### (f) Prescribed ZO midplane timescale audit

氢与氦的局域松弛时间均远短于轨道周期，近心点附近由于中面更热、更密而更短。该面板是
规定中面状态的时标审计，不是轨道耦合 NLTE 解。`[A/V/O]`

## 9. 收敛图逐面解释

![Phase 7B4a 数值收敛](../outputs/phase7b4a_collisional_kinetics_convergence.png)

### (a) Charge-neutrality root convergence

电子密度误差随二分次数近指数下降，48 次已到双精度舍入区。52 次的零差没有绘到对数轴，
但仍保存在 CSV 和 JSON 中；代码没有用非零 floor 伪造点。`[V]`

### (b) Prescribed ZO background convergence

H 与 He 的完整轨道 $\log_{10}t_{\rm relax}$ 曲线相对 2048 点参考收敛；1024 点误差都低于
$1.6\times10^{-5}\ \mathrm{dex}$。这只验证源相位离散，不替代将来轨道时间推进器的时间步
收敛。`[V/O]`

## 10. 文件和复现

核心文件：

- `src/eccentric_tde_observer/atomic_kinetics.py`：碰撞率、三体详细平衡、稳态与率矩阵；
- `tests/test_atomic_kinetics.py`：参数、有效域、Saha、守恒、解析松弛和禁用修补测试；
- `scripts/phase7b4a_collisional_kinetics_controls.py`：本阶段证据生成脚本。

机器可读产物：

- `outputs/phase7b4a_collisional_rates.csv`；
- `outputs/phase7b4a_density_equilibrium.csv`；
- `outputs/phase7b4a_fixed_relaxation.csv`；
- `outputs/phase7b4a_zo_midplane_timescales.csv`；
- `outputs/phase7b4a_convergence.csv`；
- `outputs/phase7b4a_collisional_kinetics_report.json`。

复现命令：

```bash
cd /Users/shandike/Downloads/A_USTCer/8.3/eccentric_tde_observer
uv run python scripts/phase7b4a_collisional_kinetics_controls.py --output-dir outputs
uv run pytest -q
```

## 11. 阶段边界与下一步

本阶段已经回答：碰撞电离和一致逆率的代数、守恒、LTE 极限与固定背景松弛均成立；在当前
规定的 ZO 中面控制状态下，局域基态 H/He 率不是轨道尺度瓶颈。`[V]`

本阶段没有回答：表层辐射场是什么、温度如何由加热与冷却决定、激发态如何布居、连续谱
从哪个深度形成，以及速度梯度如何搬移频率。`[O]`

这一最小轨道推进现已由
[[eccentric_tde_observer/docs/phase7b4b_orbit_coupled_kinetics|Phase 7B4b]] 完成：相同的
基态 H/He 率已放回 Phase 7B1 周期背景，电荷中性的 $n_{\rm e}$ 被隐式自洽更新，并通过
解析非线性控制、周期稳定态、初值独立性和时间步收敛。来源明确、可关闭的规定辐射场也已由
[[eccentric_tde_observer/docs/phase7b4c_prescribed_radiation_kinetics|Phase 7B4c]] 接入并通过
零场与热详细平衡；[[eccentric_tde_observer/docs/phase7b4d_coupled_slab|Phase 7B4d]] 又在
固定控制板层上闭合 $J_{\nu}$--基态布居--opacity 固定点；
[[eccentric_tde_observer/docs/phase7b4e_continuum_emission|Phase 7B4e]] 已通过同截面基态
Milne 连续发射和固定温度能量门。下一步先求规定加热下的温度平衡，仍不应加入 Cloudy、
盘风或完整 NLTE 谱表。`[A/V/O]`
