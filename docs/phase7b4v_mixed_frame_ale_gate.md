# Phase 7B4v：完整 Lorentz 物质源与 ALE 联立门

> [!abstract] 本阶段结论
> Phase 7B4v 续接
> [[eccentric_tde_observer/docs/phase7b4t_mixed_frame_group_gate|Phase 7B4t]] 与
> [[eccentric_tde_observer/docs/phase7b4u_multigroup_continuum_gate|Phase 7B4u]]。
> 完整 Lorentz 物质碰撞算子已经与 ALE 储能、空间通量写入同一后向 Euler 残差；零速度、
> 刚体平移、同源呼吸和 $\beta\tau=2$ 动态扩散四力控制全部通过。[V]
> 但 1205 个分段常数物理频率组在三个真实一步物态上的最大误差为
> $1.2829\times10^{-2}$，没有通过 $10^{-3}$ 动态原子率门。[V]
> 当前没有选出可用于全轨道的动态频率组数；下一步应先改进组内频谱表示或阈值局域重构，
> 不能直接启动 2048 相位全轨道。[A-classification/O]

证据标签沿用项目约定：[L] 文献或基本关系，[V] 代码验证，[A] 工作假设或数值分类，
[O] 尚未关闭的问题。

## 1. 本阶段真正联立了什么

实验室系中的逐组、逐方向 ALE 方程写成

$$
\frac{
\Delta z_{j}^{n+1}I_{g,m,j}^{n+1}
-\Delta z_{j}^{n}I_{g,m,j}^{n}
}{\Delta t}
+
\left[
\left(c\mu_{m}-w\right)I_{g,m}^{n+1}
\right]_{j+1/2}
-
\left[
\left(c\mu_{m}-w\right)I_{g,m}^{n+1}
\right]_{j-1/2}
=
c\Delta z_{j}^{n+1}
\left(
\eta_{g,m}^{\rm lab}
-\chi_{g,m}^{\rm lab}I_{g,m,j}^{n+1}
\right).
$$

左边仍是 Phase 7B4s 已验证的实验室系储能与移动界面通量；右边不再使用静止介质
$\chi(B-I)$ 近似，而是由完整 Lorentz 往返得到。[A/V]

对物质速度 $\beta c$，实验室系到共动系的 Doppler 因子为

$$
D
=
\frac{\nu_{0}}{\nu}
=
\gamma\left(1-\beta\mu\right),
\qquad
\mu_{0}
=
\frac{\mu-\beta}{1-\beta\mu}.
$$

代码先用 Phase 7B4t 的守恒组搬移求 $I_{0,g,m}$ 与

$$
J_{0,g}
=
\frac{1}{2}
\sum_{m}w_{m,0}I_{0,g,m},
\qquad
w_{m,0}
=
\frac{w_{m}}{D_{m}^{2}}.
$$

共动系中的规定物质碰撞源为

$$
\eta_{0,g,m}
=
\eta_{0,g}^{\rm th}
+\chi_{0,g}^{\rm s}J_{0,g},
\qquad
\chi_{0,g}
=
\chi_{0,g}^{\rm a}
+\chi_{0,g}^{\rm s}.
$$

其中 $\chi_{0,g}^{\rm a}$、$\eta_{0,g}^{\rm th}$ 和 $\chi_{0,g}^{\rm s}$ 来自 Phase 7B4u
的 H/He 基态连续系数。温度与 H/He 布居仍是规定输入，不在本阶段反向更新。[A/O]

## 2. 为什么强度、发射率和消光不能共用同一个 Doppler 幂次

三个不变量分别是

$$
\frac{I_{\nu}}{\nu^{3}},
\qquad
\frac{\eta_{\nu}}{\nu^{2}},
\qquad
\chi_{\nu}\nu.
$$

因此共动系强度回到实验室系时，组积分使用 $D^{-4}$；共动系发射率回到实验室系时使用

$$
\bar\eta_{g,m}^{\rm lab}
=
\frac{D_{m}^{-3}}{\Delta\nu_{g}}
\int_{D_{m}\nu_{g-1/2}}^{D_{m}\nu_{g+1/2}}
\eta_{0,\nu}
\,\mathrm d\nu_{0},
$$

而消光系数使用

$$
\bar\chi_{g,m}^{\rm lab}
=
\frac{1}{\Delta\nu_{g}}
\int_{D_{m}\nu_{g-1/2}}^{D_{m}\nu_{g+1/2}}
\chi_{0,\nu}
\,\mathrm d\nu_{0}.
$$

这两个新接口分别回收常数发射率的 $D^{-2}$ 变换和常数消光的 $D$ 变换。[V]
若把强度的 $D^{-4}$ 机械套给物质系数，刚体移动热平衡和四力协变控制都会失败。

## 3. 三层频率网格与守护带

