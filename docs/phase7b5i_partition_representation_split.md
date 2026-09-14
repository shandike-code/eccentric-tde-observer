# Phase 7B5i：同输入注入的频率分区与 P1--P0 拆分

> [!summary] 阶段结论
> `[A/V/O]` Phase 7B5i 在 7B5h 的同输入单步映射中加入 2408 组 P0 中间控制，将
> log-P1 相对 38496 组 P0 的 H I 率注入严格拆成“细 P0 到候选分区 P0”与“同分区
> P0 到 log-P1”两项。两个移动状态的前一项在全部检查截面都占绝对分量和的
> $60.1\%$--$64.3\%$，后一项占 $35.7\%$--$39.9\%$，且两者异号抵消。4816 组同成本
> P0 改善了粗 P0，但最大宽度变化的第 4/8 次仍以 $1.17\times10^{-3}$ 与
> $1.83\times10^{-3}$ 失败。下一步授权频率分区审计；不授权把 P1 组内表示定为唯一
> 主因，也不选择生产频率表示。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5h_recurrence_decomposition|Phase 7B5h 单步分解]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

---

## 1. 三套有限表示与一个参考

在每个 P0 参考固定点输入 $R_{n}$ 上同时构造：[A]

1. 38496 组细 P0 参考；
2. 与失败候选完全相同边界的 2408 组 P0；
3. 同一 2408 组边界的 log-P1，共 4816 个谱自由度；
4. 相同率核分区策略的 4816 组 P0，作为同自由度控制。

P0 投影按原生频率区间交叠积分，不插值、不重归一化：[V]

$$
\bar J_{k}
=
\frac{1}{\Delta\nu_{k}}
\sum_{j}
J_{j}\,
\Delta\nu_{\rm jk}.
$$

所有 P0 与 log-P1 投影的频带能量误差最大为 $4.64\times10^{-16}$。[V]

## 2. 精确拆分的含义

记细 P0、候选分区 P0 和同分区 log-P1 一步后的 H I 率为
$\Gamma_{0,\rm fine}$、$\Gamma_{0,\rm part}$ 与 $\Gamma_{1,\rm part}$。则：[A/V]

$$
b_{
m total}
=
\frac{\Gamma_{1,\rm part}-\Gamma_{0,\rm fine}}
{\Gamma_{0,\rm fine}},
$$

$$
b_{\rm partition}
=
\frac{\Gamma_{0,\rm part}-\Gamma_{0,\rm fine}}
{\Gamma_{0,\rm fine}},
$$

$$
b_{\rm P1-P0}
=
\frac{\Gamma_{1,\rm part}-\Gamma_{0,\rm part}}
{\Gamma_{0,\rm fine}}.
$$

因此：[V]

$$
b_{\rm total}=b_{\rm partition}+b_{\rm P1-P0}.
$$

这里 $b_{\rm P1-P0}$ 不能窄化为“纯组内斜率误差”：它同时包含同一分区上的 P1 谱重构、
P1 组平均连续系数和 P1 Lorentz--碰撞离散与 P0 的差。[A/O]

## 3. 分区项与同分区 P1--P0 项

![Phase 7B5i partition-representation decomposition](../outputs/phase7b5i_partition_representation_decomposition.png)

**上排。** 橙色频率分区项为负，绿色同分区 P1--P0 项为正，蓝色总注入是两者抵消后的
结果。最大速度后期约为
$-1.56\times10^{-3}+9.82\times10^{-4}=-5.74\times10^{-4}$；最大宽度第 8 次约为
$-3.94\times10^{-3}+2.23\times10^{-3}=-1.71\times10^{-3}$。[V]

**下排。** 使用两个绝对分量和归一化。最大速度的分区比例为 $61.3\%$--$64.3\%$；
最大宽度变化为 $60.1\%$--$63.8\%$。它稳定越过 $50\%$ 门，但 P1--P0 项仍有约
$36\%$--$40\%$，不能称为可忽略。[A-classification/V]

15 个标量率账本的相对残差最大 $3.79\times10^{-16}$；8/16 阶联合边界求积差最大
$3.51\times10^{-16}$。7B5h 的总同输入注入也在每个截面得到复现。[V]

## 4. 同自由度 P0 是否已足够

![Phase 7B5i same-cost P0 comparison](../outputs/phase7b5i_same_cost_p0_comparison.png)

