# Phase 7B4u：H/He 多群连续系数与原子率门

> [!abstract] 本阶段定位
> Phase 7B4u 续接
> [[eccentric_tde_observer/docs/phase7b4t_mixed_frame_group_gate|Phase 7B4t]]。
> 7B4t 只证明 303 个频率组能回收 Lorentz 运动学搬移；本阶段进一步检验同一有限体积
> 表示能否回收实际 H/He opacity、Milne 发射、光致电离率、复合率和净加热。扩展后的
> 168 个 N128×2048 真实物态样本使 604 组以 $1.0093\times10^{-3}$ 轻微失败；1205 组
> 以 $2.5271\times10^{-4}$ 通过。因此下一阶段可实现完整混合系 ALE 组件，但尚不授权
> 全轨道动态谱。

证据标签沿用项目约定：[L] 文献或基本关系，[V] 代码验证，[A] 工作假设或数值分类，
[O] 尚未关闭的问题。

## 1. 为什么不能只在组中心查询 opacity

有限体积频率组保存的是频率密度平均

$$
\overline I_{g}
=
\frac{1}{\Delta\nu_{g}}
\int_{\nu_{g-1/2}}^{\nu_{g+1/2}}
I_{\nu}\,\mathrm d\nu.
$$

若未来的多群输运把组内 $I_{\nu}$ 表示为常数，则频率积分后的物质项应写成

$$
\int_{g}
\left(
\chi_{\nu}I_{\nu}-\eta_{\nu}
\right)
\mathrm d\nu
\simeq
\Delta\nu_{g}
\left(
\overline\chi_{g}\overline I_{g}
-
\overline\eta_{g}
\right),
$$

其中

$$
\overline\chi_{g}
=
\frac{1}{\Delta\nu_{g}}\int_{g}\chi_{\nu}\,\mathrm d\nu,
\qquad
\overline\eta_{g}
=
\frac{1}{\Delta\nu_{g}}\int_{g}\eta_{\nu}\,\mathrm d\nu.
$$

在组中心只计算一次 $\chi_{\nu}$ 会同时丢失离化边跃变和组内谱斜率；它不等价于上式。
[A/V]

本阶段在每个真实频率控制体内使用正权 Gauss--Legendre 积分。H I、He I、He II 基态
阈值都是组边界，节点不落在不连续处；组内阶数 8、16、32 被独立比较。没有把中心值乘以
经验修正，也没有使用 `clip`、floor 或事后详细平衡重归一化。[V]

## 2. 多群原子率怎样定义

在组内常强度表示下，基态光致电离率为

$$
\Gamma_{i}
\simeq
4\pi
\sum_{g}
\overline J_{g}
\int_{g}
\frac{\sigma_{i}(\nu)}{h\nu}\,\mathrm d\nu.
$$

受激复合使用同一组 $\overline J_{g}$ 和同一 Verner 截面；自发复合、束缚--自由发射及
自由--自由发射仍在每个组内直接积分。辐射净加热为

$$
q_{\rm rad}
=
4\pi
\sum_{g}
\Delta\nu_{g}
\left(
\overline\chi_{{\rm abs},g}\overline J_{g}
-
\overline\eta_{g}
\right).
$$

净加热可能是两个大数的小差，因此本阶段的 heating-ledger 误差用吸收功率和发射功率中
较大的一个归一化，而不是除以接近零的 $q_{\rm rad}$。这是数值尺度定义，不是物理 floor。
[A/V]

## 3. 独立参考与真实物态样本

参考频带仍为 $0.1$--$5000\ {\rm eV}$。静态节点使用 Phase 7B4q 的阈值超额正权求积：

- 160 节点为旧生产候选；
- 304 节点为第一加密；
- 584 节点为本阶段独立参考。

多群候选为 153、303、604 和 1205 个物理组；相应带两侧 Doppler 守护带的总组数为
155、305、606 和 1209。守护组不计入本阶段物理频带率积分。[A/V]

物态来自独立的 N128×2048 周期物质参考。样本包含：

- 16 个全周期均匀索引相位；
- Phase 7B4t 的最强网格变化相位 628；
- 最大速度相位 1367；
- 全域最低温度、最高温度和 He II/He III 前沿相位；
- 每个相位的 8 个固定拉格朗日深度。

去重后共 21 个相位、168 个真实状态。没有删除低温表层或接近零的离化级。[V]

## 4. 收敛结果

所有误差相对同一 584 节点参考，目标为预声明的 $10^{-3}$：

| 表示 | 最大误差 | 判定 |
|---|---:|:---:|
| 160 个静态 Gauss 节点 | $1.2001\times10^{-12}$ | 通过 |
| 304 个静态 Gauss 节点 | $1.1938\times10^{-15}$ | 通过 |
| 153 个物理频率组 | $1.4419\times10^{-2}$ | 失败 |
| 303 个物理频率组 | $3.7871\times10^{-3}$ | 失败 |
| 604 个物理频率组 | $1.0093\times10^{-3}$ | 轻微失败 |
| 1205 个物理频率组 | $2.5271\times10^{-4}$ | 通过 |

