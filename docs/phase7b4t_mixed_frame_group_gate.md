# Phase 7B4t：完整 Lorentz 频率组门与正性隐式迭代

> [!abstract] 本阶段定位
> Phase 7B4t 续接
> [[eccentric_tde_observer/docs/phase7b4s_implicit_ale_radiation|Phase 7B4s]]。
> 本阶段已经通过完整 Lorentz 射线变换、守恒频率组搬移和 N128×160×S16 正性迭代
> 压力测试，但也证明 Phase 7B4q 的 160 个 Gauss 求积节点不能直接充当 Doppler 频率
> 控制体。303 个物理频率组通过规定呼吸场的 $10^{-3}$ 运动学门；完整混合系算子尚未
> 与 ALE 方程联立，因此仍不授权全轨道动态连续谱或 Phase 4 替换。

证据标签沿用项目约定：[L] 文献或基本关系，[V] 代码验证，[A] 工作假设或数值分类，
[O] 尚未关闭的问题。

## 1. 为什么不能只在 ALE 通量里写入网格速度

Phase 7B4s 的 $c\mu-w$ 只保证移动控制体的空间能量守恒；它没有把物质共动系中的
吸收、发射和散射变换到实验室系。[A/O]

[Jiang 2021](https://arxiv.org/abs/2102.02212) 在实验室系推进离散射线，在计算物质源项时
用完整 Lorentz 变换进入共动系，并指出一阶 $v/c$ 展开在动态扩散区不一定充分；该论文
实际展示的是频率积分的灰算法。[L]
[Jiang, Stone & Davis 2014](https://arxiv.org/abs/1403.6126) 给出较早的混合系
$\mathcal O(v/c)$ 离散框架和相应动态扩散注意事项。[L]

当前 N128 轨道的最大边界速度为

$$
\max\left(\frac{|w|}{c}\right)
=
8.029\times10^{-3}.
$$

单看该数值似乎很小，但最强呼吸步在 He II 阈值附近的完整柱总光深达到
$9.094\times10^{5}$，系统尺度最大 $\beta\tau$ 达到 $6.554\times10^{3}$，局域单元
最大 $\beta\tau$ 也达到 $250.3$。[V] 因此不能用“$\beta<10^{-2}$”单独批准一阶速度
截断；本阶段采用完整 Lorentz 几何，且把动态扩散渐近一致性留作后续联立算子的独立门。
[A/V/O]

## 2. 完整 Lorentz 射线关系

对沿垂向速度 $\beta c$ 运动的物质，定义实验室系到共动系的 Doppler 因子

$$
D
=
\frac{\nu_{0}}{\nu}
=
\gamma\left(1-\beta\mu\right),
\qquad
\gamma
=
\frac{1}{\sqrt{1-\beta^{2}}}.
$$

方向像差为

$$
\mu_{0}
=
\frac{\mu-\beta}{1-\beta\mu},
$$

而相空间不变量和角测度为

$$
\frac{I_{\nu}}{\nu^{3}}
=
\frac{I_{\nu_{0}}}{\nu_{0}^{3}},
\qquad
\mathrm d\mu_{0}
=
\frac{\mathrm d\mu}{D^{2}}.
$$

频率积分后得到 Jiang 灰算法使用的关系

$$
I_{0}
=
D^{4}I.
$$

代码不把有限阶共动角权重事后归一化；它直接使用 $w_{m,0}=w_{m}/D_{m}^{2}$，并报告
$\frac12\sum_{m}w_{m,0}-1$ 的截断误差。[A/V] 对当前最大 ZO 速度，S16 的能量矩误差为
$2.220\times10^{-16}$，四项中的最大误差为通量矩的 $5.023\times10^{-15}$；即使在
额外的 $\beta=0.17$ 压力控制中，
S8 已达到 $8.032\times10^{-13}$。[V]

## 3. 为什么 Gauss 求积节点不是 Doppler 频率组

Phase 7B4q 的节点和正权专门近似

$$
\int f(\nu)\,\mathrm d\nu
\simeq
\sum_{k}w_{k}f(\nu_{k}).
$$

这里的 $w_{k}$ 是高阶积分权重，不是相邻频率控制体的几何宽度。Doppler 搬移则需要知道
一个频率区间变换后与哪些源区间重叠；只有节点而没有边界，无法定义守恒重叠积分。
[A/V]

本阶段新增显式对齐 H I、He I、He II 阈值的对数频率组。对目标共动组
$[\nu_{0,g-1/2},\nu_{0,g+1/2}]$，以组内分段常数的实验室 $I_{\nu}$ 计算

$$
\overline{I}_{0,g}
=
\frac{D^{4}}{\Delta\nu_{0,g}}
\int_{\nu_{0,g-1/2}/D}^{\nu_{0,g+1/2}/D}
I_{\nu}\,\mathrm d\nu.
$$

逆变换使用

$$
\overline{I}_{g}
=
\frac{D^{-4}}{\Delta\nu_{g}}
\int_{D\nu_{g-1/2}}^{D\nu_{g+1/2}}
I_{\nu_{0}}\,\mathrm d\nu_{0}.
$$

重叠长度严格取自频率组边界，保持非负组强度与组积分；若查询越过频率域，代码直接报错，
不做端点复制、任意外推、`clip` 或 floor。[V]

为避免物理积分频带边缘被一次变换推出网格，扩展网格在
$0.1$--$5000\ {\rm eV}$ 两侧
加入由最大 $D$ 和两次变换次数确定的显式守护带。本次守护范围为
$0.09841$--$5080.9 {\rm eV}$；守护组不计入正式物理频带积分。[A/V]

## 4. 频率组收敛门

解析控制使用 $I_{\nu}\propto\nu^{1.3}$，因此变换后的精确谱为
$I_{\nu_{0}}\propto D^{1.7}\nu_{0}^{1.3}$。没有以漂亮谱形选择指数；这个非整数幂只用于
同时检验组内斜率和边界重叠。[A]

| 每十倍频程组数 | 物理组数 | 最大逐组相对误差 | 积分能量相对误差 |
|---:|---:|---:|---:|
| 8 | 40 | $5.764\times10^{-3}$ | $2.823\times10^{-3}$ |
| 16 | 78 | $5.097\times10^{-3}$ | $1.485\times10^{-3}$ |
| 32 | 153 | $4.316\times10^{-3}$ | $7.400\times10^{-4}$ |
| 64 | 303 | $3.049\times10^{-3}$ | $3.303\times10^{-4}$ |

在真实最强呼吸速度剖面上，再构造每个局域共动系都各向同性的同一解析幂律场，并同时
执行频率搬移、角像差和共动角平均。153 组的最大 $J_{\nu_{0}}$ 误差为
$1.157\times10^{-3}$，略微失败；303 组降到 $7.735\times10^{-4}$，通过预声明的
$10^{-3}$ 门。[V] 失败值和通过值均被保留；没有降低门限。

![Phase 7B4t full Lorentz controls](../outputs/phase7b4t_lorentz_controls.png)

**左图。** 完整辐射张量 boost 随角阶迅速回到解析值；当前 ZO 速度下 S4 已接近机器
精度，$\beta=0.17$ 压力控制则清楚显示 S4 不足、S8 通过。[V]

**中图。** 点状谱密度误差只缓慢下降，但真正守恒的频率积分误差随物理组数单调下降；
303 组的积分误差为 $3.303\times10^{-4}$。[V]

**右图。** 最强网格变化相位的完整柱速度关于中面对称，表面附近达到
$|\beta|=7.207\times10^{-3}$；这是实际 N128 轨道，而不是人为刚体速度场。[V]

## 5. 正性保持的批量隐式迭代

Phase 7B4s 对每个频率做稀疏 LU。它适合 256 个物质单元的验证，但正式 16 倍辐射子网格
每频率有 65536 个未知量，LU 填充不宜作为全轨道默认路线。[V/O]

普通 BiCGSTAB 在最强呼吸步发生 breakdown；重启 GMRES 在接近零的高能强度上产生负的
舍入级分量。项目不允许把这些分量裁成零，因此本阶段没有把 Krylov 的“收敛标志”当作
通过。[V]

当前正性迭代对每个深度把所有角度的相干散射解析消去。局域方程写成

$$
d_{m}I_{m}-qJ=R_{m},
\qquad
J=\frac12\sum_{m}w_{m}I_{m},
$$

于是

$$
J
=
\frac{
\frac12\sum_{m}w_{m}R_{m}/d_{m}
}{
1-q\frac12\sum_{m}w_{m}/d_{m}
},
$$

再用前向和后向空间扫掠更新入射邻居。所有频率批量共享空间循环，避免 Python 层逐频率
重复扫掠；局域分母若非正则直接拒绝。[A/V]

最强呼吸步使用 160 个 Phase 7B4q 节点、S16 和 256 个完整柱物质单元，共 655360 个
强度未知量。结果为：[V]

| 求解器 | 运行时间 | 迭代数 | 最大线性残差 | 最大能量账本残差 |
|---|---:|---:|---:|---:|
| 正性批量源迭代 | $6.4\ {\rm s}$ | 306 | $1.89\times10^{-10}$ | $7.72\times10^{-10}$ |
| 逐频率稀疏 LU | $3.1\ {\rm s}$ | 1 | $2.33\times10^{-13}$ | $9.67\times10^{-13}$ |

两者最终强度的全局尺度归一化差为 $1.76\times10^{-14}$，最小强度均为零而非负值。[V]
当前物质网格上迭代器比 LU 慢约一倍，所以本阶段只证明无填充、正性和结果等价；它没有
证明 10485760 未知量的正式子网格全轨道已经经济可行。[V/O]

![Phase 7B4t solver and dynamic-diffusion gate](../outputs/phase7b4t_solver_and_dynamic_diffusion.png)

**左图。** 正性源迭代在当前 256 深度压力步上慢于 LU；这阻止把“迭代”自动写成“更快”。
[V]

**中图。** 三根柱分别是最终解差、线性残差和能量账本残差除以各自验收门；三者都低于
水平虚线 1。该画法直接显示离门槛还有多少余量，不需要为接近机器零的高能端差值设置
显示 floor。[V]

**右图。** He II 阈值附近的总光深和 $\beta\tau$ 同时跃升，系统 $\beta\tau$ 远大于 1；
因此当前不能把完整 Lorentz 耦合替换成未经渐近验证的一阶修正。[L/V/O]

## 6. 频率网格兼容性图

![Phase 7B4t frequency-grid compatibility gate](../outputs/phase7b4t_frequency_grid_gate.png)

**左图。** 蓝点是 160 点 Gauss 求积权重，橙点是有限体积组宽。两者即使数量接近也有
不同数学职责，不能互换。[V]

**中图。** 值为 1 的区域才属于 $0.1$--$5000 {\rm eV}$ 正式积分带；两侧值为 0 的组
只承担 Doppler 查询守护带。[A/V]

**右图。** 303 组在真实呼吸速度和 S16 下的逐频率共动平均误差全部低于 $10^{-3}$；
阈值附近的小结构被保留，没有删除坏组。[V]

## 7. 阶段决定

Phase 7B4t 的组件门通过：[V]

1. 完整 Lorentz Doppler、像差、强度不变量和角测度通过解析张量控制；
2. 正性守恒频率组搬移通过零速度、常谱、幂律和真实同源呼吸控制；
3. 153 个物理组失败，303 个物理组通过动态频率--角度 $10^{-3}$ 门；
4. 正性批量源迭代在 N128×160×S16 压力步与稀疏 LU 一致并闭合能量账本；
5. $\beta\tau$ 审计否决未经验证的一阶速度截断。

但以下授权仍为否：[O]

- 303 组的 H/He opacity、Milne 发射、光致率和净加热尚未对 604 组及静态 160/304
  求积重新收敛；
- Lorentz 频率--角度算子尚未进入 ALE 隐式方程的同一个联立残差；
- 正式 16/32 辐射子单元和 2048 相位全轨道尚未运行；
- 动态 $J_{\nu}$ 尚未反馈温度与 H/He 基态布居。

因此下一小阶段是：**先关闭阈值对齐多群的连续系数与原子率收敛，再把完整 Lorentz
碰撞算子与 ALE 输运联立。** 在此之前仍不能生成正式动态 SED、替换 Phase 4、进入 UVOT、
调用 Cloudy 或把基态连续模型称为完整 NLTE 大气。[A-classification/O]

## 8. 文件与复现

核心文件：

- `src/eccentric_tde_observer/mixed_frame_frequency.py`：Lorentz 射线关系、阈值对齐频率组、
  守恒搬移和共动平均；
- `src/eccentric_tde_observer/implicit_radiative_transfer_1d.py`：正性批量源迭代和 LU 对照；
- `scripts/phase7b4t_mixed_frame_group_gate.py`：解析控制、N128 压力步、图表和阶段判定；
- `tests/test_mixed_frame_frequency.py`：辐射张量、零速度、常谱、刚体 boost 和越界拒绝；
- `tests/test_implicit_radiative_transfer_1d.py`：源迭代与稀疏 LU 等价、正性与能量账本；
- `outputs/phase7b4t_summary.json`：机器可读阶段判定；
- `outputs/phase7b4t_angular_controls.csv`、`outputs/phase7b4t_frequency_group_controls.csv`、
  `outputs/phase7b4t_solver_stress.csv`：数值证据表；
- `outputs/phase7b4t_diagnostics.npz`：绘图所需逐频率和逐深度数组；
- `outputs/phase7b4t_lorentz_controls.png`、
  `outputs/phase7b4t_solver_and_dynamic_diffusion.png`、
  `outputs/phase7b4t_frequency_grid_gate.png`：全英文图件。

运行：

~~~bash
.venv/bin/python scripts/phase7b4t_mixed_frame_group_gate.py --force
~~~

不加 `--force` 时若全部阶段产物存在，脚本只复用，不覆盖。[V]

现场验证：

~~~bash
.venv/bin/python -m pytest -q \
  tests/test_mixed_frame_frequency.py \
  tests/test_implicit_radiative_transfer_1d.py \
  tests/test_phase7b4t_mixed_frame_group_gate.py \
  tests/test_markdown_math.py
.venv/bin/python -m pytest -q
~~~

定向控制为 `22 passed in 0.81s`，完整项目回归为
`372 passed in 53.61s`。[V] 前者覆盖 Lorentz/频率组、隐式求解器、阶段判定和
Markdown 公式规范；后者确认本阶段没有破坏此前科学路径。
