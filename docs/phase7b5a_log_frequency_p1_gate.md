# Phase 7B5a：对数频率守恒 P1 未关闭 H I 动态率门

> [!summary] 阶段结论
> `[A/V/O]` Phase 7B5a 不再只把组边界均匀放在对数频率上，而是把
> $y=\ln\nu$ 本身作为有限体积坐标，并保存 $Q=\nu I_{\nu}$ 的组平均和一次矩。
> Lorentz Doppler 搬移因此成为 $y$ 上的平移。解析平移、零速度、移动平衡、H/He
> 光致率 Jacobian 和总能量账本均通过独立回归。但在与 Phase 7B4x 相同的 4816 个
> 频谱自由度预算内，最大宽度变化状态的 H I 光致电离率误差仍为
> $2.4569\times10^{-3}$；相对普通 P1 的 $2.4547\times10^{-3}$ 没有实质改善。
> 因此 log-P1 不获生产授权，也不授权角度、辐射子网格、整轨道或物质反馈扩展。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b4x_p1_frequency_moments|Phase 7B4x 普通 P1]] ·
[[eccentric_tde_observer/docs/phase7b4z_p2_frequency_moments|Phase 7B4z P2]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

---

## 1. “对数网格”与“对数坐标表示”不是一回事

Phase 7B4x 的组边界本来就近似均匀分布在 $\ln\nu$ 上，但每个控制体内部仍把谱密度写成
$\nu$ 的线性函数。Phase 7B5a 改变的是守恒变量和组内坐标，而不只是边界位置：[A/V]

$$
y=\ln\nu,
\qquad
Q(y)=\nu q_{\nu}.
$$

于是物理频率积分严格变为

$$
\int q_{\nu}\,{\rm d}\nu
=
\int Q(y)\,{\rm d}y.
$$

在每个 $y$ 控制体中定义

$$
x=\frac{2(y-y_{\rm c})}{\Delta y},
\qquad
\bar Q=\frac{1}{\Delta y}\int Q\,{\rm d}y,
$$

$$
m=\frac{1}{\Delta y}\int Qx\,{\rm d}y,
\qquad
Q(x)=\bar Q+3mx.
$$

非负可实现条件仍为

$$
3|m|\leq\bar Q.
$$

limiter 保持 $\bar Q$ 不变，只限制未解析斜率 $m$；因此每个组的物理积分
$\Delta y\,\bar Q$ 不变。实现没有强度 floor、`clip`、`nan_to_num` 或事后重归一化。
[A/V]

## 2. Lorentz 变换为什么更简单

令

$$
D=\frac{\nu_{0}}{\nu},
$$

其中下标 0 表示共动系。Doppler 频移满足

$$
y_{0}=y+\ln D.
$$

因此频率映射只是在 $y$ 轴上平移，不再伸缩组内多项式。由标准不变量

$$
\frac{I_{\nu}}{\nu^{3}},
\qquad
\frac{\eta_{\nu}}{\nu^{2}},
\qquad
\chi_{\nu}\nu
$$

得到本阶段守恒密度的振幅变换

$$
Q_{\rm I,0}=D^{4}Q_{\rm I},
\qquad
Q_{\eta,0}=D^{3}Q_{\eta},
\qquad
\chi_{0}=\frac{\chi}{D}.
$$

代码在每个源段与目标段的 $y$ 交叠上解析积分 P1 的零阶和一次矩。守护组不足时直接拒绝，
没有把查询位置裁剪回边界。[V]

## 3. H/He 率和能量积分中的 Jacobian

辐射变量是

$$
Q_{\rm J}=\nu J_{\nu},
\qquad
J_{\nu}=\frac{Q_{\rm J}}{\nu},
\qquad
{\rm d}\nu=\nu\,{\rm d}y.
$$

因此离子 $i$ 的光致电离率写成

$$
\Gamma_{i}
=
4\pi\int
\frac{J_{\nu}\sigma_{i}(\nu)}{h\nu}
\,{\rm d}\nu
=
4\pi\int
\frac{Q_{\rm J}\sigma_{i}(\nu)}{h\nu}
\,{\rm d}y.
$$

吸收功率和热发射功率则分别为

$$
P_{\rm abs}=4\pi\int\chi_{\nu}^{\rm abs}Q_{\rm J}\,{\rm d}y,
$$

$$
P_{\rm em}=4\pi\int Q_{\eta}^{\rm th}\,{\rm d}y,
\qquad
Q_{\eta}^{\rm th}=\nu\eta_{\nu}^{\rm th}.
$$

所有节点率仍使用同一套 Verner 基态截面和 Milne 发射；改变的是谱表示，不是原子模型。
[L/A/V]

## 4. 独立解析与算子控制

专项测试回收了：[V]

1. 全局线性 $Q(y)$ 在有限 Doppler 平移后的解析组平均和一次矩；
2. $D=1$ 时两个 P1 矩逐位保持；
3. 两个对数频率 Gauss 节点的正性与组积分；
4. 零速度时两个节点分别等于两个独立静态 ALE 解；
5. 粗网格 Planck/LTE 的 H/He 光致率和能量平衡；
6. 刚体移动、共动常数 $Q_{0}$ 平衡；
7. 源代码禁用修补审计。

移动平衡控制采用

$$
Q_{\rm lab}=D^{-4}Q_{0}.
$$

得到平衡误差 $1.0350\times10^{-14}$、联立残差 $5.9299\times10^{-16}$、总能量
账本残差 $1.1360\times10^{-16}$，最终 limiter 为 0。[V]

这些结果验证了坐标、Doppler 幂次和积分测度，但不能替代真实状态的有限分辨率门。[V/O]

## 5. 三个真实一步状态

物理频带、S8 角求积、每组 16 点物理求积、三个实际物态、38496 组 P0 有限参考、
$10^{-3}$ 误差门和 4816 个频谱自由度上限均与 Phase 7B4x 相同。[A/V]

| 物理组数 | 频谱自由度 | 最冷表层最大误差 | 最大速度最大误差 | 最大宽度变化最大误差 |
|---:|---:|---:|---:|---:|
| 153 | 306 | $6.3878\times10^{-5}$ | $8.0759\times10^{-3}$ | $1.8047\times10^{-2}$ |
| 303 | 606 | $1.8487\times10^{-5}$ | $6.0897\times10^{-3}$ | $1.4197\times10^{-2}$ |
| 604 | 1208 | $1.8244\times10^{-5}$ | $3.6442\times10^{-3}$ | $9.5391\times10^{-3}$ |
| 1205 | 2410 | $1.7162\times10^{-5}$ | $1.9217\times10^{-3}$ | $5.1160\times10^{-3}$ |
| 2408 | 4816 | $1.5071\times10^{-5}$ | $9.0431\times10^{-4}$ | $2.4569\times10^{-3}$ |

![Phase 7B5a log-P1 frequency convergence](../outputs/phase7b5a_log_p1_frequency_convergence.png)

**左图。** 最冷表层在全部候选上通过。最大速度状态只在 2408 组越过黑色
$10^{-3}$ 门；最大宽度变化状态在同一预算仍高于门约 2.46 倍。三条曲线总体下降，
不存在因为单个异常 bin 造成的假失败。[V]

**右图。** 最高预算下，最大宽度变化状态唯一明显越门的分量仍是 H I 光致电离率；
能量、左右通量、He I/He II 率和净加热都更小。结论不是由总能量单位变换造成的。[V]

## 6. 残差、limiter 和成本

![Phase 7B5a log-P1 operator diagnostics](../outputs/phase7b5a_log_p1_operator_diagnostics.png)

**左上。** 最冷表层 153 组的联立残差为 $1.4082\times10^{-6}$，高于预声明的
$2\times10^{-8}$；其余候选约为 $7.74\times10^{-12}$--$1.79\times10^{-11}$。
粗网格失败点被完整保留，因此全部候选算子门为失败。[V]

**右上。** 总能量账本最大值为 $4.3475\times10^{-9}$，本身低于门；最大宽度变化状态
在最高两档约为 $2.35\times10^{-10}$。这说明粗冷状态的失败来自固定点/组内可实现离散，
不是全带能量不守恒。[V]

**左下。** 最终 limiter 触发 405--2345 次，累计触发 7665--95750 次，并不随组数单调。
它们集中在 Wien 尾、连续系数阈值和 Lorentz 交叠后的未解析斜率。limiter 保持组积分，
但触发频繁仍说明当前 P1 形状不是生产表示。[V/O]

**右下。** 一单元运行时间约为 $0.17$--$5.92\ {\rm s}$；最高预算尚未乘以 N128、正式
角阶、16/32 辐射子单元和 2048 相位。门失败后没有继续扩大成本。[V/O]

## 7. 与普通 P1 和 P2 的同预算比较

| 表示 | 物理组数 | 频谱自由度 | 最大速度误差 | 最大宽度变化误差 |
|---|---:|---:|---:|---:|
| 普通 P1：$\nu$ 内线性 | 2408 | 4816 | $9.0435\times10^{-4}$ | $2.4547\times10^{-3}$ |
| 普通 P2：$\nu$ 内二次 | 1604 | 4812 | $7.5063\times10^{-4}$ | $2.5472\times10^{-3}$ |
| log-P1：$Q(y)$ 内线性 | 2408 | 4816 | $9.0431\times10^{-4}$ | $2.4569\times10^{-3}$ |

log-P1 与普通 P1 在决定性宽度状态上只相差约 $0.09\%$。这不是实现失败，而是一个有用
的否定结果：当单元已经足够窄时，$\nu$ 内 P1 和 $\ln\nu$ 内 P1 的局域展开几乎等价；
H I 率误差主要受阈值加权积分量控制，而不是 Doppler 坐标伸缩本身。[V/O]

## 8. 正式判定与下一步

| 判据 | 结果 |
|---|---|
| 对数 P1 投影、Jacobians 和 Lorentz 平移 | 通过 |
| 零速度与移动平衡 | 通过 |
| 全部候选算子门 | 失败，保留 153 组冷表层点 |
| 三状态 $10^{-3}$ 频率门 | 失败 |
| 4816 自由度效率门 | 失败，因为没有共同精度通过点 |
| log-P1 生产组件门 | **失败** |

不选择 log-P1 生产网格，不授权 S16/S24、16/32 辐射子网格、整轨道、温度--布居反馈、
Phase 4 替换或 UVOT。[A-classification/V]

下一表示若仍只提高多项式阶数或更换全局坐标，现有证据预期收益有限。更合理的最小测试是
在仍保留总能量守恒矩的同时，显式保存或控制 H I 光致电离泛函误差；但这需要重新证明
该附加量在 Lorentz 搬移、碰撞源和 ALE 推进中的闭合，不能把参考答案硬编码成校正因子。
[A/O]

## 9. 代码、产物与证据边界

新增：[V]

- `src/eccentric_tde_observer/log_frequency_moments.py`：$Q(y)$ P1、非负性与 Lorentz 平移；
- `src/eccentric_tde_observer/log_multigroup_continuum.py`：对数测度下的 H/He 基态连续率；
- `src/eccentric_tde_observer/mixed_frame_ale_log_p1.py`：完整 log-P1 Lorentz--ALE 联立；
- `scripts/phase7b5a_log_frequency_p1_gate.py`：同预算三状态门和英文图；
- `tests/test_mixed_frame_ale_log_p1.py`、`tests/test_phase7b5a_log_frequency_p1_gate.py`
  及对数频率/微物理回归。

运行：

```bash
uv run python scripts/phase7b5a_log_frequency_p1_gate.py --force
uv run pytest -q
```

主要产物为 `outputs/phase7b5a_summary.json`、三个 CSV 和上面两张经过目视检查的英文图。
[V]

本阶段完成后的现场完整回归为 `439 passed in 57.31s`。[V]

- `[A]`：log-P1 截断、可实现性 limiter、同预算和分类门；
- `[V]`：解析平移、Jacobians、移动平衡、三状态误差、残差、账本、limiter 和成本；
- `[O]`：目标率误差控制、角度/辐射子网格/时间收敛、物质反馈和激发态原子物理。

本阶段仍是规定物态的一步动态连续辐射组件，不是新的观测连续谱，更不是 NLTE 原子线谱。
[V/O]