**左图。** 最冷表层的三种有限表示都远低于 $10^{-3}$。[V]

**中图。** 最大速度状态中，2408 组 P0 从第 1 次起失败；4816 组 P0 全部通过，但误差仍
高于 2408 组 log-P1。log-P1 用组内一次矩有效抵消了一部分粗分区偏差。[V/O]

**右图。** 最大宽度变化最严格。4816 组 P0 在第 4/8 次分别为
$1.1721\times10^{-3}$ 与 $1.8348\times10^{-3}$，仍失败；2408 组 log-P1 在第 8 次也为
$1.7086\times10^{-3}$。同自由度 P0 并没有关闭全部单步率门。[V]

这张图不选择“看起来最好”的表示：同成本 P0 在最大速度较差，在最大宽度后期略差或接近
log-P1，且两者都存在失败截面。[A/V/O]

## 5. 两个分量位于哪些能段

![Phase 7B5i component-region evolution](../outputs/phase7b5i_component_region_evolution.png)

**上排。** 分区项在最冷表层约 $89\%$ 位于 H I shoulder；最大速度的 Doppler 比例从
$32\%$ 增到 $58\%$；最大宽度变化从 $15\%$ 增到 $83\%$。[V]

**下排。** 同分区 P1--P0 项也发生相似迁移，但 Doppler 占比略低：最大速度后期约
$48\%$，最大宽度第 8 次约 $75\%$。两个分量在相同阈值区域异号响应，这解释了总率的
显著抵消，也说明不能只用一个总误差数判断单个算符。[V/O]

图中省略始终为 0 的 H I 阈值以下列；完整 CSV 中每个分量、每个截面的五段绝对比例和为
1。[V]

## 6. 门槛与下一步

| 判据 | 结果 |
|---|---|
| 细 P0 下一截面复现 | 15/15 逐位通过 |
| 三种输入投影能量 | 全部通过，最大 $4.64\times10^{-16}$ |
| 分区--P1/P0 标量率账本 | 全部通过，最大 $3.79\times10^{-16}$ |
| 8/16 阶率定位 | 全部通过，最大 $3.51\times10^{-16}$ |
| 两个移动状态共同主导项 | 频率分区项 |
| 4816 组同成本 P0 单步率门 | 失败，最大 $1.8348\times10^{-3}$ |
| 频率分区审计 | **授权** |
| P1 表示定为唯一主因 | **未授权** |
| 针对算符修正 | **未授权** |
| 生产频率表示 | **未选择** |

下一小阶段应保持固定点与物理系数不变，对率核分区做预声明、非拟合的结构控制：[A/O]

1. 比较普通对数、当前 H I 率核分区和显式 H I Doppler 带细化；
2. 固定总组数与组内 P0，避免与 P1 阶数混在一起；
3. 至少在 2408、4816 组和更高参考层检查误差随组数的符号与收敛率；
4. 不扫描并事后挑选任意聚焦比例；Doppler 带宽由已知最大速度唯一给出；
5. 只有跨两个移动状态稳定改善，才讨论新的生产候选。

## 7. 代码、产物与证据边界

新增或扩展：[V]

- `src/eccentric_tde_observer/rate_error_localization.py`：任意 P0 网格间的守恒投影；
- `scripts/phase7b5i_partition_representation_split.py`：四表示单步率账本和英文图；
- `tests/test_phase7b5i_partition_representation_split.py`：阶段判定、跨阶段复现和授权边界；
- `tests/test_rate_error_localization.py`：P0 投影能量与常数场回收。

运行：

```bash
PYTHONPATH=scripts uv run python scripts/phase7b5i_partition_representation_split.py --force
uv run pytest -q
```

主要产物为 `outputs/phase7b5i_summary.json`、两个 CSV 和三张经过目视检查的英文图。[V]

本阶段完成后的现场完整回归为 `491 passed in 55.29s`。[V]

- `[A]`：2408 组同分区 P0、4816 组同自由度 P0 与 $50\%$ 主导阈值；
- `[V]`：守恒投影、单步复现、标量率账本、同成本门和阈值区定位；
- `[O]`：频率分区内部应采用哪一种非拟合结构，以及 P1--P0 项的更细算符来源；
- `[L]`：本阶段没有新增文献物理。

Phase 7B5i 是频率离散诊断，不是收敛生产谱、动态 NLTE 大气或 Phase 4 替换。[A/V/O]
