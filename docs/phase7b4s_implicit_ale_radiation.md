# Phase 7B4s：隐式 ALE 辐射储能核与 N128 双频 pilot

> [!abstract] 本阶段定位
> Phase 7B4s 续接
> [[eccentric_tde_observer/docs/phase7b4r_n128_time_reference|Phase 7B4r]]，先在规定的
> N128×2048 物质轨道上加入真正的辐射储能和非局域输运。它通过解析极限、移动网格守恒
> 和双频周期 pilot，但还没有速度引起的频率--角度耦合，也没有把辐射反馈给温度与布居；
> 因此它是动态转移核门，不是可替换 Phase 4 的动态 NLTE 连续谱。

证据标签沿用项目约定：[L] 文献或基本关系，[V] 代码验证，[A] 工作假设或受控 pilot，
[O] 尚未关闭的问题。

## 1. 为什么不能沿用显式静止网格核

[[eccentric_tde_observer/docs/phase7b4p_frozen_nonlocal_transfer|Phase 7B4p]] 已测得

$$
\max\left(\frac{t_{\rm diff}}{P_{\rm orb}}\right)=0.7379,
$$

所以逐相位静态形式解不能代表整个轨道。Phase 7B2 的时间依赖控制核虽有辐射储能，但空间
输运是显式迎风，真实光速下受 CFL 限制，而且只接受静止均匀网格。[V]

N128×2048 轨道的完整双面柱有 256 个物质单元。若采用 Phase 7B4q 已通过的每个物质单元
16 个辐射子单元和 16 个方向，则每个频率有 65536 个强度未知量；160 个阈值求积频率的
直接全轨道显式推进不具可行性。256 个物质单元网格的最小显式 CFL 步长已只有
$0.7098\ {\rm s}$，即一个 $4.160\times10^{6}\ {\rm s}$ 轨道至少需要
$5.86\times10^{6}$ 个输运步；正式 16 倍辐射子网格的对应下限约为
$0.04436\ {\rm s}$ 和 $9.38\times10^{7}$ 步/轨道。[V]

