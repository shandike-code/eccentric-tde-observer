# Phase 7B4e：基态 Milne 连续发射与固定温度能量账本

> [!abstract] 阶段结论
> `[V]` 本阶段在固定温度、固定密度板层中，用同一组 H I、He I、He II 基态 Verner
> 光致截面同时构造光致电离率、自然/受激复合率、净束缚--自由消光和复合连续发射；
> 自由--自由过程满足 Kirchhoff 关系，电子散射保持相干。
> `[V]` 双侧同温 Planck 控制一步保持 LTE，Milne 源函数相对峰值 Planck 强度的最大误差为
> $2.86\times10^{-16}$；主展示解的边界--体积能量残差和光子率恒等式残差分别为
> $7.42\times10^{-16}$ 和 $2.79\times10^{-15}$。
> `[A-control]` 当前气体温度仍固定；图中的出射连续谱只是基态 Milne 控制谱，不是 ZO
> 环带大气谱，也不是可替换 modified-blackbody 的最终答案。
> `[O]` 激发态、与总辐射复合率一致的级联、bound--bound 转移、气体能量方程、速度--频率
> 耦合和轨道周期耦合仍未闭合。

导航：[[eccentric_tde_observer/README|项目 README]] ·
[[eccentric_tde_observer/docs/phase7b4d_coupled_slab|Phase 7B4d 固定板层反馈]] ·
[[eccentric_tde_observer/docs/phase7b3_atomic_continuum|Phase 7B3 原子连续谱]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

---

## 1. 7B4e 关闭了哪一个缺口

Phase 7B4d 已闭合 $J_{\nu}$--基态布居--opacity 固定点，但内部连续发射严格取零。因此
光子被吸收后只离开辐射场，不能检验复合连续发射、Kirchhoff 极限或完整边界--体积能量
账本。7B4e 把固定点扩展为

$$
\boldsymbol x^{(k)}
\longrightarrow
\left(\chi_{\nu}^{(k)},\eta_{\nu}^{(k)}\right)
\longrightarrow
J_{\nu}^{(k)}
\longrightarrow
\left(\Gamma_{i}^{(k)},\alpha_{i}^{(k)}\right)
\longrightarrow
\boldsymbol x_{\rm eq}^{(k)}.
$$

这里 $\boldsymbol x$ 仍只包含 H I/H II 和 He I/He II/He III 基态电离分数。为保证“率”和
“发射”确实来自同一个原子闭合，本阶段使用**直接复合到基态**的 Milne 控制网络，不把
Phase 7B3 的文献总辐射复合率混入。后者包含到激发态的复合，若没有逐级复合连续谱和级联，
与基态发射强行配对会破坏光子数账本。`[L/A-control]`

因此 7B4e 不是在 7B4d 的全部碰撞网络上“加一条发射曲线”，而是独立隔离出一个可严格
验收的纯辐射基态子问题。碰撞电离、三体逆过程和它们的气体能量交换留给后续能量方程阶段。
`[A-control/O]`

## 2. 束缚--自由 Milne 闭合

对每条基态连续边，定义 Saha 因子

$$
S_{i}(T)
=\left.\frac{n_{i+1}n_{\rm e}}{n_{i}}\right|_{\rm LTE}.
$$

使用同一个基态光致截面 $\sigma_{i}(\nu)$，含受激复合修正的净束缚--自由消光为

$$
\chi_{\nu,i}^{\rm bf}
=\sigma_{i}(\nu)
\left[
n_{i}
-\frac{n_{i+1}n_{\rm e}}{S_{i}(T)}
\exp\left(-\frac{h\nu}{k_{\rm B}T}\right)
\right].
$$

自然复合连续发射系数为

$$
\eta_{\nu,i}^{\rm bf}
=\sigma_{i}(\nu)
\frac{n_{i+1}n_{\rm e}}{S_{i}(T)}
\frac{2h\nu^{3}}{c^{2}}
\exp\left(-\frac{h\nu}{k_{\rm B}T}\right).
$$

在 LTE 中 $n_{i+1}n_{\rm e}/S_{i}=n_{i}$，所以逐频得到

$$
\frac{\eta_{\nu,i}^{\rm bf}}{\chi_{\nu,i}^{\rm bf}}
=B_{\nu}(T).
$$

这不是事后把源函数设成 Planck 函数，而是由同一截面和详细平衡关系推导出来。代码若发现
$\chi_{\nu,i}^{\rm bf}<0$，会抛出 `ContinuumPopulationInversionError`；不会用 `clip`、floor
或重归一化把反转态伪装成普通吸收介质。`[L/V]`

## 3. 与同一截面配对的辐射率

光致电离率为

$$
\Gamma_{i}
=4\pi\int
\frac{\sigma_{i}(\nu)J_{\nu}}{h\nu}
\,\mathrm d\nu.
$$

直接复合到基态的自然辐射复合系数为

$$
\alpha_{i}^{\rm sp}
=\int
\frac{8\pi\nu^{2}}{c^{2}}
\frac{\sigma_{i}(\nu)}{S_{i}(T)}
\exp\left(-\frac{h\nu}{k_{\rm B}T}\right)
\,\mathrm d\nu,
$$

受激复合系数为

$$
\alpha_{i}^{\rm st}
=4\pi\int
\frac{\sigma_{i}(\nu)J_{\nu}}{h\nu S_{i}(T)}
\exp\left(-\frac{h\nu}{k_{\rm B}T}\right)
\,\mathrm d\nu.
$$

于是 $\alpha_{i}^{\rm Milne}=\alpha_{i}^{\rm sp}+\alpha_{i}^{\rm st}$。当
$J_{\nu}=B_{\nu}(T)$ 时，代码逐种离子回收

$$
\alpha_{i}^{\rm Milne}
=\frac{\Gamma_{i}[B_{\nu}(T)]}{S_{i}(T)}.
$$

主控制的频率网格在每条 Verner 截面跳变处同时放置“可表示的边下左极限”和精确边节点，
避免梯形积分跨越不连续截面。旧的规定辐射场网格接口没有被改写。`[V]`

## 4. 自由--自由、散射与转移方程

自由--自由消光沿用含受激辐射修正的热电子表达式，其发射严格取

$$
\eta_{\nu}^{\rm ff}
=\chi_{\nu}^{\rm ff}B_{\nu}(T).
$$

总真吸收和热发射为

$$
\chi_{\nu}^{\rm abs}
=\sum_{i}\chi_{\nu,i}^{\rm bf}+\chi_{\nu}^{\rm ff},
$$

$$
\eta_{\nu}^{\rm th}
=\sum_{i}\eta_{\nu,i}^{\rm bf}+\eta_{\nu}^{\rm ff}.
$$

电子散射为 $\chi_{\nu}^{\rm es}=n_{\rm e}\sigma_{\rm T}$。静态平面平行转移的源函数等价写成

$$
S_{\nu}
=\frac{\eta_{\nu}^{\rm th}+\chi_{\nu}^{\rm es}J_{\nu}}
{\chi_{\nu}^{\rm abs}+\chi_{\nu}^{\rm es}}.
$$

单侧边界在 $\mu=0$ 处不连续，因此本阶段新增半区间 Gauss--Legendre 角求积：正、负半球
分别映射求积，再合并成总方向网格。它精确回收每个半球的零阶矩和一阶矩，避免用全区间
节点缓慢逼近单侧入射能流。原全区间接口保留不变。`[V]`

## 5. 固定温度能量账本

气体从辐射场获得的局域净功率为

$$
q_{\rm rad}(z)
=4\pi\int
\left[
\chi_{\nu}^{\rm abs}J_{\nu}
-\eta_{\nu}^{\rm th}
\right]
\,\mathrm d\nu.
$$

转移解必须满足

$$
F_{\rm bottom}-F_{\rm top}
+\int q_{\rm rad}(z)\,\mathrm dz
=0.
$$

主控制保持 $T=4.0\times10^{4}\ \mathrm K$ 不变，所以还必须显式报告

$$
q_{\rm thermostat}(z)=-q_{\rm rad}(z).
$$

$q_{\rm thermostat}$ 不是已知物理加热机制，而是回答“若强行固定当前温度，外部热库每单位
体积必须补入或移走多少能量”。本阶段没有解 $T(z)$，因此不能把 $q_{\rm rad}\ne0$ 的解称为
辐射平衡大气。`[A-control/V/O]`

束缚--自由光子账本另逐种离子验证

$$
4\pi\int
\frac{\chi_{\nu,i}^{\rm bf}J_{\nu}-\eta_{\nu,i}^{\rm bf}}
{h\nu}
\,\mathrm d\nu
=n_{i}\Gamma_{i}
-n_{i+1}n_{\rm e}\alpha_{i}^{\rm Milne}.
$$

这条恒等式正是“同一截面同时产生率与发射”的核心验收门。`[V]`

## 6. 控制参数与正式展示结果

固定控制仍取

$$
T=4.0\times10^{4}\ \mathrm K,
\qquad
\rho=10^{-10}\ \mathrm{g\,cm^{-3}},
\qquad
m_{\rm slab}=10^{-4}\ \mathrm{g\,cm^{-2}},
$$

上边界入射为

$$
I_{\nu}^{\rm top,in}
=10^{-6}B_{\nu}(1.5\times10^{5}\ \mathrm K),
$$

下边界无入射。能量范围为 $0.1$--$5000\ \mathrm{eV}$。正式展示采用 2049 个对数基点、
三条边的左右极限节点、16 个深度单元和 16 个半区间角方向，总频率点数为 2055。
这些参数只构造中等光深控制板层，不来自某个 ZO 面元。`[A-control]`

有限能段的能流分解为：

| 分量 | 相对入射能流 |
|---|---:|
| 顶面向外 | 0.0752506 |
| 底面向外 | 0.9234955 |
| 气体净辐射加热 | 0.00125389 |
| 所需恒温项 | -0.00125389 |

三项辐射分配之和为 1；主解相对边界能量残差为 $7.42\times10^{-16}$，最大相对光子率
恒等式残差为 $2.79\times10^{-15}$，固定点残差为 $6.63\times10^{-12}$。`[V]`

取固定归一化深度 $x=z/L$：

| 位置 | $x_{\rm H\,\rm II}$ | $x_{\rm He\,\rm III}$ |
|---:|---:|---:|
| $x=0.2$ | 0.998420 | 0.959172 |
| $x=0.5$ | 0.998286 | 0.955141 |
| $x=0.8$ | 0.998066 | 0.949155 |

这些布居与 Phase 7B4d 不应逐值比较：7B4d 使用碰撞电离与文献总辐射复合率但无内部发射，
7B4e 使用纯辐射、直接到基态的 Milne 控制网络。二者回答的是不同闭合测试。`[A-control]`

## 7. 主图逐面解释

![Phase 7B4e 基态 Milne 连续发射](../outputs/phase7b4e_continuum_emission.png)

### (a) Finite-band continuum energy flow

横轴为光子能量，纵轴为每个对数能量区间的能流除以总入射能流。黑线是入射场；蓝线是
顶面向外的返回与内部发射总和；红线是底面透射与内部发射总和。三条灰色竖线标出 H I、
He I 和 He II 连续边。曲线只表示该固定板层的控制谱，不是 ZO 观察者谱。`[A-control/V]`

### (b) Self-consistent ground-state populations

H II 在全层保持约 $0.998$；He III 从照明面约 $0.960$ 缓慢降至底部约 $0.949$，He II
对应增加。这里“self-consistent”只指基态 Milne 率、连续 opacity、内部连续发射与
$J_{\nu}$ 的固定点。`[V/O]`

### (c) Fixed-temperature energy ledger

辐射净加热为正，所需恒温项逐深度严格取相反数。越靠近无入射底边界，局域净加热越强；
这提示规定的 $4\times10^{4}\ \mathrm K$ 并不是当前辐照下自动得到的平衡温度。`[V/O]`

### (d) Admissible initial-state convergence

完全中性初态和高温 LTE 初态在 1025 基点控制网格上分别收敛到同一解，最终五种离子分数
最大差为 $2.57\times10^{-11}$。完全电离初态会产生负的基态净消光，已被显式拒绝，不能
当作普通初态再裁剪。`[V]`

## 8. 详细平衡与收敛图逐面解释

![Phase 7B4e 详细平衡与收敛控制](../outputs/phase7b4e_continuum_convergence.png)

### (a) LTE Kirchhoff control

双侧边界取同温 Planck 场、布居取 Saha 状态时，Milne 热源函数与 $B_{\nu}$ 在整段频率上
重合。以峰值 Planck 强度归一的最大绝对差为 $2.86\times10^{-16}$。`[V]`

### (b) Ground-state detailed balance

对 H I、He I、He II，直接积分得到的 $\alpha_{i}^{\rm Milne}$ 与
$\Gamma_{i}[B_{\nu}]/S_{i}$ 重合，最大相对误差为 $1.11\times10^{-16}$。这验证的是
基态详细平衡，不代表已经得到总辐射复合率或复合级联。`[V/O]`

### (c) Separated numerical convergence

频率、深度和角度分别加密，布居误差与能量诊断误差独立展示。主控制 1025 基点直接加密到
2049 基点时，最大布居差为 $8.15\times10^{-5}$，顶/底出射能流相对差分别为
$6.28\times10^{-4}$ 和 $8.58\times10^{-5}$；净加热因是两个大能流之差，相对差仍为
$2.55\times10^{-2}$。在分离频率扫描中，2049 相对 4097 基点的相应误差降到
$2.05\times10^{-5}$、$1.55\times10^{-4}$、$2.19\times10^{-5}$ 和
$4.33\times10^{-3}$。`[V]`

16 到 32 个深度单元的主配置控制给出最大布居差 $3.28\times10^{-5}$、最大能量诊断差
$3.38\times10^{-4}$；16 到 32 阶半区间角求积给出 $2.39\times10^{-5}$ 和
$4.07\times10^{-3}$。因此布居和顶/底出射能流已达到约 $10^{-4}$--$10^{-3}$ 级，微小
净加热差值的实际频率/角度误差约为几个 $10^{-3}$，没有伪装成 $10^{-3}$ 以下。`[V]`

### (d) Finite-band energy partition

顶面与底面向外能流加上气体净辐射加热，回到单位入射能流；恒温项与气体净加热等量反号。
该柱状图不能解读为真实盘中存在一个已知负加热机制。`[A-control/V/O]`

## 9. 文件、测试与复现

核心文件：

- `src/eccentric_tde_observer/continuum_emission.py`：Milne 网格、净消光、连续发射、同截面率和固定点；
- `src/eccentric_tde_observer/radiative_transfer_1d.py`：新增半区间角求积，保留原全区间接口；
- `tests/test_continuum_emission.py`：Kirchhoff、详细平衡、能量、光子率、初态和拒绝测试；
- `tests/test_radiative_transfer_1d.py`：半区间零阶/一阶角矩测试；
- `scripts/phase7b4e_continuum_emission.py`：正式控制、逐轴收敛、制图和机器可读报告。

机器可读产物：

- `outputs/phase7b4e_continuum_emission_report.json`：参数、主结果、严格控制和阶段边界；
- `outputs/phase7b4e_emissive_slab_depth.csv`：逐深度布居、率和能量项；
- `outputs/phase7b4e_emergent_continuum.csv`：入射、顶面向外和底面向外连续谱；
- `outputs/phase7b4e_continuum_convergence.csv`：频率、深度、角度、欠松弛与主配置直接加密；
- `outputs/phase7b4e_continuum_emission.png`：主控制四面板图；
- `outputs/phase7b4e_continuum_convergence.png`：详细平衡、收敛与能量分配图。

复现命令：

```bash
cd /Users/shandike/Downloads/A_USTCer/8.3/eccentric_tde_observer
uv run python scripts/phase7b4e_continuum_emission.py --output-dir outputs
uv run pytest -q
```

代码没有使用 `nan_to_num`、无物理理由的 `clip`、任意 floor、失败点删除或事后重归一化。
本阶段新增 8 项连续发射专项测试和 1 项半区间角矩测试；全项目现场回归为
`265 passed in 8.88s`。所有图内标题、坐标和图例均为英文。`[V]`

## 10. 当前允许与禁止的结论

> `[L/V]` 可以说：基态 H/He 的同截面 Milne 率、净束缚--自由消光、复合连续发射和
> 自由--自由 Kirchhoff 发射已经形成一个满足 LTE、光子数和总能量控制的固定温度闭环。

> `[A-control/V]` 可以说：在当前规定板层中，内部连续发射只小幅重分配入射能量，气体
> 净吸收约占有限能段入射能流的 $1.25\times10^{-3}$；若保持温度固定，必须有等量反号的
> 外部恒温项。

> `[O]` 不能说：该出射曲线已经是 ZO 裸偏心盘的真实连续谱，或已经证明它优于
> modified-blackbody。当前还没有求解温度、激发态、总复合级联、bound--bound、Compton
> 能量交换、速度--频率耦合或轨道周期。

这一步现已由
[[eccentric_tde_observer/docs/phase7b4f_temperature_balance|Phase 7B4f]] 接续：固定密度板层
已求逐深度温度、稳定根与无根门；完整 ZO 近心点单面耗散在当前薄层中无根，因此下一步先
扫描有限沉积柱质量，而不是直接推广回 ZO 周期柱。`[A/V/O]`