一次完整碰撞往返需要两次频率查询，因此本阶段区分：[A/V]

1. 1205 个 $0.1$--$5000\ {\rm eV}$ 物理实验室组；
2. 1207 个一次变换共动碰撞组；
3. 1209 个两次变换实验室源组。

守护组只为 Doppler 查询提供定义域，不计入正式物理频带积分。组件控制中的守护强度由
解析移动平衡或局域 Planck 场明确规定；它还不是全轨道自洽边界条件。[A/O]
任何查询越过外层守护带都会直接失败，不做端点外推、`clip`、floor 或重归一化。[V]

## 4. 解析和制造控制

三个 1205 组制造平衡结果为：[V]

| 控制 | 误差 | 全局联立残差 | 总能量账本残差 |
|---|---:|---:|---:|
| 零速度回到静止 ALE | $3.810\times10^{-14}$ | $4.081\times10^{-14}$ | $3.835\times10^{-14}$ |
| 刚体平移共动平衡 | $3.846\times10^{-15}$ | $3.327\times10^{-15}$ | $7.398\times10^{-18}$ |
| 单元同源呼吸平衡 | $1.534\times10^{-14}$ | $2.331\times10^{-14}$ | $3.149\times10^{-17}$ |

动态扩散压力控制采用紧支撑的各向异性共动谱、$\beta=0.05$、纯相干散射光深
$\tau=40$，所以 $\beta\tau=2>1$。它不依赖一阶 $v/c$ 展开。[A/V]

对辐射碰撞四力，代码独立检查

$$
S_{\rm E}^{\rm lab}
=
\gamma
\left(
S_{\rm E}^{0}
+\beta cS_{\rm P}^{0}
\right),
$$

$$
S_{\rm P}^{\rm lab}
=
\gamma
\left(
S_{\rm P}^{0}
+\frac{\beta}{c}S_{\rm E}^{0}
\right).
$$

S4、S8、S16 的能量四力误差为 $2.10\times10^{-13}$、$3.25\times10^{-13}$、
$6.26\times10^{-13}$；动量四力误差均低于 $2.8\times10^{-14}$。三个角阶的全局联立
残差约 $10^{-10}$，总能量账本残差约 $3.0$--$3.5\times10^{-9}$，全部通过预声明门。[V]

![Phase 7B4v mixed-frame ALE controls](../outputs/phase7b4v_mixed_frame_ale_controls.png)

**左上。** 零速度、刚体移动和同源呼吸都远低于 $10^{-3}$ 制造平衡门，说明 ALE 网格速度
与物质 Lorentz 速度没有被混为同一个量。[V]

**右上。** 在 $\beta\tau=2$ 时，完整四力协变误差仍接近浮点精度；这只验证完整算子，
不表示 S4 已经是实际大气的正式角分辨率。[V/O]

**左下。** 真实最冷表层的 1205 组一步计算，其全局联立残差、频带积分能量账本和固定点
变化全部低于门。算子能解并不等于频率表示已收敛。[V]

**右下。** 图保留约 $600\ {\rm eV}$ 处接近 1 的逐组相对残差。对应强度已经进入
`float64` 次正规数范围；没有用 floor 抬高，也没有删除这些组。全局方程残差和频带积分
账本仍约 $10^{-11}$，因此报告同时保留“全局通过”和“逐组高能尾相对量失去意义”两件事。
[V]

## 5. 三个真实一步物态

实际门使用 N128×2048 规定物质轨道中的三个独立压力状态：[A/V]

1. Phase 1024 到 1025 的最冷表层，即 Phase 7B4u 的系数最坏状态；
2. Phase 1367 到 1368 的最大单元速度状态，$|\beta|=7.546\times10^{-3}$；
3. Phase 628 到 629 的最大单元宽度变化状态，$|\beta|=5.000\times10^{-3}$。

每个状态都只推进一个真实拉格朗日表层单元；这仍是组件压力测试，不是全柱或全轨道。[A]
1205 组计算的最大光深依次约为 $1.395\times10^{5}$、$3.036\times10^{4}$ 和
$5.484\times10^{2}$，全局联立残差不超过 $3.59\times10^{-11}$，频带积分能量账本不超过
$1.29\times10^{-10}$。[V]

## 6. 1205 组为什么失败

原计划先用 2408 组有限参考检查 1205 组；发现失败后，没有放宽 $10^{-3}$ 门，而是继续
保留 4814、9625、19249 和 38496 组结果。[A/V]

相对 38496 组有限参考，最大误差为：[V]

| 真实状态 | 1205 组 | 9625 组 | 19249 组 | 主导失败量 |
|---|---:|---:|---:|---|
| 最冷系数表层 | $1.874\times10^{-4}$ | $1.248\times10^{-5}$ | $6.084\times10^{-6}$ | He I/H I 光致率 |
| 最大单元速度 | $5.020\times10^{-3}$ | $6.550\times10^{-4}$ | $2.886\times10^{-4}$ | H I/He II 光致率 |
| 最大宽度变化 | $1.2829\times10^{-2}$ | $1.437\times10^{-3}$ | $5.318\times10^{-4}$ | H I 光致率 |