604 组的失败来自 heating ledger；其 opacity 作用量、光致电离率和受激复合率误差分别为
$9.3274\times10^{-5}$、$3.7832\times10^{-4}$ 和 $9.0922\times10^{-4}$，但最低温
表层的吸收--发射小差使最终账本误差达到 $1.0093\times10^{-3}$。[V]

1205 组的最差误差仍来自同一账本，但降到 $2.5271\times10^{-4}$。组内 16 阶相对
32 阶的最大差仅为 $8.954\times10^{-16}$；所以失败来自组内常强度表示，而不是组内
Gauss 积分不足。[V]

![Phase 7B4u multigroup continuum gate](../outputs/phase7b4u_multigroup_gate.png)

**左图。** 153--1205 组的 opacity 作用量、光致率、受激/总复合率和 heating ledger
近似按组宽平方下降；自发发射积分已接近机器精度。水平虚线是 $10^{-3}$ 门。[V]

**中图。** 蓝柱是静态 Gauss 节点，橙柱是有限体积组。160/304 节点的职责是高阶积分，
而频率组还必须表示可被 Doppler 搬移的谱密度，所以相同数量级的节点和组不能交换。
604 组柱略高于门，1205 组明确低于门。[V]

**右图。** 604 组误差在 21 个相位和 8 个固定质量深度上都被保留。最坏点位于最低温
表层，而不是 Phase 7B4t 的最大速度步；因此只检查速度压力相位会错误批准 604 组。[V]

## 5. 最坏物态的连续系数

604 与 1205 组的共同最坏样本为：

$$
\Phi=0.50390,
\qquad
T=9363.6\ {\rm K},
\qquad
\rho=2.4951\times10^{-14}\ {\rm g\,cm^{-3}}.
$$

该点位于最表层，He I 分数为 $0.97617$，He II 分数为 $0.023829$。[V]

![Phase 7B4u worst-state continuum coefficients](../outputs/phase7b4u_worst_state_coefficients.png)

**左图。** 黑线为 584 节点真实吸收，橙色虚线与蓝色点线为 604/1205 组平均。三条
H/He 离化边的跳跃被显式保留；彩色阶梯与黑线高度重合说明 coefficient averaging
本身正确。[V]

**中图。** 热发射跨越极大的指数动态范围，组平均仍沿参考曲线。高能端趋近浮点零的
物理指数尾没有用显示 floor 抬高。[V]

**右图。** 五个基态离化级全部显示；接近零的 He III 也未删除。低温、高 He I 分数使
该表层对离化边附近的组内谱斜率最敏感。[V]

## 6. 阶段决定

Phase 7B4u 的多群连续系数门通过，但正式候选不是 604 组，而是 1205 个物理组：[V]

1. 160/304 静态节点相对 584 节点参考均通过；
2. 153、303 和 604 组失败，失败结果完整保留；
3. 1205 组以 $2.5271\times10^{-4}$ 通过；
4. 组内 16 阶求积已经充分；
5. 因此下一小阶段获准把 1205 组完整 Lorentz 源项与 ALE 输运联立。

以下授权仍为否：[O]

- 尚未实现同一残差中的 Lorentz 频率--角度变换、吸收、发射、散射和 ALE 储能；
- 尚未回收零速度、刚体平移、同源呼吸及动态扩散解析/半解析极限；
- 尚未在正式辐射子网格和 2048 相位上运行；
- 温度与 H/He 布居仍是规定物质输入；
- 尚无动态 SED、Phase 4 替换、UVOT、Cloudy 或真实线形成授权。

## 7. 文件与复现

核心文件：

- `src/eccentric_tde_observer/multigroup_continuum.py`：组内正权求积、H/He 组平均
  连续系数、原子率和能量交换；
- `scripts/phase7b4u_multigroup_continuum_gate.py`：真实物态抽样、收敛、图表和判定；
- `tests/test_multigroup_continuum.py`：解析组积分、LTE 收敛、拒绝域和禁修补控制；
- `tests/test_phase7b4u_multigroup_continuum_gate.py`：样本、组数和机器判定回归；
- `outputs/phase7b4u_summary.json`：机器可读阶段结论；
- `outputs/phase7b4u_multigroup_convergence.csv`：全部数值表示和误差分量；
- `outputs/phase7b4u_worst_states.csv`：每个候选的最坏真实物态；
- `outputs/phase7b4u_state_sample.csv`：168 个实际状态；
- `outputs/phase7b4u_multigroup_gate.png` 和
  `outputs/phase7b4u_worst_state_coefficients.png`：全英文图件。

运行：

~~~bash
.venv/bin/python scripts/phase7b4u_multigroup_continuum_gate.py --force
~~~

本阶段收尾时的定向回归覆盖多群连续系数、7B4u 机器判定、7B4s/7B4t 接口兼容和
Markdown 数学规范，结果为 `24 passed in 1.14s`。随后执行完整回归：

~~~bash
.venv/bin/python -m pytest -q
~~~

现场结果为 `380 passed in 54.71s`。[V]