[Jiang 2021](https://arxiv.org/abs/2102.02212) 展示了把离散纵标空间输运和气体--辐射源项
同时隐式化以解除光速时间步限制的有限体积路线；
[Jiang, Stone & Davis 2014](https://arxiv.org/abs/1403.6126) 则强调沿每条离散射线守恒离散，
并在混合系中处理速度源项。[L] 本阶段采用前者的“实验室系强度 + 全隐式守恒输运”骨架，
但暂不声称已经实现论文的完整速度变换。[A/O]

## 2. 本阶段求解的方程

静止介质的实验室系一维方程写成

$$
\frac{1}{c}\frac{\partial I_{\nu}}{\partial t}
+\mu\frac{\partial I_{\nu}}{\partial z}
=
\chi_{\nu,\rm a}\left(B_{\nu}-I_{\nu}\right)
+\chi_{\nu,\rm s}\left(J_{\nu}-I_{\nu}\right),
$$

其中

$$
J_{\nu}
=
\frac{1}{2}\int_{-1}^{1}I_{\nu}\,\mathrm d\mu.
$$

ZO 半柱使用固定质量坐标，因此物理宽度随轨道呼吸。对边界速度为 $w_{j+1/2}$ 的移动控制
体，代码推进守恒 ALE 形式

$$
\frac{
\Delta z_{j}^{n+1}I_{\nu,m,j}^{n+1}
-\Delta z_{j}^{n}I_{\nu,m,j}^{n}
}{\Delta t}
+\left[
\left(c\mu_{m}-w\right)I_{\nu,m}^{n+1}
\right]_{j+1/2}
-\left[
\left(c\mu_{m}-w\right)I_{\nu,m}^{n+1}
\right]_{j-1/2}
=
c\Delta z_{j}^{n+1}
\left[
\chi_{\nu,\rm a}\left(B_{\nu}-I_{\nu,m}^{n+1}\right)
+\chi_{\nu,\rm s}\left(J_{\nu}^{n+1}-I_{\nu,m}^{n+1}\right)
\right].
$$

时间采用后向 Euler，界面强度按 $c\mu_{m}-w$ 单调迎风；吸收、热发射、相干各向同性
电子散射和空间输运进入同一个逐频率稀疏线性系统。没有通过强度裁剪维持正性；若解产生
负强度或非有限值，代码直接拒绝。[A/V]

### 2.1 离散能量账本

逐频率柱辐射能为

$$
\mathcal E_{\nu}
=
\frac{4\pi}{c}
\sum_{j}J_{\nu,j}\Delta z_{j},
$$

ALE 边界能流为

$$
\mathcal F_{\nu,\rm ALE}
=
2\pi\sum_{m}w_{m}
\left(\mu_{m}-\frac{w}{c}\right)
I_{\nu,m}^{\rm up},
$$

物质吸热为

$$
\mathcal Q_{\nu,\rm mat}
=
4\pi\sum_{j}
\chi_{\nu,\rm a,j}
\left(J_{\nu,j}-B_{\nu,j}\right)
\Delta z_{j}.
$$

每一步直接检查

$$
\Delta\mathcal E_{\nu}
+\Delta t
\left(
\mathcal F_{\nu,\rm ALE,\rm R}
-\mathcal F_{\nu,\rm ALE,\rm L}
+\mathcal Q_{\nu,\rm mat}
\right)
=
\mathcal R_{\nu}.
$$

散射项在角积分中解析抵消，所以不能用“散射能量误差”掩盖线性求解误差。[V]

## 3. 移动网格审计

![Phase 7B4s ZO moving-grid audit](../outputs/phase7b4s_zo_mesh_motion.png)

- 左上：完整轨道的单侧几何厚度从 $4.074\times10^{12}\ {\rm cm}$ 变化到
  $1.541\times10^{14}\ {\rm cm}$，说明相邻相位不是同一个固定空间网格。[V]
- 右上：由 ZO 解析呼吸率得到的最大表面速度为 $0.00802865c$，由相邻网格端点得到的
  离散 ALE 速度为 $0.00802860c$。16 方向半区间求积的最小 $|\mu|=0.019855$，所以
  当前 S16 节点尚未发生相对传播方向反转；但 $v/c$ 已显著高于 $10^{-3}$ 精度目标，不能
  据此删除速度源项。[V/O]
- 左下：近心点五次幂聚集网格产生 $4.66\times10^{-10}$--$1.622\times10^{4}\ {\rm s}$
  的极不均匀步长。最小步长是数值采样坐标，不是新的物理时标；隐式系统在这些步上趋近
  恒等映射。[A/V]
- 右下：单步物理宽度最大只变化 $0.902\%$，但最细表层单元相邻边界的位移可达其宽度的
  $1.141$ 倍。因此不能把新旧柱按同一空间下标直接复制；守恒 ALE 体积分是必要的。[V]

解析端点速度与前向离散速度的最大归一化差为 $2.13\times10^{-3}$；这是有限时间步的
端点导数差，不是通过重定义 ZO 速度得到的“修正”。[V]

## 4. 解析与数值控制

![Phase 7B4s implicit ALE controls](../outputs/phase7b4s_implicit_controls.png)

- 左上：周期真空平流在 32、64、128 单元上的最大误差依次为
  $1.581\times10^{-3}$、$3.988\times10^{-4}$、$9.992\times10^{-5}$；加密后稳定下降。
- 右上：长时间隐式解与独立分层常源函数静态形式解的差从 N128 的 $0.05064$ 降到
  N512 的 $0.01498$。两者空间离散不同，图检验的是一致收敛，不把有限 N 差异删除。
- 左下：均匀吸收后向 Euler 解析误差为 $8.88\times10^{-16}$，移动网格几何守恒误差为
  $1.78\times10^{-15}$，纯散射周期能量误差为 $7.47\times10^{-14}$。
- 右下：N128 双频 pilot 第一周期相对初态改变 $0.0883$；第二周期端点与起点逐位一致。
  两周期最大能量账本残差均为 $1.424\times10^{-9}$，低于预声明的 $2\times10^{-8}$ 门。

这些控制共同验证了储能、输运、散射、移动体积和真空边界的离散骨架；它们没有验证完整
H/He 动态 NLTE 闭合。[V/O]

## 5. N128×2048 双频周期 pilot

pilot 直接使用 Phase 7B4r 的 128 个半柱质量单元、2048 个轨道相位、温度和基态 H/He
布居。为先隔离动态输运，只选择 10 eV 与 60 eV 两个诊断频率和 4 个方向；初态取第一相位
局域 $B_{\nu}$，随后迭代完整周期直到辐射端点闭合。[A]

![Phase 7B4s radiation-storage pilot](../outputs/phase7b4s_radiation_pilot.png)

- 左上：图画的是两个单色点的原始 $F_{\nu}$，不是频率求积后的 SED。10 eV 出射
  $F_{\nu}$ 在 $3.28\times10^{-4}$--$1.63\times10^{-2}$ 之间；60 eV 在远心点附近极弱，
  不能把两条曲线连成宽带谱。[A/V]
- 右上：10 eV 表层 $J_{\nu}/B_{\nu}$ 为 $0.495$--$61.2$，说明散射和深层输运可使表层
  场显著偏离局域 Planck 值；60 eV 为 $0.9976$--$1.0028$，在这个规定物质 pilot 中被
  强吸收/发射耦合锁近局域值。[V]
- 左下：中面 10 eV 的 $J_{\nu}/B_{\nu}$ 为 $0.945$--$0.998$，展示有限但可分辨的辐射记忆；
  60 eV 几乎局域。频率行为不同，正是不能用单一 modified-blackbody 稀释因子代替
  非局域频率转移的直接数值例子。[V]
- 右下：2048 个相位的逐步能量残差全部低于 $2\times10^{-8}$；最大值为
  $1.424\times10^{-9}$。双面出射通量最大相对不对称仅 $3.70\times10^{-14}$。[V]

pilot 运行两个周期，共约 $20.5\ {\rm s}$；最大线性系统残差为 $2.821\times10^{-13}$。
它证明完整 N128 物质轨道可承载隐式辐射状态，但两个频率、四方向和物质单元深度不构成
任何频率、角度或辐射子网格收敛结论。[A/V/O]

## 6. ALE 已处理什么，尚未处理什么

ALE 中的 $w$ 只保证移动控制体的几何守恒；它不是物质源项的 Lorentz 变换。当前代码仍把
$\chi_{\nu}$、$B_{\nu}$ 和相干散射源按静止介质形式放入实验室系方程，因此缺少：[O]

1. $O(v/c)$ 或完整 Lorentz 的频率漂移与角度像差；
2. 辐射压力在压缩/膨胀中的功交换；
3. 不同频率格点之间由速度产生的耦合；
4. 动态 $J_{\nu}$ 对温度、H/He 布居和 opacity 的反向反馈。

本轨道最大 $v/c=8.03\times10^{-3}$。即便 S16 掠射节点尚未反向，忽略速度项的先验误差
尺度也高于项目优先追求的 $10^{-3}$，所以 Phase 7B4s 不能授权完整动态非局域谱。
[A-classification/V/O]

## 7. 阶段决定与下一小阶段

Phase 7B4s 的隐式 ALE 核门通过：[V]

1. 后向 Euler 吸收解析极限通过；
2. 纯散射和移动网格几何守恒通过；
3. 真空平流与冻结形式解随深度加密收敛；
4. N128×2048 双频周期储能 pilot 通过周期、线性系统、能量和镜像门；
5. 真实光速显式全轨道路线在物质网格上已需至少 $5.86\times10^{6}$ 个 CFL 步，在
   正式 16 倍辐射子网格上约需 $9.38\times10^{7}$ 步，因而被拒绝。

下一小阶段应先实现并验证混合系速度源项，同时把逐频率直接稀疏 LU 改成可扩展的块扫描或
Jiang 类迭代器；随后才把 160 点阈值求积、16/24 方向和 16/32 辐射子单元收敛重新接回。
只有规定物质轨道的全频动态转移通过，才允许联立温度与基态布居反馈。[O]

本阶段仍不授权：生成正式动态连续谱、替换 Phase 4、进入 UVOT、调用 Cloudy、解释真实
TDE 的 X-ray/optical 比，或把双频曲线称为 H/He NLTE 输出谱。[O]

## 8. 文件与复现

核心文件：

- src/eccentric_tde_observer/implicit_radiative_transfer_1d.py：隐式 ALE 离散纵标步和能量账本；
- scripts/phase7b4s_implicit_ale_radiation.py：解析控制、网格审计、双频周期 pilot 和英文图；
- tests/test_implicit_radiative_transfer_1d.py：吸收、散射、ALE、平流、冻结回归和守恒测试；
- tests/test_phase7b4s_implicit_ale_radiation.py：质量镜像、阶段控制和开放物理边界测试；
- outputs/phase7b4s_two_frequency_pilot.npz：双频周期 $J_{\nu}$、出射诊断和最终强度；
- outputs/phase7b4s_summary.json：机器可读阶段判定；
- outputs/phase7b4s_controls.csv、outputs/phase7b4s_mesh_audit.csv、
  outputs/phase7b4s_pilot_cycles.csv、outputs/phase7b4s_pilot_phase.csv：数值证据表；
- outputs/phase7b4s_implicit_controls.png、outputs/phase7b4s_zo_mesh_motion.png、
  outputs/phase7b4s_radiation_pilot.png：英文图件。

复用已有成品可运行：

~~~bash
.venv/bin/python scripts/phase7b4s_implicit_ale_radiation.py
~~~

只有显式加入 `--force` 才会重算并覆盖本阶段对应产物。[V]