因此：[V/O]

- 1205 组在最冷静态系数门通过，不代表动态 $J_{0,\nu}$ 的组内形状也已收敛；
- 最慢收敛的是 H I 光致电离率，不是总辐射能或 ALE 能量账本；
- 9625 组在最大宽度变化状态仍失败；
- 19249 组只相对有限 38496 组参考通过，不能称为连续频率极限；
- 直接选择 19249 组做 N128×2048×S16 全轨道会造成不合理代价，因此当前不选生产组数。

![Phase 7B4v actual-state frequency convergence](../outputs/phase7b4v_actual_state_convergence.png)

**左图。** 三个真实状态的误差随频率组数下降，但速度和宽度压力状态明显慢于最冷系数
状态；水平虚线保持 $10^{-3}$，失败点没有删除。[V]

**中图。** 1205 组最显著的误差集中在 H I 光致率；辐射总能、He 率和净加热通常小得多。
这说明下一步应改善阈值附近动态强度的组内表示，而不是重写已经闭合的 ALE 能量账本。[V]

**右图。** 单元组件成本近似随频率组数增长。19249 组的一单元通过不能外推成全柱全轨道
可行性；正式路线应优先测试守恒 P1/矩重构或阈值局域子组，而不是暴力采用约两万组。[A/O]

## 7. 阶段决定

Phase 7B4v 的结论必须拆成两层：[A-classification/V/O]

1. **完整 Lorentz--ALE 算子门通过。** 零速度、刚体平移、同源呼吸、动态扩散四力、正性、
   全局残差和能量账本均通过；
2. **1205 组完整组件门失败。** 三个真实一步状态中的最坏动态原子率误差为
   $1.2829\times10^{-2}$；
3. 19249 组只在三个单元状态上相对 38496 组有限参考通过，不获生产选择；
4. 当前正式动态频率组数为“未选定”；
5. S16/S24、16/32 辐射子网格和 2048 相位全轨道都不获准；
6. 温度--布居反馈、Phase 4 替换、UVOT、Cloudy 与真实线形成继续不获准。

下一数值问题已经由本阶段确定：在守恒 Doppler 搬移和正性不被破坏的前提下，检验组内
线性频谱矩、阈值局域子组或等价的自适应频率表示，目标是在远少于约两万组时同时回收
动态 $J_{0,\nu}$、H/He 光致率和能量账本。[O]

## 8. 文件与复现

核心文件：

- `src/eccentric_tde_observer/mixed_frame_ale.py`：三层频率守护、完整 Lorentz 物质源、
  正性 ALE 扫掠、联立残差、能量账本与四力诊断；
- `src/eccentric_tde_observer/mixed_frame_frequency.py`：新增发射率和消光系数各自的组搬移；
- `scripts/phase7b4v_mixed_frame_ale_gate.py`：制造控制、动态扩散、真实状态加密、图表和判定；
- `tests/test_mixed_frame_ale.py`：零速度、移动平衡、动态扩散和禁修补测试；
- `tests/test_phase7b4v_mixed_frame_ale_gate.py`：频率组数、阶段失败保留和授权边界回归；
- `outputs/phase7b4v_summary.json`：机器可读阶段结论；
- `outputs/phase7b4v_controls.csv`、`outputs/phase7b4v_dynamic_diffusion.csv`：解析控制；
- `outputs/phase7b4v_actual_states.csv`、`outputs/phase7b4v_actual_state_convergence.csv`：
  真实一步状态与频率加密；
- `outputs/phase7b4v_diagnostics.npz`：未设 floor 的逐组残差；
- `outputs/phase7b4v_mixed_frame_ale_controls.png`、
  `outputs/phase7b4v_actual_state_convergence.png`：全英文图件。

运行：

~~~bash
.venv/bin/python scripts/phase7b4v_mixed_frame_ale_gate.py --force
~~~

不加 `--force` 时，如果全部阶段产物存在，脚本只复用当前结果。[V]

## 9. 测试与代码审计

定向测试覆盖 Lorentz 发射率/消光搬移、零速度回归、移动平衡、动态扩散四力、三层频率
守护、失败结论保留和 Markdown 公式规范；结果为 `19 passed`。随后运行完整测试
套件，现场结果为 `390 passed in 56.04s`。[V]

新代码通过 `compileall` 与公共导出唯一性检查；`mixed_frame_ale.py` 和阶段脚本中没有
`nan_to_num`、`np.clip`、任意物理 floor、删点或事后重归一化。禁用接口名只出现在
回归测试的源码扫描断言中。[V]
