# Phase 6：corrected ZO 曲面上的条件性谱线响应

上级导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/erratum_2022_correction|ZO 2022 Erratum 修正]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]

> [!important] 科学边界
> 本阶段输出的是 corrected ZO 几何、速度、投影、可见性和弱场频移共同决定的
> **条件性谱线响应**或**运动学线核**。Halpha 的 $6562.8\ \mathrm{\mathring A}$
> 只提供展示波长轴；结果不是 Halpha、Hbeta 或 He II 的绝对光度预言。`[A/V]`

## 1. 传递方程与 corrected 面积

观察者频率密度采用

$$
F_{\nu_{\rm obs}}^{\rm line}
=\frac{1}{D^2}\int_{\rm visible}
g^3 I_{\nu_{\rm em}}^{\rm line}
\left(\frac{\nu_{\rm obs}}{g},\mu_{\rm em}\right)
\,\mathrm dA_{\rm image}.
$$

其中 $g=\nu_{\rm obs}/\nu_{\rm em}$ 沿用 Phase 2 的弱场 Doppler、横向 Doppler、
引力红移和垂向呼吸速度；可见性沿用正反面判断与自遮挡求积。像平面面积
$\mathrm dA_{\rm image}$ 由 corrected ZO 曲面的 Cartesian 三角形投影得到，等价的源平面
测度是

$$
\mathrm dA_{\rm corr}
=a\,j(1-e\cos E)\,\mathrm da\,\mathrm dE.
$$

三种最小权重都采用局域各向同性线强度 `[A]`；发射角的 $\mu_{\rm em}$ 依赖只通过投影
像面积进入。本阶段没有假装已经知道真实原子线的角分布。

代码没有调用任何 pre-Erratum 面积。对于归一化 delta 线，频率变量变换再产生一个 $g$，
所以积分线能流为

$$
F_{\rm line}
=\frac{1}{D^2}\int_{\rm visible}
g^4\mathcal I_{\rm line}\,\mathrm dA_{\rm image}.
$$

`observer_line_profile` 同时构造 $F_{\nu}$ 与每 Å 的 $F_{\lambda}$，并逐 bin 验证

$$
\lambda F_{\lambda}=\nu F_{\nu}.
$$

实现位于 `src/eccentric_tde_observer/line_response.py`，独立于连续谱模块。`[V]`

## 2. 三种受控发射权重

| 名称                           | 定义                                                         | 允许的解释                 |
| ---------------------------- | ---------------------------------------------------------- | --------------------- |
| uniform `[A-control]`        | $\mathcal I_{\rm line}=\mathrm{constant}$                  | 解析环和纯运动学控制            |
| thermal power `[A-proxy]`    | $\mathcal I_{\rm line}\propto\sigma_{\rm SB}T_{\rm eff}^4$ | 若线响应跟随 ZO 局域耗散时的归一化线形 |
| fully ionized EM `[A-proxy]` | $\mathcal I_{\rm line}\propto\int n_{e} n_{i}\,\mathrm dz$ | 完全电离极限下的归一化线形         |

EM 代理使用既有归一化垂向剖面：若
$\rho=(\Sigma/H)f(z/H)$，则

$$
\int n_{e} n_{i}\,\mathrm dz
\propto
\frac{\Sigma^2}{H}\int f^2(\zeta)\,\mathrm d\zeta.
$$

这里没有复合系数、能级布居或线源函数，因而不比较三种权重的绝对线强度，也没有任意
$r^{-q}$ 发射率指数。真实复合系数接口留作 `[O]`，不能用 $T_{\rm eff}$ 伪造气体的 NLTE
状态。

## 3. 线形变量与分类

展示速度定义为

$$
v\simeq c\left(\frac{\lambda}{\lambda_{0}}-1\right),
\qquad
\lambda_{0}=6562.8\ \mathrm{\mathring A}.
$$

诊断包括 $\Delta v_{\rm peak}$、$F_{\rm red}/F_{\rm blue}$、质心、二阶线宽、偏度和

$$
D_{\rm trough}
=1-\frac{F_{\rm trough}}
{\min(F_{\rm red},F_{\rm blue})}.
$$

`[A-classification]` 只有红蓝两侧均存在局域峰、峰间距大于一个速度 bin、谷位于两峰之间，
且 $D_{\rm trough}\ge0.1$ 时才标为双峰。中央谷使用相邻三个 bin 的中位数，不允许单个坏
bin 决定分类。把阈值从 $0.05$、$0.10$ 提高到 $0.20$ 时，全部三种权重的 504 个方向中
双峰计数从 448、424 降到 320；因此二元标签不是文献定理，连续诊断才是正式结果。`[V]`

