# Phase 7B4l：保守子单元重构与空间生产门

证据标记：`[V]` 代码验证；`[A]` 工作假设；`[A-classification]` 数值分类阈值；`[O]`
未解决问题。

关联文档：

- [[eccentric_tde_observer/docs/phase7b4i_periodic_dynamic_energy|Phase 7B4i 周期动态能量柱]]；
- [[eccentric_tde_observer/docs/phase7b4j_adaptive_dynamic_convergence|Phase 7B4j 自适应深度与时间审计]]；
- [[eccentric_tde_observer/docs/phase7b4k_error_estimated_dynamic_convergence|Phase 7B4k 双网格误差与时间审计]]；
- [[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]；
- [[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]。

## 1. 本阶段回答什么

Phase 7B4k 已证明，继续调节单一网格监视权重不能同时收敛尖锐 He III 前沿的逐点值和柱
积分量。7B4l 因而检验一个更具体的问题：在不改变 ZO 源场和周期动态方程的前提下，把每个
父质量单元中的常数状态改成保守线性子单元，能否同时满足物理域、守恒和 $10^{-3}$ 空间
生产门？`[A/V]`

这里的子单元是被周期求解器独立保存和推进的有限体积自由度，不是免费获得的高阶闭合。
父单元只组织延拓、限制和守恒账本；实际计算成本仍随有效子单元数增加。`[A/V]`

本阶段不加入非局域频率转移、激发态、速度--频率耦合或新耗散律，也不生成观察者谱。
`[O]`

## 2. 保守延拓

半柱质量坐标仍定义为

$$
x=\frac{m}{m_{0}},\qquad 0\le x\le1.
$$

每个父单元保存的独立守恒变量取为

$$
\boldsymbol{q}
=
\left(
u_{\rm tot},
x_{\rm HII},
x_{\rm HeII},
x_{\rm HeIII}
\right).
$$

中性级由元素粒子数约束导出，而不是再独立推进：

$$
x_{\rm HI}=1-x_{\rm HII},
\qquad
x_{\rm HeI}=1-x_{\rm HeII}-x_{\rm HeIII}.
$$

第 $j$ 个父单元内第 $s$ 个子单元的线性状态为

$$
\boldsymbol{q}_{j,s}
=
\overline{\boldsymbol{q}}_{j}
+
\theta_{j}\boldsymbol{\sigma}_{j}
\left(x_{j,s}-x_{j}\right),
$$

其中斜率使用 minmod 限制；父单元两端用单边斜率。由于子单元中心关于父单元质量中心满足

$$
\sum_{s}
\frac{\Delta x_{j,s}}{\Delta x_{j}}
\left(x_{j,s}-x_{j}\right)=0,
$$

因此延拓严格回收父平均：

$$
\sum_{s}
\frac{\Delta x_{j,s}}{\Delta x_{j}}
\boldsymbol{q}_{j,s}
=
\overline{\boldsymbol{q}}_{j}.
$$

这也适用于严格嵌套但父单元内部不等宽的子网格。`[V]`

## 3. 物理域限制与温度反演

公共凸限制因子 $0\le\theta_{j}\le1$ 同时施加以下约束：

$$
0\le x_{\rm HII}\le1,
$$

$$
x_{\rm HeII}\ge0,
\qquad
x_{\rm HeIII}\ge0,
\qquad
x_{\rm HeII}+x_{\rm HeIII}\le1,
$$

以及正的热能

$$
u_{\rm tot}-u_{\rm ion}>0.
$$

当解析限制恰落在浮点边界上时，代码只用 `np.nextafter` 向凸域内部移动一个浮点间隔；这是
数值上表达严格不等式，不是温度、布居或 opacity 的物理 floor。任何父状态本身越界都会
直接报错。`[A/V]`

子单元温度不由插值给出，而是从守恒总比能反演。当前基态 H/He 热力学满足

$$
u_{\rm tot}
=
u_{\rm ion}
+
\frac{3}{2}k_{\rm B}
\left(
\frac{n_{\rm nuc}}{\rho}
+
\frac{n_{e}}{\rho}
\right)T
+
\frac{a_{\rm rad}}{\rho}T^{4},
\qquad
a_{\rm rad}=\frac{4\sigma_{\rm SB}}{c}.
$$

给定密度和布居后，右端对 $T>0$ 严格单调，所以可用括区间求根得到唯一正温度；代码没有
设置温度 floor。三组独立状态的往返反演最大相对误差为
$1.323\times10^{-16}$。`[V]`

## 4. 动态限制与守恒账本

延拓后的每个子单元由既有周期动态求解器独立推进。限制回父单元时，粒子数、总比能和
Rosseland opacity 都按单元质量加权：

$$
\overline{q}_{j}
=
\sum_{s}
\frac{\Delta m_{j,s}}{\Delta m_{j}}q_{j,s}.
$$

父单元面通量直接取相同位置的子单元面通量。内部子单元面的通量散度望远镜相消：

$$
\sum_{s}
\left(F_{j,s+1/2}-F_{j,s-1/2}\right)
=
F_{j+1/2}-F_{j-1/2}.
$$

因此该操作不需要删除失败相位或事后重归一化。三档正式算例中，初态和限制后的质量、总
元素粒子数、各离化级、电荷、总比能、光深及面通量散度残差均低于
$1.32\times10^{-15}$；周期能量账本最大相对残差为 $1.20\times10^{-12}$。`[V]`

### 4.1 为什么守恒诊断曾出现假失败

第一次报告把接近零的单个离化级也写成对称相对误差。约 $10^{-16}$ 的绝对舍入差除以同量级
布居后会被放大，尤其使 He 级误报为百分数误差。正式诊断现区分：

- 总 H/He 粒子数使用相对残差；
- 单个离化级使用绝对布居残差。

初态由声明输入重新构造。已保存的耗时动力学解没有重跑；旧的非负布居对称相对残差
$r$ 严格上界单级绝对误差，而 $2r$ 和 $3r$ 分别上界 H、He 总级误差，所以报告保留这些
更保守的上界并显式记录 `dynamics_recomputed=false`。这只修正诊断归一化，不改变任何物理
状态或空间收敛结果。`[V]`

## 5. 制造前沿控制

制造解使用宽度 $w=0.08$、在 $x_{\rm f}=0.15$--$0.85$ 间移动的 He III 前沿：

$$
x_{\rm HeIII}(x)
=
\frac{1}{2}
\left[
1-\tanh\left(\frac{x-x_{\rm f}}{w}\right)
\right].
$$

父单元平均由解析反导函数计算，不用点采样冒充体积平均。8 个父单元各分为 4 个子单元时：

| 指标 | 父单元常数 | 受限子单元 | 改善倍数 |
|---|---:|---:|---:|
| 平均绝对误差 | $3.1146\times10^{-2}$ | $1.6394\times10^{-2}$ | $1.900$ |
| 最大绝对误差 | $2.6744\times10^{-1}$ | $1.3844\times10^{-1}$ | $1.932$ |

制造前沿和父平均守恒控制都通过。`[V]`

![Phase 7B4l conservative subcell controls](../outputs/phase7b4l_subcell_controls.png)

- `(a)` 黑线是解析前沿，红阶梯是父单元常数，蓝点是受限子单元；蓝点能恢复前沿斜率，但
  仍是有限分辨率表示。`[V]`
- `(b)` 扫过完整质量柱时，子单元平均绝对误差在每个前沿位置都低于父单元常数。`[V]`
- `(c)` 显示公共凸限制因子；只在前沿靠近边界、外推可能越出人口单纯形时收缩斜率。`[V]`
- `(d)` 父平均与能量--温度往返残差均处于浮点舍入量级。`[V]`

## 6. 正式 ZO 深度审计

空间审计沿用 Phase 7B4k 的轨道全局监视函数，构造一个 64 单元主网格。父单元数取
8、16、32，每个父单元保留 2 个真实子单元，对应有效深度数 16、32、64；64 单元解只是
本轮有限分辨率参考，不是连续极限。空间轴隔离计算使用 64 个轨道相位和 71 个频率点，已
通过的 1024 对 2048 时间门则继承自 Phase 7B4k。`[A/V]`

生产分类预先要求 32 单元相对 64 单元的表面能流、逐点温度/opacity、逐点人口、柱平均
温度/opacity、柱平均人口和 He III 半高前沿位置误差都低于 $10^{-3}$，并且前沿状态失配
相位数为零。`[A-classification]`

| 有效深度数 | 表面能流相对误差 | 逐点 $T/\kappa_{\rm R}$ 相对误差 | 逐点人口绝对误差 | 柱平均 $T/\kappa_{\rm R}$ 相对误差 | 柱平均人口绝对误差 | 前沿失配相位数 | 前沿位置误差 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | $4.864\times10^{-4}$ | $2.605\times10^{-2}$ | $0.2114$ | $1.512\times10^{-3}$ | $2.842\times10^{-3}$ | 2 | $1.739\times10^{-3}$ |
| 32 | $1.392\times10^{-4}$ | $1.520\times10^{-2}$ | $0.1132$ | $3.131\times10^{-4}$ | $5.755\times10^{-4}$ | 0 | $4.471\times10^{-4}$ |
| 64 | 当前参考 | 当前参考 | 当前参考 | 当前参考 | 当前参考 | 0 | 当前参考 |

32 单元解的表面能流、柱平均量和前沿位置已经通过，但逐点温度/opacity 误差仍为 $1.52\%$，
逐点人口绝对误差仍为 $0.113$。因此固定每父单元 2 个子单元没有关闭空间生产门。它改善了
单元内表示，却没有消除移动电离前沿所需的局部自由度不足。`[V/O]`

![Phase 7B4l retained subcell depth convergence](../outputs/phase7b4l_subcell_convergence.png)

- `(a)` 展示梯度最强相位的 He III 前沿；曲线在大部分柱内重合，但表面附近的窄跃迁控制
  最大范数。`[V]`
- `(b)` 三档表面能流响应几乎重合，说明全局能流比局部布居更早收敛。`[V]`
- `(c)` 逐点两项误差随 16 到 32 单元下降，却仍显著高于 $10^{-3}$ 目标；这就是正式失败项。
  `[V/O]`
- `(d)` 柱平均热力学、柱平均人口和前沿位置在 32 单元时都低于目标，清楚显示“积分量通过”
  不等于“局域状态通过”。`[V]`

## 7. 阶段判据

| 判据 | 结果 |
|---|---|
| 制造前沿相对父常数表示改善 | 通过 `[V]` |
| 父平均、能量反演和动态限制守恒 | 通过 `[V]` |
| 1024 对 2048 相位时间门 | 通过，继承 Phase 7B4k `[A-classification/V]` |
| 32 对 64 有效深度生产门 | 失败 `[V/O]` |
| 联合深度--时间参考 | 不获准 `[O]` |
| 非局域频率依赖动态转移 | 不获准 `[O]` |
| Phase 4 大气替换与 UVOT | 不获准 `[O]` |

下一微阶段是 **Phase 7B4m：前沿感知的可变子单元细化与嵌入式保守误差估计**。它应保留
已经验证的 1024 相位时间目标，只在嵌入式误差要求处增加真实有限体积自由度，并独立报告
成本与局域/积分误差。只有空间门通过后，才允许联合 1024 相位参考；联合门通过后，才进入
非局域、频率依赖的动态转移。`[V/O]`

后续结果见
[[eccentric_tde_observer/docs/phase7b4m_front_aware_variable_refinement|Phase 7B4m 报告]]：
可变 60 与 62 层候选已通过对有限 64 层参考的空间门，但联合 64 深度、1024 相位参考仍只
获得准入、尚未执行。`[V/O]`

本阶段没有使用 `nan_to_num`、任意 `clip`、任意 floor、删除失败相位或事后物理
重归一化。子单元定向测试为 `6 passed in 4.47s`，合入后全项目现场回归为
`312 passed in 42.97s`。`[V]`

## 8. 产物

- `src/eccentric_tde_observer/subcell_reconstruction.py`；
- `tests/test_subcell_reconstruction.py`；
- `scripts/phase7b4l_conservative_subcell_reconstruction.py`；
- `outputs/phase7b4l_control_report.json`；
- `outputs/phase7b4l_subcell_report.json`；
- `outputs/phase7b4l_complete_report.json`；
- `outputs/phase7b4l_manufactured_front.csv`；
- `outputs/phase7b4l_subcell_edges.csv`；
- `outputs/phase7b4l_subcell_profiles.csv`；
- `outputs/phase7b4l_subcell_convergence.csv`；
- `outputs/phase7b4l_subcell_controls.png`；
- `outputs/phase7b4l_subcell_convergence.png`。
