# Phase 7B4h：有限静力大气表准入门

> `[V]` 低分辨率、全柱、含碰撞 H/He Milne 连续过程的直接求解存在静态热平衡根；但在
> ZO 给定的 $m_{0}$、$H$ 和 $Q$ 上，LTE 基态 H/He Rosseland 扩散柱只能提供所需静力压力的
> 约三成。两种预先声明的耗散律、全部 12 个代表柱都要求
> $H_{\rm static}/H_{\rm ZO}=0.292$--$0.356$，没有进入 $0.8$--$1.2$ 的几何保持门。因此本阶段
> **不允许**用该静态表替换 Phase 4，也不进入 UVOT 仪器层；下一阶段进入周期动态柱。

关联文档：

- [[eccentric_tde_observer/docs/phase7b4g_finite_deposition_column|Phase 7B4g 有限沉积柱静态门]]；
- [[eccentric_tde_observer/docs/phase7b_periodic_column|Phase 7B1 周期柱数值底座]]；
- [[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]；
- [[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]。

## 1. 本阶段究竟检验什么

Phase 7B4g 已证明：把 ZO 单面耗散分配到有限质量柱后，可以找到稳定温度根，而且输出连续谱
与局域黑体差异很大。那仍是固定密度、双真空面的控制柱，不能直接成为环带大气表。

Phase 7B4h 增加三个此前缺少的条件：

1. 用 ZO 已有的单面柱质量 $m_{0}$、尺度高度 $H$ 和共动垂向重力系数 $Q$ 建立有限密度剖面；
2. 用中面镜像严格实施对称边界，并从表面到中面逐层积分通量；
3. 检验气体压力与辐射压力能否支撑同一个 ZO 几何，而不重定义 ZO 的 $H(a,E)$。

这里的核心不是“能不能求出某条温度曲线”，而是：**该温度与 opacity 解能否在保持 ZO 几何时
同时满足静力支撑。** `[A/V]`

## 2. ZO 到有限柱的映射

### 2.1 质量坐标与 $n=3$ 闭合

采用 Lynch--Ogilvie 垂向闭合中项目已有的有限 $n=3$ 形状：

$$
\rho(z)=\rho_{\rm c}
\left[1-\left(\frac{z}{3H}\right)^2\right]^3,
\qquad |z|<3H,
$$

并定义从上表面指向中面的质量坐标

$$
m(z)=\int_{z}^{3H}\rho(z')\,{\rm d}z',
\qquad 0\leq m\leq m_{0}.
$$

程序先在 $m$ 上布点，再用解析累计质量函数的反函数得到 $z$。每个单元直接取

$$
\rho_{k}=\frac{\Delta m_{k}}{\Delta z_{k}},
$$

所以总质量由离散定义回收，不需要事后重归一化。下半柱由上半柱镜像得到；密度、加热和温度
均精确满足中面对称。`[A/V]`

### 2.2 所需支撑压力

共动垂向重力取 ZO 已有的线性形式

$$
g_{z}=-Qz.
$$

上述 $n=3$ 密度对应的所需支撑压力满足

$$
\frac{{\rm d}P_{\rm req}}{{\rm d}z}=-\rho Qz,
\qquad
P_{\rm req}(z)=P_{\rm c}
\left[1-\left(\frac{z}{3H}\right)^2\right]^4.
$$

这只是把 ZO 源场映射成一个可审计的压力目标；没有修改 ZO 动力学或本征模。`[A]`

## 3. 两种受控耗散律

总单面通量固定为

$$
F_{\rm ZO}=\sigma_{\rm SB}T_{\rm eff}^4.
$$

系数都在求解前由 $F_{\rm ZO}$ 决定，不能根据输出谱调整。

### 3.1 单位质量均匀耗散

$$
q_{m}=\frac{F_{\rm ZO}}{m_{0}}.
$$

它是最简单的质量加热控制。`[A-control]`

### 3.2 局域支撑压力加权耗散

$$
q_{\rm vol}=C_{\rm P} P_{\rm req},
\qquad
\int_{0}^{m_{0}}\frac{q_{\rm vol}}{\rho}\,{\rm d}m=F_{\rm ZO}.
$$

它对应“局域体积耗散随支撑压力变化”的受控 $\alpha$ 型代理。它不是从当前 ZO 动力学额外
推导出的唯一耗散律，因此证据等级为 `[A-proxy]`。两种选择的目的，是检查结论是否依赖单一
垂向加热形状。

## 4. 深层扩散与 H/He Rosseland opacity

质量坐标从表面指向中面，单面通量满足

$$
\frac{{\rm d}F}{{\rm d}m}=-q_{m},
\qquad
F(0)=F_{\rm ZO},
\qquad
F(m_{0})=0.
$$

温度由灰扩散控制给出：

$$
\frac{{\rm d}T^4}{{\rm d}m}
=\frac{3\kappa_{\rm R}F}{4\sigma_{\rm SB}},
\qquad
T^4(0)=\frac{1}{2}T_{\rm eff}^4.
$$

其中 Rosseland 平均定义为

$$
\frac{1}{\kappa_{\rm R}}
=
\frac{
\int_{0}^\infty \kappa_{\nu}^{-1}
\left(\partial B_{\nu}/\partial T\right)\,{\rm d}\nu
}{
\int_{0}^\infty
\left(\partial B_{\nu}/\partial T\right)\,{\rm d}\nu
}.
$$

$\kappa_{\nu}$ 使用项目同一组 H I、He I、He II 基态 Milne 束缚--自由、自由--自由和 Thomson
散射 opacity，并在 LTE H/He 电离闭合下迭代 $T$ 与 $\kappa_{\rm R}$。它比常数 Thomson 灰控制
更物理，但仍缺少金属、激发态、线空白和完整 Compton 重分布。`[L/A/O]`

这种盘环带大气以 $T_{\rm eff}$、$m_{0}$ 和 $Q$ 为局域坐标，与 TLUSTY 盘大气的标准参数化一致；
参见 [TLUSTY 用户指南](https://tlusty.oca.eu/tlusty/Tlusty2002/pdf/tlguide202.pdf)、
[Hubeny & Hubeny 1998](https://tlusty.oca.eu/tlusty/Tlusty2002/pdf/1998Hubeny2.pdf) 和
[Davis & Hubeny 2006](https://tlusty.oca.eu/tlusty/Tlusty2002/pdf/2006Davis.pdf)。`[L]`

## 5. 静力验收量

计算的总压力为

$$
P_{\rm tot}=P_{\rm gas}+P_{\rm rad}.
$$

固定 ZO 厚度首先直接比较 $P_{\rm tot}$ 与 $P_{\rm req}$。随后只作为诊断，反求满足最深单元

$$
\frac{P_{\rm tot}}{P_{\rm req}}=1
$$

的 $H_{\rm static}$。反求根并不自动代表整柱通过；程序另行报告质量加权完整剖面残差

$$
\epsilon_{\rm P,1}
=
\frac{
\sum_{k} \Delta m_{k}
\left|P_{{\rm tot},k}-P_{{\rm req},k}\right|
}{
\sum_{k} \Delta m_{k} P_{{\rm req},k}
}.
$$

求解前声明两个准入门：

- 几何保持：$|H_{\rm static}/H_{\rm ZO}-1|\leq0.2$；
- 压力剖面：$\epsilon_{\rm P,1}\leq0.1$。

阈值属于 `[A-classification]`；结果与阈值的距离足够大，因此没有通过移动阈值得出结论。

## 6. 代表柱结果

### 6.1 固定 ZO 厚度

12 个 Phase 7A 代表柱的结果为：

| 耗散律 | 固定 $H_{\rm ZO}$ 的 $\epsilon_{\rm P,1}$ | $H_{\rm static}/H_{\rm ZO}$ | 几何通过数 |
|---|---:|---:|---:|
| 单位质量均匀 | $0.691$--$0.726$ | $0.292$--$0.334$ | 0/12 |
| 支撑压力加权 | $0.673$--$0.709$ | $0.313$--$0.356$ | 0/12 |

因此，不是某一个代表点或某一种耗散律失败，而是整个已选准静态代表集都要求明显更薄的静力柱。
`[V]`

代表柱 03 的源输入和主结果为：

| 量 | 数值 |
|---|---:|
| $T_{\rm eff}$ | $3.6496\times10^4\ {\rm K}$ |
| $m_{0}$ | $5.8559\times10^2\ {\rm g\,cm^{-2}}$ |
| $Q$ | $1.6777\times10^{-9}\ {\rm s^{-2}}$ |
| $H_{\rm ZO}$ | $1.3579\times10^{12}\ {\rm cm}$ |
| 均匀耗散 $H_{\rm static}/H_{\rm ZO}$ | $0.330685$ |
| 压力耗散 $H_{\rm static}/H_{\rm ZO}$ | $0.352249$ |
| 对应中面温度 | $1.0840\times10^5$、$1.1024\times10^5\ {\rm K}$ |

### 6.2 压力匹配根仍暴露出的动态信号

缩小 $H$ 后，所有 12 个代表柱的完整压力剖面均通过 $0.1$ 门，残差范围为 $0.028$--$0.061$。
但这些根的

$$
\max\left(\frac{g_{\rm rad}}{g}\right)=1.12\text{--}1.27.
$$

这表示某些层的向外辐射加速度超过局域重力；在完整静力解中通常会要求密度反转、对流或动态
响应。这里把它作为“密度反转诊断”，不把它伪装成已求出的稳定静力大气。`[V/O]`

代表柱 03 的 H/He Rosseland opacity 只有约
$0.336$--$0.356\ {\rm cm^2\,g^{-1}}$。若在固定 $H_{\rm ZO}$ 下人为改成常数 opacity，最深压力
匹配需要约 $1.106$ 或 $1.029\ {\rm cm^2\,g^{-1}}$，同时
$\max(g_{\rm rad}/g)>1$。这个扫描只量化“缺多少支撑”，不能把所需常数 opacity 当成新物理
输入。`[A-diagnostic/V]`

## 7. 直接非灰热根控制

真空边界、只有光致/辐射过程时，内部加热柱会落入全中性、零电子、零连续发射的暗解。为避免
把这个缺过程解误判成物理解，本阶段显式加入 Phase 7B4a 已验证的碰撞电离与详细平衡三体复合。
这不是数值 floor，也没有强迫最终布居保持 LTE；LTE 只用于初始布居。`[V]`

代表柱 03 的 $4+4$ 深度、39 频点、2 个半空间角节点直接控制得到：

- 温度范围 $3.7631\times10^4$--$4.8454\times10^4\ {\rm K}$；
- 最大局域能量残差 $2.35\times10^{-9}$；
- 全局能量残差 $1.69\times10^{-7}$；
- 顶面通量与目标之比 $1.000000169$；
- 温度镜像残差为 0。

它证明静态热根存在，但固定 $H_{\rm ZO}$ 的压力残差仍为 $0.986$。该低分辨率控制不能提供
生产级大气谱；深光深全离散角直接求解在加密后刚性很强，本阶段用经过解析门的扩散方程承担
深层结构。`[V/O]`

## 8. 图件逐一解释

![Phase 7B4h static atmosphere admission gate](../outputs/phase7b4h_hydrostatic_gate.png)

### (a) Static scale-height mismatch

蓝、橙两条曲线覆盖 12 个代表柱；全部落在 $0.29$--$0.36$，远低于绿色几何保持区。耗散律
改变结果约数个百分点，无法消除数量级明确的厚度失配。`[V]`

### (b) Reference-column pressure root

试探 $H$ 增大时，最深层总压/所需压力单调下降；两条曲线都在 $H/H_{\rm ZO}\simeq0.3$ 附近
穿过 1。虚线 $H/H_{\rm ZO}=1$ 处的比值仅约 0.31--0.34。`[V]`

### (c) Reference-column pressure profile

虚线是固定 ZO 厚度，深层长期停在约 0.3；实线是最深层匹配后的较薄柱，主体接近 1。最表面
$P_{\rm req}\rightarrow0$，比值会放大，因此采用对数纵轴并以质量加权整柱残差作正式门。`[V]`

### (d) Pressure-matched diffusion structure

两种耗散律的温度从表面约 $3.1\times10^4\ {\rm K}$ 上升到中面约
$1.1\times10^5\ {\rm K}$；H/He Rosseland opacity 只在约
$0.336$--$0.356\ {\rm cm^2\,g^{-1}}$ 内变化。该图是深层结构
控制，不是观察者连续谱。`[V/O]`

![Phase 7B4h numerical convergence](../outputs/phase7b4h_hydrostatic_convergence.png)

### (a) Depth convergence

半柱深度从 64 加密到 128，$H_{\rm static}/H_{\rm ZO}$ 的相对变化为
$1.99\times10^{-4}$（均匀耗散）和 $1.63\times10^{-4}$（压力耗散）。`[V]`

### (b) Frequency convergence

H/He Rosseland 网格从 129 加密到 257 个基础频点，相对变化为
$4.34\times10^{-4}$ 和 $4.05\times10^{-4}$。`[V]`

### (c) Full-profile residual

两种耗散律的完整压力剖面残差在深度加密后分别收敛到约 0.036 和 0.046，低于预先声明的
0.1 门。它说明反求到的薄柱内部近似自洽，却不能挽救与 ZO 厚度的失配。`[V]`

### (d) Density-inversion diagnostic

$\max(g_{\rm rad}/g)$ 随深度加密稳定在约 1.13 和 1.19，高于水平线 1；这不是单个网格点漂移。
`[V/O]`

## 9. 代码、产物与复现

核心文件：

- `src/eccentric_tde_observer/hydrostatic_atmosphere.py`：$n=3$ 有限柱、耗散律、扩散与压力门；
- `src/eccentric_tde_observer/continuum_emission.py`：逐深度密度与可选碰撞闭合；
- `src/eccentric_tde_observer/thermal_balance.py`：镜像温度参数化和逐深度密度温度根；
- `scripts/phase7b4h_hydrostatic_table_gate.py`：代表柱扫描、收敛、报告和英文图；
- `tests/test_hydrostatic_atmosphere.py`：质量、通量、解析灰解、压力根和禁用数值修补测试。

机器可读产物：

- `outputs/phase7b4h_representative_hydrostatic_gate.csv`；
- `outputs/phase7b4h_reference_profiles.csv`；
- `outputs/phase7b4h_reference_root_curve.csv`；
- `outputs/phase7b4h_convergence.csv`；
- `outputs/phase7b4h_hydrostatic_gate_report.json`；
- `outputs/phase7b4h_hydrostatic_gate.png`；
- `outputs/phase7b4h_hydrostatic_convergence.png`。

复现命令：

```bash
cd /Users/shandike/Downloads/A_USTCer/8.3/eccentric_tde_observer
uv run python scripts/phase7b4h_hydrostatic_table_gate.py --output-dir outputs
uv run pytest -q
```

本阶段完成后的全项目现场回归为 `296 passed`。`[V]`

## 10. 路线决策

1. `[V]` 静态热平衡根存在，不能把结果表述成“任何静态温度解都不存在”；
2. `[V]` 在当前 H/He 物理闭合下，保持 ZO $H$ 的静态大气表失败，不能替换 Phase 4；
3. `[V]` 两种受控耗散律和 12 个代表柱给出同一方向，结论不是挑选代理所得；
4. `[O]` 金属、激发态、线空白和 Compton 可能改变 opacity，但不能用未计算过程事后补足压力；
5. `[O]` 下一阶段进入周期动态柱，联立轨道相位依赖的压缩功、垂向运动、能量和 H/He 布居；
6. `[O]` 在动态柱通过周期闭合、守恒和收敛门以前，仍不进入 UVOT，也不把当前结果称为真实
   TDE 连续谱或线谱。