## 4. 解析与守恒验证

![圆环 arcsine 解析核与数值环](../outputs/phase6_ring_arcsine_validation.png)

**怎么看。** 黑线是有限速度 bin 对解析 arcsine 核的精确积分，橙线是一百万个等方位
样本的数值环。两端角峰重合，概率分布的 $L_{1}$ 差为 $9.64\times10^{-4}$。

**验证了什么。** `[V]` 倾斜 Newtonian 圆环回收

$$
P(v)=\frac{1}{\pi\sqrt{v_{\rm K}^2\sin^2i-v^2}},
\qquad |v|<v_{\rm K}\sin i.
$$

独立 face-on 环测试在关闭引力红移和垂向速度后只占一个 $v=0$ bin；uniform 权重、
$i=45^\circ$ 的完整传递测试中，$e=0$ 与 $e=10^{-5}$ 平均归一化差小于 $10^{-4}$，
没有偏心趋零时的跳变。

**不能证明什么。** arcsine 角峰是无局域展宽的积分奇点控制，只验证运动学和离散积分，
不能证明真实气体一定保持双峰。

全图谱中直接 $g^4$ 面积分与频率积分线能流的最大相对残差为
$5.6\times10^{-16}$；圆盘控制为 $1.7\times10^{-15}$，局域热展宽测试为
$3.3\times10^{-16}$。`[V]`

## 5. 圆盘与偏心盘对照

![圆盘随倾角的条件性线核](../outputs/phase6_circular_inclination_profiles.png)

**怎么看。** $e=0$ 的 uniform 控制在 face-on 时退化为窄核；倾角增加后，投影旋转速度
增大并形成对称双角峰。弱场正式曲线保留小的 relativistic beaming 和统一红移，因此不应
要求每个 bin 严格镜像相等。

**验证了什么。** `[V]` 圆盘本身就会产生双峰。$i=60^\circ$ 时改变名义近心点相位，
归一化谱的最大平均绝对变化只有 $2.03\times10^{-4}$，属于离散网格误差，而不是物理
进动信号。

**不能证明什么。** 双峰本身不能区分圆盘和偏心盘；区分信息必须来自不对称、质心、线翼
及其相位关联。

偏心盘的相位变化达到峰比 $0.199$--$4.23$、质心约
$\pm5700\ \mathrm{km\,s^{-1}}$，远高于圆盘控制的 $2.03\times10^{-4}$ 归一化谱差地板。`[V]`

![偏心盘的倾角和方位线核](../outputs/phase6_eccentric_orientation_profiles.png)

**怎么看。** 图使用 corrected 严格参考源 $(e,\mathcal V)=(0.6,0.01)$、thermal-power
代理和固定均匀高斯展宽 $\sigma_{v}/v_{\rm K}=0.02$，即约
$124\ \mathrm{km\,s^{-1}}$。行方向增加倾角，列方向改变 $\Phi$。倾角控制投影速度范围，
方位控制热近心区落在接近侧还是远离侧，因而红蓝峰高度、质心和线翼随相位交换。

**验证了什么。** `[V]` corrected ZO 裸偏心盘的几何和速度允许双峰；它还允许明显不对称
和质心漂移。$i=60^\circ$ 的 thermal-power 扫描中，红蓝峰比为 $0.199$--$4.23$，质心为
$-5663$--$5813\ \mathrm{km\,s^{-1}}$，峰间距为
$4600$--$10600\ \mathrm{km\,s^{-1}}$。

**不能证明什么。** 这些曲线逐条按峰值归一化，不能读出等效宽度或 Halpha 光度。

## 6. 发射权重与倾角依赖

![三种受控权重的线形对照](../outputs/phase6_weight_comparison.png)

**怎么看。** 同一 $i=60^\circ,\Phi=90^\circ$ 几何下，uniform 权重平均整个可见面，
thermal-power 强调 ZO 热耗散区，EM 强调高密度、较小尺度高度的区域。三条曲线均双峰，
但峰高、谷深和线翼显著不同。

**验证了什么。** `[V]` 在 168 个 $(i,\Phi)$ 方向中，uniform、thermal-power 和 EM
分别有 107、162 和 155 个通过 $D_{\rm trough}\ge0.1$。双峰不是只存在于某一个代理，
但其稳定性强烈依赖未闭合的线发射权重。

