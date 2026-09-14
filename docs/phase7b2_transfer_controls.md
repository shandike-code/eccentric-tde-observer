# Phase 7B2：频率--角度辐射转移解析控制

> [!abstract] 阶段结论
> `[V]` 本阶段建立了一维平面平行、频率分组、角度分辨的静态和时间依赖辐射转移控制核，
> 并通过真空、等温纯吸收、保守纯散射、线性源函数和时间解趋近静态解的门槛。
> `[A]` Planck 源函数、灰吸收和灰相干散射都只是解析控制输入。
> `[O]` 当前仍没有物理频率依赖 opacity、H/He 原子率、速度导致的频率--角度耦合、
> 耗散深度闭合或 NLTE 连续谱，因此本阶段没有替换 Phase 2--5 的 modified-blackbody。

导航：[[eccentric_tde_observer/README|项目 README]] ·
[[eccentric_tde_observer/docs/phase7b_periodic_column|Phase 7B1 周期柱]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

---

## 1. 为什么 Phase 7B2 先做解析控制

Phase 7B1 已经给出规定的 ZO 周期背景和守恒布居推进器，但它没有求辐射场。若此时直接
加入大量原子过程，就无法判断误差来自转移离散、边界、刚性源项还是原子率。本阶段因此只
关闭最小的转移数值问题：给定 extinction、热源函数和散射比例，能否可靠推进
$I_{\nu}(t,z,\mu)$。`[A/V]`

这种分层次实现与文献中的方法论一致：Jiang、Stone 与 Davis 使用离散射线、迎风空间更新
和算子分裂处理时间依赖转移；Hauschildt 与 Baron 则展示了形式解、散射源函数和
operator splitting 的标准结构。两篇文献支持算法框架，不代表本项目已经实现其完整的
$O(v/c)$、MHD 或生产级多维求解器。`[L/A]`

- [Jiang, Stone & Davis 2014](https://arxiv.org/abs/1403.6126)
- [Hauschildt & Baron 2006](https://arxiv.org/abs/astro-ph/0601183)

## 2. 当前方程、坐标和边界

深度坐标 $z$ 从板层顶部向下增加，$\mu>0$ 表示向下传播，$\mu<0$ 表示从顶部向外传播。
当前静止介质方程为

$$
\frac{1}{c}\frac{\partial I_{\nu}}{\partial t}
+\mu\frac{\partial I_{\nu}}{\partial z}
=\chi_{\nu}\left(S_{\nu}-I_{\nu}\right).
$$

各向同性、相干散射控制使用

$$
S_{\nu}
=\epsilon_{\nu}B_{\nu}
+\left(1-\epsilon_{\nu}\right)J_{\nu},
$$

$$
J_{\nu}=\frac{1}{2}\int_{-1}^{1}I_{\nu}\,\mathrm d\mu,
\qquad
F_{\nu}=2\pi\int_{-1}^{1}\mu I_{\nu}\,\mathrm d\mu.
$$

其中 $\chi_{\nu}$ 是 extinction per length，$\epsilon_{\nu}$ 是一次相互作用被真实吸收的
概率。于是 $\epsilon_{\nu}=1$ 是纯吸收控制，$\epsilon_{\nu}=0$ 是保守纯散射控制。
当前频率组彼此独立，没有 Compton 重分布，也没有速度项把相邻频率或角度连接起来。
`[A/O]`

静态真空边界只允许顶部向下的入射强度和底部向上的入射强度。输入若把“出射方向”误填成
外部入射，代码直接拒绝。时间控制可选择同样的开放边界，或选择周期空间边界；周期边界与
外部入射不能同时打开。`[V]`

## 3. 静态形式解

每个深度单元内把源函数取为常数。沿一条方向余弦为 $\mu$ 的特征线，单元出射强度为

$$
I_{\nu,\mathrm{out}}
=I_{\nu,\mathrm{in}}\exp\left(-\frac{\Delta\tau_{\nu}}{|\mu|}\right)
+S_{\nu}\left[1-\exp\left(-\frac{\Delta\tau_{\nu}}{|\mu|}\right)\right].
$$

单元平均强度也用该指数解解析计算。实现没有对大光深做任意裁剪；当
$\Delta\tau_{\nu}=0$ 时直接取真空极限。`[V]`

散射问题写成离散 $\Lambda$ 算子的线性系统：

$$
\left[\mathbf I-\operatorname{diag}(1-\boldsymbol\epsilon)\boldsymbol\Lambda\right]
\boldsymbol S
=\boldsymbol\epsilon\boldsymbol B
+(1-\boldsymbol\epsilon)\boldsymbol J_{\rm boundary}.
$$

Phase 7B2 显式构造稠密 $\Lambda$ 矩阵并直接求解。这样便于严格检查源函数方程残差，但计算
量和内存不适合生产级多频率高分辨率柱。后续若进入真实原子和多频率阶段，应改为经过验证的
ALI、Gauss--Seidel 或 Krylov 路径。`[A/O]`

## 4. 五个解析门槛

### 4.1 真空传播

当 $\chi_{\nu}=0$ 时，入射强度应穿过板层而不衰减。静态和时间控制均回收该极限；周期时间
控制在 CFL 恰为 1 时把离散脉冲精确平移三个单元，最大绝对误差为 0。`[V]`

### 4.2 等温纯吸收

对总光深 $\tau_{\nu}$、无外部入射且源函数为常数 $B_{\nu}$ 的板层，顶部向外强度解析解为

$$
I_{\nu}^{\rm out}(\mu_{\rm out})
=B_{\nu}\left[1-\exp\left(-\frac{\tau_{\nu}}{\mu_{\rm out}}\right)\right],
\qquad 0<\mu_{\rm out}\le1.
$$

顶部单面出射能流为

$$
F_{\nu}^{\rm out}
=2\pi B_{\nu}\left[\frac{1}{2}-E_{3}(\tau_{\nu})\right].
$$

若 $\tau_{\nu}$ 是灰的，对频率积分后有

$$
F^{\rm out}
=\left[1-2E_{3}(\tau)\right]\sigma_{\rm SB}T^{4}.
$$

角分辨强度在浮点精度内回收解析式。64 阶 Gauss--Legendre 求积在 $\tau=1$ 的能流相对
误差为 $2.533\times10^{-4}$。使用 2049 个对数频率点积分 Planck 函数时，
$\pi\int B_{\nu}\,\mathrm d\nu=\sigma_{\rm SB}T^{4}$ 的相对误差为
$6.843\times10^{-6}$。`[V]`

### 4.3 线性源函数的深度收敛

控制源函数取

$$
S(\tau)=S_{0}+\Delta S\frac{\tau}{\tau_{\rm tot}}.
$$

深度网格从 16、32、64 加到 128 时，顶部强度最大绝对误差依次为
$2.465\times10^{-3}$、$6.199\times10^{-4}$、$1.552\times10^{-4}$ 和
$3.881\times10^{-5}$；每次加倍约下降四倍，回收到分层中点形式解的二阶趋势。`[V]`

### 4.4 保守纯散射

顶部半球以 $I_{\nu}=1$ 入射，底部真空。令反射、透射与入射能流分别为
$F_{\rm R}$、$F_{\rm T}$ 和 $F_{\rm in}$，保守门要求

$$
\frac{F_{\rm R}+F_{\rm T}}{F_{\rm in}}=1.
$$

| 总散射光深 | 深度单元 | 反射分数 | 透射分数 | 反射加透射 |
|---:|---:|---:|---:|---:|
| 0.1 | 128 | 0.0847619 | 0.9152381 | 1.0000000 |
| 1 | 128 | 0.4469238 | 0.5530762 | 1.0000000 |
| 10 | 128 | 0.8831773 | 0.1168227 | 1.0000000 |
| 199.099 | 1024 | 0.9932948 | 0.0067052 | 1.0000000 |

最难的 ZO 高光深案例中，源函数方程相对残差为 $8.91\times10^{-16}$，能量平衡相对残差
为 $1.21\times10^{-11}$，最小强度保持非负。`[V]`

必须区分“守恒”和“分量收敛”：在 $\tau_{\rm es}=199.099$ 时，512 到 1024 个深度单元
之间，反射分数相对变化只有 $1.75\times10^{-4}$，但很小的透射分数仍变化
$2.59\%$。因此本阶段可以确认总能流守恒和散射极限方向正确，却不能声称高光深透射已经
达到 $10^{-3}$ 相对精度。固定 512 个深度单元时，32 到 64 阶角求积使透射分数相对变化
$4.06\times10^{-4}$，说明此时主要限制来自深度而不是角度。`[V/O]`

### 4.5 时间解趋近静态解

碰撞步把角平均与各向异性部分分开：

$$
J_{\nu}(t+\Delta t)
=B_{\nu}+\left[J_{\nu}(t)-B_{\nu}\right]
\exp\left(-c\chi_{\nu}\epsilon_{\nu}\Delta t\right),
$$

$$
I_{\nu}-J_{\nu}
\longrightarrow
\left(I_{\nu}-J_{\nu}\right)
\exp\left(-c\chi_{\nu}\Delta t\right).
$$

空间输运使用 CFL 不大于 1 的单调迎风凸组合，并采用半步碰撞--整步输运--半步碰撞。
均匀吸收衰减和均匀纯散射各向同性化的最大解析误差均为 0；纯散射总辐射含量相对残差为
0。开放板层从零辐射场推进到等温纯吸收静态解时，深度网格从 16 加密到 2048，最大绝对
误差从 $4.921\times10^{-2}$ 降至 $4.960\times10^{-4}$，表现为预期的一阶空间收敛。
`[V]`

## 5. ZO 压力测试怎样接入

Phase 7A 的代表柱 03 对应径向索引 8；Phase 7B1 把该半长轴展开成完整轨道。在选中相位
$E=0$，本阶段只读取

$$
T_{\rm eff}=3.64961\times10^{4}\ {\rm K},
\qquad
\tau_{\rm es,\rm mid}=199.099.
$$

$T_{\rm eff}$ 只用于等温 Planck 解析控制；$\tau_{\rm es,\rm mid}$ 只用于单侧灰纯散射压力
测试。代码没有把电子散射光深重命名为吸收光深，没有使用 pre-Erratum 面积，也没有修改
$\Sigma$、$H$、$T_{\rm eff}$ 或任何 ZO 动力学源场。局域柱测试不做全盘面积积分，所以此处
也不存在用旧面积替代 corrected 面积的问题。`[A/V]`

## 6. 图怎样看

![Phase 7B2 频率--角度转移控制](../outputs/phase7b2_transfer_controls.png)

### 面板 (a)：等温纯吸收

横轴是无量纲频率 $h\nu/(kT)$，纵轴是 $\nu F_{\nu}/(\sigma_{\rm SB}T^{4})$。实线是
数值离散纵标结果，虚线是指数积分解析解。小光深压低整条谱，大光深趋近半无限黑体边界。
曲线重合验证形式解和角求积，不是 ZO 的新物理连续谱。`[A-control/V]`

### 面板 (b)：保守散射

蓝、橙曲线分别是反射和透射能流分数，绿线是二者之和。光深增加时透射降低、反射升高，
但绿线保持 1。最右点使用实际 ZO 单侧电子散射光深。它验证守恒和高光深数值稳定性，不
代表真实盘只有灰相干电子散射。`[A-control/V/O]`

### 面板 (c)：三个静态收敛轴

角求积、线性源函数的深度离散、Planck 频率积分和高光深散射角求积分别收敛。把这些轴
分开，是为了避免一个较小的总误差掩盖某个尚未分辨的方向。`[V]`

### 面板 (d)：两个仍需重点看的深度问题

蓝线是高光深纯散射透射相对最细 1024 单元结果的变化；橙线是时间解与静态形式解的最大
差。橙线已在 2048 单元低于 $10^{-3}$，蓝线在 512 到 1024 间仍为 $2.59\%$。因此本图
同时显示了一个通过的时间静态门和一个尚未达到目标精度的高光深小透射分量。`[V/O]`

## 7. 产物与复现

```bash
cd /Users/shandike/Downloads/A_USTCer/8.3/eccentric_tde_observer
uv run python scripts/phase7b2_transfer_controls.py --output-dir outputs
uv run pytest -q
```

- `outputs/phase7b2_transfer_report.json`：假设、接受门、ZO 压力测试与未解决物理；
- `outputs/phase7b2_absorption_spectrum.csv`：逐频率数值和解析纯吸收能流；
- `outputs/phase7b2_scattering_conservation.csv`：反射、透射、守恒、源残差和条件数；
- `outputs/phase7b2_convergence.csv`：角、深度、频率和高光深散射的独立收敛；
- `outputs/phase7b2_time_controls.csv`：真空、吸收、散射和静态极限时间控制；
- `outputs/phase7b2_transfer_controls.png`：四面板审计图。

本阶段完成后的全项目现场回归为 `209 passed`；其中 14 个新增测试专门覆盖上述转移解析
极限、收敛趋势、守恒、非负性和非法输入拒绝。以后复现仍应以当次测试输出为准。`[V]`

## 8. 本阶段允许与禁止的结论

> `[V]` 可以说：项目已有一个通过基本解析极限、保持非负、能检查源方程和能流残差的
> 一维频率--角度静态及时间依赖转移底座。

> `[O]` 不可以说：项目已经产生比 modified-blackbody 更真实的 ZO 连续谱。当前画出的
> Planck 形状是解析输入，不是从原子布居、真实 opacity 和能量方程涌现的结果。

Phase 7B3 已完成其中第一项：

1. `[L/V]` 可追溯的 H/He 基态 bound--free、总辐射复合、free--free 和电子散射率；
2. `[A/O]` ZO 总表面能流怎样分配到柱深度，而不人为指定漂亮的加热剖面；
3. `[O]` 垂向呼吸速度带来的频率--角度耦合，以及何时必须保留 $O(v/c)$ 项；
4. `[O]` 辐射场、布居与气体能量之间的时间依赖闭合；
5. `[O]` 高光深散射应采用生产级迭代算子，并把小透射分量也收敛到明确目标。

Phase 7B3 的实现、阈值分段、静态耦合与剩余边界见
[[eccentric_tde_observer/docs/phase7b3_atomic_continuum|Phase 7B3 报告]]。它仍未解决列表
第 2--5 项，因此不能宣称动态 NLTE 谱，也没有调用 Cloudy、盘风或事件拟合。
