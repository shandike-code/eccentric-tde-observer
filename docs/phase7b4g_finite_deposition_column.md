# Phase 7B4g：有限沉积柱质量的静态大气门

## 1. 本阶段结论

> `[V]` 保持 Phase 7B1 近心点单面耗散不变时，固定密度有限柱在声明温度域内出现内部、
> 稳定的静态根。因此当前证据**不支持立即进入周期动态 NLTE 柱**。

> `[A-classification/V]` 参考 $3\ {\rm g\,cm^{-2}}$ 柱的顶部连续谱与局域 ZO 黑体在归一化
> 谱形、ionizing fraction 和 $\nu F_{\nu}$ 峰位置上均有大差异；路线门因此选择先建立有限
> 静力大气表，而不是先做 UVOT 仪器层。

> `[O]` 当前结果仍不是 Phase 4 的替换表。固定密度、双真空边界、顶帽耗散、基态 H/He、
> 线完全逃逸上边界和无 Compton 频率重分布都必须在替换观察者连续谱前升级。

关联文档：

- [[eccentric_tde_observer/docs/phase7b4f_temperature_balance|Phase 7B4f 规定加热温度平衡]]；
- [[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]；
- [[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]。

## 2. 为什么需要这一门

Phase 7B4f 把完整近心点通量沉积在 $10^{-4}\ {\rm g\,cm^{-2}}$ 控制薄层时没有静态根，
但实际 ZO 单边柱质量为 $585.586\ {\rm g\,cm^{-2}}$。该失败不能区分以下可能：

1. 耗散柱确实过浅；
2. 缺失 Compton 能量交换；
3. 缺失激发态线冷却；
4. 静态近似整体失败。

Phase 7B4g 保持总单面通量 $F_{\rm ZO}=1.0060\times10^{14}\
{\rm erg\,s^{-1}\,cm^{-2}}$ 不变，只扫描沉积质量柱并逐项打开最小附加能量过程。

## 3. 物理定义和边界

### 3.1 有限顶帽沉积柱

固定密度控制仍采用

$$
\rho=10^{-10}\ {\rm g\,cm^{-3}}.
$$

从受照表面向内定义质量坐标

$$
m(z)=\rho(z-z_{\rm top}).
$$

在 $0\leq m<m_{\rm dep}$ 内按单位质量柱均匀沉积：

$$
q_{\rm dep}(m)
=
\rho\frac{F_{\rm ZO}}{m_{\rm dep}}.
$$

扫描中总板层柱质量等于 $m_{\rm dep}$。跨越沉积边界的离散单元按解析重叠比例积分，直接满足

$$
\int q_{\rm dep}\,{\rm d}z=F_{\rm ZO},
$$

没有事后重归一化。`[A-deposition/V]`

板层两面均使用真空出射边界。因此它回答“有限静态柱能否承载该耗散”，不等同于从盘面到
中面的对称半大气。`[A/O]`

### 3.2 Compton 能量交换

在 $h\nu\ll m_{\rm e}c^{2}$ 的 Thomson 一阶极限，正号定义为气体受热：

$$
q_{\rm C}
=
\frac{n_{\rm e}\sigma_{\rm T}}{m_{\rm e}c^{2}}
4\pi\int J_{\nu}
\left(h\nu-4k_{\rm B}T\right){\rm d}\nu.
$$

代码在每次温度、布居和转移重算后使用新的 $J_{\nu}$，没有冻结辐射背景。当前最高光子能量
满足 $h\nu_{\max}/(m_{\rm e}c^{2})=9.78\times10^{-3}$。公式可参见
[Park et al. 的 Compton heating 定义](https://academic.oup.com/mnras/article/445/3/2325/1049535)。
`[L/V]`

这里仍没有 Kompaneets 频率重分布；Compton 只进入气体能量账本。`[A/O]`

### 3.3 激发态线冷却边界

完整多能级 NLTE 尚未实现。本阶段只比较：

- `disabled`：没有净线冷却；
- `full_escape`：每次 H I 或 He II 碰撞激发产生的线能量全部逃逸。

全部逃逸上边界采用

$$
\Lambda_{{\rm H\,I}}
=
n_{\rm e}n_{{\rm H\,I}}
\frac{7.5\times10^{-19}
\exp(-118348/T)}{1+\sqrt{T/10^{5}}},
$$

以及

$$
\Lambda_{{\rm He\,II}}
=
n_{\rm e}n_{{\rm He\,II}}
\frac{5.54\times10^{-17}T^{-0.397}
\exp(-473638/T)}{1+\sqrt{T/10^{5}}},
$$

单位均为 ${\rm erg\,s^{-1}\,cm^{-3}}$。这些常用拟合及其来源见
[Rosdahl et al. 2013 的冷却率附录](https://academic.oup.com/mnras/article/436/3/2188/1247446)。
`[L]`

该上边界没有激发态布居、碰撞退激、线光深、逃逸概率或能量再分配；它不能产生可信的
H$\alpha$、Ly$\alpha$ 或 He II 光度。`[A-upper/O]`

### 3.4 总能量方程

逐深度求解

$$
q_{\rm dep}
+q_{\rm cont}
+q_{\rm C}
-\Lambda_{\rm line}
=0,
$$

其中 $q_{\rm cont}$ 是 Phase 7B4e 的基态 bound--free、free--free 连续净交换。四套控制为：

1. 连续过程；
2. 连续过程加 Compton；
3. 连续过程加线完全逃逸上边界；
4. 三者同时打开。

## 4. 解析和代码验证

- 有限顶帽沉积跨越部分网格单元时仍逐浮点精度回收输入通量；`[V]`
- Compton 项在离散辐射 Compton 温度处回到零，温度上下两侧符号相反；`[V]`
- H I 与 He II 线项分别随对应基态布居消失；`[V]`
- Compton 和线边界可以独立关闭；`[V]`
- 温度求解器的局域、全局能量残差包含附加项；`[V]`
- 代码没有 `nan_to_num`、无物理理由的 `clip`、任意 floor、失败点删除或事后归一化。`[V]`

本阶段新增 7 项有限柱附加能量专项测试；全项目现场回归为 `279 passed`。`[V]`

## 5. 有限柱根拓扑

低成本拓扑网格在 $2\times10^{5}$--$3\times10^{6}\ {\rm K}$ 内得到：

| $m_{\rm dep}$ [$\rm g\,cm^{-2}$] | 静态根温度 [K] | 声明温度域状态 |
|---:|---:|---|
| $0.30$--$1.25$ | 无内部根 | 到温度上界仍为净加热 |
| $1.50$ | $2.122\times10^{6}$ | 唯一稳定根 |
| $2.00$ | $1.116\times10^{6}$ | 唯一稳定根 |
| $2.50$ | $6.843\times10^{5}$ | 唯一稳定根 |
| $3.00$ | $4.696\times10^{5}$ | 唯一稳定根 |
| $4.00$ | $2.784\times10^{5}$ | 唯一稳定根 |
| $5.00$ | 无内部根 | 从温度下界起已为净冷却，根低于声明域 |

所有 $143$ 个正式拓扑采样点均得到有效辐射--布居固定点。最低**采样**稳定柱是
$1.5\ {\rm g\,cm^{-2}}$，但这不是对临界柱质量的连续拟合，也不能把根强行外推到相邻温度
域外。`[V]`

参考 $3\ {\rm g\,cm^{-2}}$ 只占实际单边柱的 $0.5123\%$，其 Thomson 光深约为 1；
它是表面有限柱门，不是整柱平均。`[A/V]`

## 6. 微物理控制与逐深度解

在较高分辨率参考网格上：

| 控制 | 等温稳定根 [K] | 附加能量/$F_{\rm ZO}$ |
|---|---:|---:|
| 连续过程 | $4.8953\times10^{5}$ | $0$ |
| 加 Compton | $4.8918\times10^{5}$ | $-3.64\times10^{-4}$ |
| 加线完全逃逸 | $4.5883\times10^{5}$ | $-3.22\times10^{-2}$ |
| 两者同时 | $4.5850\times10^{5}$ | $-3.25\times10^{-2}$ |

负号表示对气体冷却。Compton 在高温根上只是 $\sim3\times10^{-4}$ 级冷却；线完全逃逸
上边界把根温度降低约 $6.3\%$，但没有改变根数或稳定性。`[V]`

两项同时打开的逐深度解为

$$
T=4.542\times10^{5}\text{--}4.629\times10^{5}\ {\rm K}.
$$

最大局域能量相对残差为 $1.15\times10^{-9}$，全层残差为 $9.88\times10^{-10}$；最大热
增长率为 $-0.167\ {\rm s^{-1}}$，因此该离散根稳定。`[V]`

只计单原子平动内能的热时间为 $2.73\ {\rm s}$，是轨道周期的
$6.55\times10^{-7}$。电离和激发内能尚未计入，所以这是工作时标；但它与轨道时间相差六个
数量级，当前参考根不触发动态门。`[A-timescale/V]`

## 7. 连续谱路线门

双真空边界下，顶部有限能段连续通量是局域 ZO 黑体的 $0.482$。该数主要反映能量从板层
两面逃逸，不能被解释为盘面本征光度减少一半。路线判断只使用归一化谱形和无量纲能量位置。
`[A/V]`

连续谱对照得到：

- 归一化谱形 $L_{1}$ 距离：$1.239$；
- 氢离化阈值以上能流比例：有限柱 $0.757$，局域黑体 $0.351$；
- $\nu F_{\nu}$ 峰：$43.97\ {\rm eV}$ 对 $11.37\ {\rm eV}$；
- 峰能量比：$3.87$。

预先声明的 `[A-classification]` 要求谱形距离大于 $0.2$ 且峰能量比大于 2；把谱形阈值改为
$0.1$ 或 $0.3$ 均不改变“大差异”分类。`[A-classification/V]`

该结论不是“已经得到物理 X-ray 谱”。当前顶面谱只有 H/He 基态连续过程；线完全逃逸损失
没有作为线光子重新放回输出谱，Compton 也没有做频率重分布。`[O]`

## 8. 图件逐一解释

![Phase 7B4g 有限沉积柱](../outputs/phase7b4g_finite_column.png)

### (a) Finite-column root topology

浅柱在整个温度域保持净加热；加深沉积柱后连续冷却增强，$1.5$--$4\ {\rm g\,cm^{-2}}$
依次穿过零点。$5\ {\rm g\,cm^{-2}}$ 曲线从下界起已在零线下方，表示根低于本阶段声明域，
不是“静态无解”。`[V]`

### (b) Process controls at 3 g cm$^{-2}$

仅 Compton 曲线几乎覆盖连续基线；线完全逃逸曲线向下移动约 $3\%$。两类附加过程都没有
制造新根或消灭原有根。`[V]`

### (c) Depth-resolved static roots

连续基线几乎等温；线完全逃逸上边界使温度整体下降，并产生约 $2\%$ 的浅层--深层变化。
另一组初温回到同一剖面，变化不是初值分支。`[V]`

### (d) Local energy ledger

连续交换承担约 $96.75\%$ 的耗散，线完全逃逸上边界承担约 $3.22\%$，Compton 约为
$0.033\%$。各深度总和回到零。`[V]`

![Phase 7B4g 收敛与谱差](../outputs/phase7b4g_convergence.png)

### (a) Profile refinement

温度剖面在频率 $65$ 到 $129$ 基点时变化 $9.95\times10^{-3}$；深度 $4$ 到 8 为
$5.41\times10^{-4}$；角度 $4$ 到 8 为 $2.34\times10^{-3}$。初温改变后的差为
$2.46\times10^{-9}$。频率仍是主误差轴。`[V]`

### (b) Microphysics boundary sensitivity

四根均稳定；线边界的温度影响远大于当前 Compton 一阶能量项，但仍小于有限柱根与 ZO
$T_{\rm eff}$ 的数量级差异。`[V]`

### (c) Sampled net-heating sign

二维图显示浅柱净加热、深柱净冷却及两者之间的根带。中性色只保留给失败点评价；本次正式
温度域内没有失败点。`[V]`

### (d) Emergent continuum versus local blackbody

两条曲线分别按各自有限能段积分归一化，只用于比较形状；绝对顶部通量比另行记录。有限柱
谱的峰移到 EUV，并显著增加离化种子能流。它仍是静态门输出，不是 Phase 4 替换谱。`[V/O]`

## 9. 收敛、产物和复现

| 加密轴 | 温度剖面最大相对差 | 顶部连续通量相对差 |
|---|---:|---:|
| 频率 $65\rightarrow129$ | $9.95\times10^{-3}$ | $2.67\times10^{-4}$ |
| 深度 $4\rightarrow8$ | $5.41\times10^{-4}$ | $4.62\times10^{-4}$ |
| 角度 $4\rightarrow8$ | $2.34\times10^{-3}$ | $3.74\times10^{-4}$ |

温度仍只有百分级频率精度；谱形距离 $1.239$ 和峰能量比 $3.87$ 远大于该误差，路线分类稳健。
`[V]`

核心文件：

- `src/eccentric_tde_observer/static_atmosphere_energy.py`：有限沉积、Compton 和线边界；
- `src/eccentric_tde_observer/thermal_balance.py`：附加能量项进入根和稳定性矩阵；
- `scripts/phase7b4g_finite_deposition_column.py`：正式扫描、加密、报告与英文图；
- `tests/test_static_atmosphere_energy.py`：解析极限、开关和能量账本测试。

机器可读产物：

- `outputs/phase7b4g_finite_column_report.json`；
- `outputs/phase7b4g_column_topology.csv`；
- `outputs/phase7b4g_validity_map.csv`；
- `outputs/phase7b4g_process_controls.csv`；
- `outputs/phase7b4g_temperature_profile.csv`；
- `outputs/phase7b4g_convergence.csv`；
- `outputs/phase7b4g_emergent_continuum.csv`；
- `outputs/phase7b4g_finite_column.png`；
- `outputs/phase7b4g_convergence.png`。

复现命令：

```bash
cd /Users/shandike/Downloads/A_USTCer/8.3/eccentric_tde_observer
uv run python scripts/phase7b4g_finite_deposition_column.py --output-dir outputs
uv run pytest -q
```

## 10. 路线决策

1. `[V]` 静态近似没有失败：存在稳定有限柱根，热时间远短于轨道周期；
2. `[V]` 连续谱差异大：暂不进入 UVOT 仪器层；
3. `[O]` 下一阶段建立有限静力大气表，至少加入垂向密度、物理耗散结构和中面对称边界；
4. `[O]` 只有该表通过能量、网格和边界验收后，才替换 Phase 4 并重算观察者谱；
5. `[O]` 若静力表失去稳定根或热/电离时标接近轨道时标，才进入周期动态 NLTE；
6. `[O]` Cloudy 或其他真实线形成仍等待连续谱与 ionizing seed 的物理表完成。

后续结果见
[[eccentric_tde_observer/docs/phase7b4h_hydrostatic_table_gate|Phase 7B4h 有限静力大气表准入门]]：
`[V]` 静态热根存在，但当前 H/He 静力柱在全部 12 个代表点都只能以
$H_{\rm static}/H_{\rm ZO}=0.292$--$0.356$ 支撑自身，未通过保持 ZO 几何的准入门。因此路线已
从“建立静力表”切换为“周期动态柱”，Phase 4 替换和 UVOT 仪器层仍未获准。