**不能证明什么。** 三种代理的归一化不同，不能比较绝对强度；不能挑选峰形最漂亮的一条
作为真实 Halpha 预言。

按倾角分解后，thermal-power 在 $i=30^\circ$ 及 $i\ge60^\circ$ 的 24 个相位全部双峰；
EM 在 $i=60^\circ$ 全部双峰，在 $70^\circ$ 和 $75^\circ$ 各有 23/24；uniform 在
$15^\circ$--$75^\circ$ 有 15--21/24 个相位双峰。$i=0$ 的 thermal-power 和 EM 也可能被
分类器识别为双峰，这是引力/横向红移、垂向呼吸速度与径向权重共同产生的多分量结构，
不能把它叫作旋转双角峰。因而“明显旋转双峰”的稳健范围是中高倾角，约
$i\gtrsim30^\circ$，且必须同时报告权重与相位。`[A/V]`

## 7. 展宽与双峰合并

![局域展宽下的双峰合并](../outputs/phase6_broadening_merger.png)

**怎么看。** 固定 $(e,\mathcal V,i,\Phi)=(0.6,0.01,60^\circ,90^\circ)$ 和
thermal-power 代理，在观察者速度空间施加均匀高斯卷积，并从 delta 数值核连续增加
$\sigma_{v}/v_{\rm K}$；其中 $0.02$ 是 atlas、诊断图和动态谱的正式工作点。角峰逐渐变圆，中央谷
逐渐填平。这条扫描与逐面元、位置相关的 $T_{\rm gas}=T_{\rm eff}$ 氢热展宽是两种不同实现。

**验证了什么。** `[V]` 在采样点 $\sigma_{v}/v_{\rm K}=0.3$ 仍为双峰，$0.5$ 已合并；当前只能把
合并尺度夹在 $0.3$ 与 $0.5$ 之间，不能声称已经求得精确临界值。若工作假设
$T_{\rm gas}=T_{\rm eff}$，氢的一维热宽为 $8.2$--$17.9\ \mathrm{km\,s^{-1}}$，该方向仍
明显双峰。逐面元热宽先定义在发射系，再按 $\sigma_{v,\rm obs}=\sigma_{v,\rm em}/g$
变换到展示速度轴；常数 $g$ 解析测试已回收该比例。

**不能证明什么。** $T_{\rm gas}=T_{\rm eff}$ 是 `[A]`，不是气体热平衡解；扫描不是对数据
拟合，也没有真实仪器线扩散函数。

## 8. 倾角、相位和进动诊断

![线诊断随倾角和相位的二维图](../outputs/phase6_line_diagnostic_maps.png)

**怎么看。** 四幅图依次给出 thermal-power 的峰间距、红蓝峰比、质心和谷深。沿倾角
方向主要扩大速度尺度，沿相位方向则产生强烈的符号和峰强交换。

**验证了什么。** `[V]` 近心区从接近侧转到远离侧时，红蓝峰比跨过 1，质心跨过 0；
峰间距和谷深也随相位变化。低倾角或浅谷处的空白是诊断未通过，而不是删除失败点。

**不能证明什么。** 二维图是归一化响应图谱，不包含进动周期的绝对天数，也不能替代
连续诊断 CSV。

![一个进动周期的动态线核](../outputs/phase6_dynamic_spectrum.png)

**怎么看。** 固定 $i=60^\circ$，纵轴从 $\Phi=0^\circ$ 到 $345^\circ$。亮脊在红蓝两侧
周期性交换，整体亮度已经逐相位归一化，因此颜色只编码线形。

**验证了什么。** `[V]` 进动可以造成峰强反转、质心漂移和峰间距变化；在某些倾角和权重
下，相位扫描还会跨过当前单峰/双峰分类边界。这个选定的 $i=60^\circ$ thermal-power
序列本身 24/24 都保持双峰，不能把其他方向的转换误画到它上面。

**不能证明什么。** 动态图的纵轴不是观测时间；绝对 $P_{\rm prec}$ 仍未闭合。

## 9. 连续谱并列与边界案例

![连续谱与归一化线核并列](../outputs/phase6_continuum_and_line_kernel.png)

**怎么看。** 左图是相同源和观察方向的条件性裸盘连续谱，右图是独立归一化的运动学线核。
两者分面显示，右图明确标记无等效宽度。

**验证了什么。** `[V]` 线模块复用了同一 corrected 几何、可见性和弱场频移，而没有把线
逻辑塞进连续谱模块，也没有为线核任意指定绝对强度。

