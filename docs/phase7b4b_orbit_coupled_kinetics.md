# Phase 7B4b：电荷自洽的轨道耦合 H/He 基态动力学

> [!abstract] 阶段结论
> `[V]` 本阶段把 Phase 7B4a 已验证的 H I、He I、He II 碰撞电离、总辐射复合和三体
> 详细平衡率放回规定 ZO 完整轨道，在每个隐式时间步重新满足电荷中性，并得到周期稳定态。
> `[A-control]` 当前明确关闭外部光致电离，温度仍是灰 Eddington 中面输入；因此结果是
> “无辐照基态动力学控制”，不是物理中面或表层电离史。
> `[O]` 动态解几乎跟随瞬时碰撞稳态，但该稳态与 LTE 的氦布居最多相差 0.99909；这直接
> 说明下一缺口是辐射--布居耦合，而不是继续减小当前时间步或把控制曲线输出成谱。

导航：[[eccentric_tde_observer/README|项目 README]] ·
[[eccentric_tde_observer/docs/phase7b4a_collisional_kinetics|Phase 7B4a 碰撞动力学]] ·
[[eccentric_tde_observer/docs/phase7b_periodic_column|Phase 7B1 周期背景]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

---

## 1. 本阶段回答什么

Phase 7B4a 只在固定局域状态下验证了率矩阵。Phase 7B4b 进一步回答：当 ZO 中面密度和
温度随真实开普勒轨道时间变化时，H/He 布居能否形成守恒周期稳定态，布居相对瞬时稳态有
多大滞后，以及结果是否依赖正电子密度初值。`[A/V]`

本阶段没有计算连续谱。关闭光致电离率

$$
\Gamma_{\rm H\,\rm I}
=\Gamma_{\rm He\,\rm I}
=\Gamma_{\rm He\,\rm II}=0
$$

是一个刻意的控制，不是“盘内没有辐射”的物理结论。它隔离碰撞动力学和刚性时间推进，
同时让缺失辐射造成的偏差可以被直接量化。`[A-control/O]`

## 2. 为什么使用离子分数而不是直接推进数密度

沿拉格朗日柱，ZO 呼吸会改变总核数密度。设氢和氦的归一化布居分别为

$$
\boldsymbol x_{\rm H}=(x_{\rm H\,\rm I},x_{\rm H\,\rm II}),
$$

$$
\boldsymbol x_{\rm He}=(x_{\rm He\,\rm I},x_{\rm He\,\rm II},x_{\rm He\,\rm III}),
$$

并要求

$$
x_{\rm H\,\rm I}+x_{\rm H\,\rm II}=1,
$$

$$
x_{\rm He\,\rm I}+x_{\rm He\,\rm II}+x_{\rm He\,\rm III}=1.
$$

共同压缩项对同一元素的总数密度和各电离态数密度相同，因此在分数方程中相消；密度变化
仍通过电子碰撞和复合率进入。电子密度每步由

$$
n_{\rm e}
=n_{\rm H}x_{\rm H\,\rm II}
+n_{\rm He}
\left(x_{\rm He\,\rm II}+2x_{\rm He\,\rm III}\right)
$$

重新求出，不使用上一时刻的固定电子密度。`[L/A/V]`

## 3. 正性保持的电荷自洽隐式步

当前率很快：Phase 7B4a 已发现最慢 He 局域时标最高也只有轨道周期的
$6.62\times10^{-8}$。显式步若按轨道网格推进会严重不稳定，因此采用后向 Euler：

$$
\boldsymbol x^{k+1}-\boldsymbol x^{k}
=\Delta t\,
\mathbf R\!\left(n_{\rm e}^{k+1}\right)
\boldsymbol x^{k+1}.
$$

给定一个试探 $n_{\rm e}^{k+1}$ 后，H 与 He 方程都是线性的。氢的闭式隐式更新为

$$
x_{\rm H\,\rm I}^{k+1}
=\frac{x_{\rm H\,\rm I}^{k}+\Delta t\,d_{\rm H}}
{1+\Delta t(u_{\rm H}+d_{\rm H})},
$$

$$
x_{\rm H\,\rm II}^{k+1}
=\frac{x_{\rm H\,\rm II}^{k}+\Delta t\,u_{\rm H}}
{1+\Delta t(u_{\rm H}+d_{\rm H})}.
$$

氦利用总数守恒消去一个分量，只解二维隐式系统。这样避开三态守恒矩阵的零本征模在
$\Delta t\,R\gg1$ 时造成的病态三维线性系统；这不是事后重归一化。`[A/V]`

随后在严格物理区间

$$
0\le n_{\rm e}^{k+1}\le n_{\rm H}^{k+1}+2n_{\rm He}^{k+1}
$$

内对电荷残差做 64 次二分。该区间来自电荷上限，不是任意数值裁剪。生产解的最大相对
电荷残差为 $4.26\times10^{-16}$，H/He 粒子数最大残差为
$3.33\times10^{-16}$，最小离子分数仍为正的 $2.04\times10^{-6}$。`[V]`

## 4. 全中性分支为什么必须保留

当前控制只有电子碰撞电离，没有光子电离。若初态严格满足

$$
n_{\rm e}=0,
$$

则碰撞电离体积率 $n_{i}n_{\rm e}C_{i}$ 也严格为零，全中性状态是一个动力学吸收分支。
代码保留该分支，不用任意电子 floor 强迫电离。`[L/V]`

生产轨道从相位零的正电子密度瞬时碰撞稳态开始，并另用
$\boldsymbol x_{\rm H}=(0.8,0.2)$、
$\boldsymbol x_{\rm He}=(0.6,0.3,0.1)$ 做独立正布居初值。两种正初值收敛后的完整周期曲线
最大差为 $4.44\times10^{-16}$；前者一周收敛，后者两周收敛。可以说“正电子密度分支
遗忘初值”，不能说“严格全中性分支会自行电离”。`[A-control/V]`

## 5. ZO 周期背景和瞬时比较解

沿径向索引 8 使用 Phase 7B1 的开普勒时间轴。中面密度与温度仍取

$$
\rho_{0}(E)=\frac{\Sigma(E)}{H(E)}f(0),
$$

$$
T_{0}^{4}(E)=\frac{3}{4}T_{\rm eff}^{4}(E)
\left[\frac{\kappa_{\rm gray}\Sigma(E)}{2}+\frac{2}{3}\right].
$$

每个相位另计算两个静态参照：

1. `instantaneous kinetic steady state`：与动态解使用完全相同的无辐照碰撞电离、总辐射
   复合和三体详细平衡率；
2. `LTE Saha control`：同一 $\rho_{0},T_{0}$ 下的基态 Saha 解。

第一项量化有限率造成的动力学滞后；第二项量化当前无辐照反应集相对 LTE 的物理闭合缺口。
这两个差不能混为同一种“误差”。`[A/V]`

## 6. 周期稳定态结果

1024 相位点生产解的范围为：

| 分数 | 最小值 | 最大值 |
|---|---:|---:|
| H II | 0.9991576 | 0.9999911 |
| He I | $2.0352\times10^{-6}$ | 0.0689975 |
| He II | 0.0255785 | 0.9855425 |
| He III | $8.2353\times10^{-5}$ | 0.9744195 |

这些范围只能标为无辐照基态控制。它们显示近心点高温阶段 He III 占优，远离近心点后 He II
占优，并出现少量 He I；不能把这种变化直接当作真实轨道电离史。`[A-control/V/O]`

动态解相对瞬时碰撞稳态的最大离子分数差为

$$
\max_{\rm E,i}\left|x_{i}^{\rm dyn}-x_{i}^{\rm inst}\right|
=3.57\times10^{-7},
$$

电子密度最大相对滞后为 $3.16\times10^{-8}$。这验证在当前中面控制上，有限碰撞时标的
动态滞后很小。`[V]`

相反，瞬时碰撞稳态相对 LTE 的最大离子分数差为

$$
\max_{\rm E,i}\left|x_{i}^{\rm inst}-x_{i}^{\rm LTE}\right|
=0.999090,
$$

电子密度最大相对差为 0.08963。差异主要来自氦：LTE 控制几乎保持 He III，而无辐照反应集
在大部分轨道给出 He II。原因是总辐射复合已经加入，但其逆光致过程被本控制刻意关闭；
ZO 密度又远低于三体复合主导区，故该反应集不应恢复 LTE。`[L/A/V]`

这不是数值失败，恰好是本阶段最重要的科学诊断：下一步必须加入有来源的辐射场并测试
$\Gamma_{i}$--布居耦合，不能继续把无辐照结果修饰成谱。`[O]`

## 7. 非线性解析氢控制

为独立验证“电子密度随布居更新”，构造只有氢、光致电离率 $\Gamma$ 和辐射复合率
$\alpha$ 的常背景控制。令 $x=x_{\rm H\,\rm II}$，由 $n_{\rm e}=n_{\rm H}x$ 得

$$
\frac{\mathrm dx}{\mathrm dt}
=\Gamma(1-x)-n_{\rm H}\alpha x^{2}.
$$

它是 Riccati 方程。定义

$$
r_{\pm}
=\frac{-\Gamma\pm
\sqrt{\Gamma^{2}+4n_{\rm H}\alpha\Gamma}}
{2n_{\rm H}\alpha},
$$

$$
q(t)=
\frac{x_{0}-r_{+}}{x_{0}-r_{-}}
\exp\!\left[-n_{\rm H}\alpha(r_{+}-r_{-})t\right],
$$

则解析解为

$$
x(t)=\frac{r_{+}-q(t)r_{-}}{1-q(t)}.
$$

后向 Euler 的末点误差从 32 步的 $5.50\times10^{-4}$ 连续降到 1024 步的
$1.52\times10^{-5}$；后四档每次加倍步数，误差比趋近 2，符合一阶方法。这里选择
L-stable 的一阶隐式步是为了抑制极刚性快模，不假装它具有二阶精度。`[A-control/V]`

## 8. 两条轨道收敛轴

### 8.1 固定源节点内的时间细分

固定 256 个 ZO 源节点，在每个源区间把正温度和核数密度按轨道时间线性插值，并将时间步
细分为 1、2、4、8 份；16 份、共 4096 点作为参考。2048 点相对参考的最大离子分数绝对
误差为 $1.10\times10^{-9}$。`[A/V]`

### 8.2 ZO 源相位网格

独立重建 256、512、1024 和 2048 相位点的 ZO 源与完整动力学解，以 2048 点为参考做周期
插值。1024 点的四条离子分数曲线中，最大均方根误差为
$1.09\times10^{-5}$。256、512、1024 点误差约按四倍缩小，当前总误差主要由源相位
离散而不是隐式动力学步长控制。`[V]`

## 9. 主图逐面解释

![Phase 7B4b 轨道耦合 H/He 基态动力学](../outputs/phase7b4b_orbit_coupled_kinetics.png)

### (a) Prescribed ZO midplane background

红线是灰 Eddington 中面温度，蓝线是 $n=3$ 垂向剖面的中面密度。两者在近心点附近迅速
升高，并严格使用开普勒时间相位；它们仍是规定背景，不由本阶段率方程反馈。`[A/V]`

### (b) Orbit-coupled hydrogen response

蓝线是动态 H II，橙色虚线是瞬时无辐照碰撞稳态，绿色点线是 LTE Saha 控制。动态与瞬时
曲线视觉重合，但两者均略低于几乎完全电离的 LTE 控制。`[A/V]`

### (c) Orbit-coupled helium response

实线是动态 He I、He II、He III，虚线是对应瞬时碰撞稳态。近心点附近 He III 快速占优，
轨道大部分时间则以 He II 为主；实线与虚线视觉重合说明有限率滞后很小。这里没有把 LTE
曲线叠入该面板，以免九条曲线遮盖；LTE 缺口集中显示在面板 (d)。`[A-control/V]`

### (d) Numerical lag versus missing-radiation gap

蓝线是动态解相对瞬时碰撞稳态的最大分数差，最高只有 $3.57\times10^{-7}$；橙线是瞬时
碰撞稳态相对 LTE 的最大差，在大部分轨道接近 1。两者相差六到九个数量级，明确证明当前
主导不确定性不是时间推进误差，而是被刻意关闭的辐射逆过程。`[V/O]`

## 10. 收敛图逐面解释

![Phase 7B4b 数值收敛](../outputs/phase7b4b_orbit_coupled_kinetics_convergence.png)

### (a) Analytic nonlinear H control

电子密度随 H II 分数变化的 Riccati 控制表现为稳定一阶收敛，验证电荷自洽隐式步没有退化
成固定电子密度近似。`[A-control/V]`

### (b) Orbit time-step convergence

固定源节点内继续细分时间步时，误差降到 $10^{-9}$；因此当前生产结果不受后向 Euler
时间步误差主导。`[V]`

### (c) ZO source-grid convergence

重新加密 ZO 源相位后误差按近二阶下降，1024 点相对 2048 点为
$1.09\times10^{-5}$。这是生产轨道的主导离散误差。`[V]`

## 11. 文件、测试与复现

核心文件：

- `src/eccentric_tde_observer/orbital_kinetics.py`：电荷自洽隐式步和周期 H/He 求解器；
- `tests/test_orbital_kinetics.py`：解析 Riccati、固定点、全中性分支、初值独立性和拒绝测试；
- `scripts/phase7b4b_orbit_coupled_kinetics.py`：本阶段证据脚本。

机器可读产物：

- `outputs/phase7b4b_periodic_kinetics.csv`：逐轨道相位动态、瞬时碰撞稳态和 LTE 布居；
- `outputs/phase7b4b_convergence.csv`：解析、时间细分和源相位三条收敛轴；
- `outputs/phase7b4b_orbit_coupled_kinetics_report.json`：假设、残差、范围和阶段边界。
- `outputs/phase7b4b_orbit_coupled_kinetics.png`：规定背景、周期布居与缺失辐射诊断；
- `outputs/phase7b4b_orbit_coupled_kinetics_convergence.png`：三条独立收敛轴。

复现命令：

```bash
cd /Users/shandike/Downloads/A_USTCer/8.3/eccentric_tde_observer
uv run python scripts/phase7b4b_orbit_coupled_kinetics.py --output-dir outputs
uv run pytest -q
```

`tests/test_orbital_kinetics.py` 的 7 项专项测试和全项目 `242 passed` 均通过；Markdown 数学
规范检查无待修改文件。`[V]`

## 12. 当前允许与禁止的结论

> `[V]` 可以说：电荷自洽、正性保持的 H/He 基态率方程已经在规定 ZO 轨道上形成周期
> 稳定态；解析非线性氢控制、正初值遗忘、粒子数、电荷和三条收敛轴均通过。

> `[A/V]` 可以说：在灰温度无辐照中面控制中，动态布居几乎跟随瞬时碰撞稳态。

> `[O]` 不能说：该轨道曲线是真实盘内电离史、NLTE 大气或可用于输出连续谱。瞬时碰撞
> 稳态与 LTE 的氦分数差接近 1，已经证明关闭辐射场会 materially 改变结果。

这一步现已由
[[eccentric_tde_observer/docs/phase7b4c_prescribed_radiation_kinetics|Phase 7B4c]] 完成：
来源明确、可关闭的规定 Planck 场已使 $\Gamma_{i}(t)$ 进入同一周期求解器，并通过零场和
热详细平衡极限；[[eccentric_tde_observer/docs/phase7b4d_coupled_slab|Phase 7B4d]] 又在固定
控制板层上联立 Phase 7B2 的 $J_{\nu}$、基态布居和 opacity；
[[eccentric_tde_observer/docs/phase7b4e_continuum_emission|Phase 7B4e]] 再完成同截面基态 Milne
发射和固定温度能量账本。下一步先求规定加热下的温度平衡，仍不加入任意 Cloudy 光源、
盘风、激发态伪率或绝对谱归一化。`[A/V/O]`