**不能证明什么。** 这不是连续谱上叠加的可观测 Halpha，也不能从左右面板高度推导线连续
谱比。corrected 有效域边界源 $(e,\mathcal V)=(0.65,0.01)$ 在
$i=60^\circ,\Phi=90^\circ$ 仍为双峰，峰间距约
$10500\ \mathrm{km\,s^{-1}}$、红蓝峰比 $0.530$；它只作为边界敏感性案例，没有替换
Phase 4 的全部结果。

## 10. 收敛与实际误差

| 审计 | $\Delta v_{\rm peak}$ | $F_{\rm red}/F_{\rm blue}$ | $v_{\rm centroid}$ |
|---|---:|---:|---:|
| 源网格 $33\times512\to65\times1024$ | $0$ | $4.10\times10^{-3}$ | $1.94\times10^{-4}$ |
| 速度网格 $1601\to3201$ | $5.08\times10^{-3}$ | $1.43\times10^{-2}$ | $2.59\times10^{-5}$ |

表中相对变化定义为 $|x_{\rm coarse}/x_{\rm fine}-1|$，以细网格结果为分母。峰间距和红蓝
峰比没有达到优先目标 $10^{-3}$；实际限制分别约为 $0.5\%$ 和 $1.4\%$。
质心达到目标。自适应深度 2、4、6 的 $i=75^\circ$ 控制给出完全相同的诊断和可见/无遮挡
面积比 1；这是因为严格参考源在这组观察者网格中没有自遮挡边界，而不是因为删除了遮挡
点。独立的双层方块解析部分遮挡夹具给出蓝侧 $g^4$ 能流分数 $0.3731155$；自适应深度
1、3、5、7 的绝对误差从 $7.27\times10^{-2}$ 降至 $6.91\times10^{-4}$，确认线能流会跨
真实遮挡边界收敛。展宽核、delta 极限和速度网格已分别审计；峰高对 bin 和卷积宽度比质心
更敏感。`[V]`

## 11. 八个科学问题的回答

1. **corrected ZO 裸偏心盘允许双峰吗？** 允许。三种受控权重都存在大量双峰方向。`[V]`
2. **哪些倾角明显？** 中高倾角最稳健，约 $i\gtrsim30^\circ$；具体相位覆盖依赖权重。`[A/V]`
3. **哪些方位明显不对称？** 当热近心区主要落在接近侧或远离侧时最强；在本相位约定下，
   $i=60^\circ$ 扫描覆盖红蓝峰比 $0.199$--$4.23$。应引用连续图谱而非把单一角度普适化。`[V]`
4. **进动会做什么？** 可造成峰强反转、质心漂移、峰间距变化；在部分倾角/权重下会跨越
   单峰/双峰分类，但不是每条相位序列都会转换。`[V]`
5. **是否依赖单一权重？** 不依赖单一权重才“允许”双峰，但双峰相位覆盖、峰比和质心对
   权重高度敏感。`[V/O]`
6. **多大展宽下消失？** 选定控制在 $0.3<\sigma_{v}/v_{\rm K}<0.5$ 的已采样区间合并；临界值
   尚未细化，也不是普适常数。`[V/O]`
7. **圆盘也会双峰吗？** 会；倾斜旋转圆盘自然产生双角峰。`[L/V]`
8. **什么更能区分偏心盘？** 红蓝峰不对称、质心、非对称线翼，以及它们与近心点方位和
   进动相位的关联变化，比“双峰”这个标签更有区分力。`[V/O]`

> 双峰本身不能证明偏心性；圆盘旋转也可以产生双峰。更有区分力的是红蓝峰不对称、质心、
> 线翼以及它们随近心点方位和进动相位的关联变化。

## 12. 尚未闭合的线物理 `[O]`

当前没有 NLTE 能级布居、线自吸收、光致电离平衡、电子散射重分布、时间依赖气体温度、
真实仪器线扩散函数，也没有加入本阶段禁止的再处理层或自由盘风。因此：

> 当前 ZO 几何允许双峰，但双峰是否成为真实观测预言取决于尚未闭合的线发射和线转移物理。

复现命令为：

```bash
uv run python scripts/phase6_line_response.py --output-dir outputs
uv run pytest -q tests/test_line_response.py tests/test_erratum.py
```

机器可读证据位于 `outputs/phase6_line_response_report.json`、
`outputs/phase6_line_diagnostics.csv`、`outputs/phase6_broadening_sensitivity.csv`、
`outputs/phase6_convergence.csv` 和 `outputs/phase6_dynamic_spectrum.csv`。
