# Phase 7B5o：1--2--4 分层 P0 的初始态/收敛态独立验证

> [!summary] 阶段结论
> `[A/V/O]` 冻结协议、材料哈希、旧留出排除、4816 叶预算、参考源求解、映射/投影/求积
> 和正式收敛算子控制全部通过；9632 组 master 在 12 个新状态的能量与 H/He 联合门全部
> 通过。4816 叶候选的能量、H I 和 He I 均通过，但在 `signed width change q80` 的参考
> 收敛态得到 He II 光致电离率误差 $1.0005463\times10^{-3}$，严格高于 $10^{-3}$。
> 因此不选择生产频率表示，也不进入角度--辐射子网格门。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5o_preregistered_protocol|7B5o 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5n_preregistered_protocol|7B5n 协议失败]] ·
[[eccentric_tde_observer/docs/phase7b5m_actual_multiresolution_validation|7B5m]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]

---

## 1. 验证对象

开发集仍是已经暴露的三个压力病例和 $n=0,1,2,4,8$，共 15 个状态。9632 组 master
谱只用于计算每个父带采用 1、2 或 4 个 P0 叶时的局域能量/H/He 缺陷。整数动态规划在
冻结的

$$
\sum_{p} k_{p}=4816,
\qquad
k_{p}\in\{1,2,4\}
$$

约束下选择网格。验证病例和验证谱没有进入这个目标。[A/V]

最终 2408 个父带的选择为：[V]

| 每父带叶数 | 父带数 | 贡献的物理叶数 |
|---:|---:|---:|
| 1 | 1408 | 1408 |
| 2 | 296 | 592 |
| 4 | 704 | 2816 |
| **合计** | **2408** | **4816** |

冻结网格在验证前后的 SHA-256 都是
`2f905d8ad0df879df3cba4311921a37233f082d5022e1630ace1934f8053bad7`。[V]

## 2. 独立验证状态

7B5o 排除了 7B5n 已打开的六个病例，重新按物态和几何分位选择六个病例：[A/V]

| 选择轴 | 低分位病例 | 高分位病例 |
|---|---|---|
| 下一时刻表面温度 | q40：phase 1433, depth 0 | q60：phase 1637, depth 0 |
| 有符号单元中心速度 | q20：phase 1307, depth 144 | q80：phase 740, depth 144 |
| 有符号单元宽度变化 | q20：phase 1560, depth 7 | q80：phase 487, depth 29 |

每个病例验证初始态和参考收敛态，共 12 个状态。参考源求解分别在 17--152 次迭代收敛；
最大联立残差为 $7.5853\times10^{-11}$，最大能量账本残差为
$5.8148\times10^{-10}$，最小强度为严格的 0。没有 floor。[V]

## 3. 联合物理量

P0 谱能量积分采用

$$
Q=\int J_{\nu}\,\mathrm d\nu.
$$

对 $s\in\{\mathrm{H\ I},\mathrm{He\ I},\mathrm{He\ II}\}$，光致电离率为

$$
\Gamma_{s}
=
4\pi\int_{\nu_{s}}^{\infty}
\frac{J_{\nu}\sigma_{\nu,s}}{h\nu}\,\mathrm d\nu.
$$

候选与 8192 组/decade 参考分别积分，再计算

$$
\epsilon_{\rm X}
=
\left|
\frac{X_{\rm candidate}-X_{\rm reference}}
{X_{\rm reference}}
\right|.
$$

能量和三种率都必须逐状态严格满足 $\epsilon_{\rm X}<10^{-3}$。8/16 阶率求积的最大相对变化
只有 $4.1273\times10^{-16}$；候选和 master 的最大投影能量误差分别为
$3.0583\times10^{-16}$ 和 $3.5758\times10^{-16}$。[V]

## 4. 验证误差

![Phase 7B5o joint validation errors](../outputs/phase7b5o_validation_errors.png)

四个面板依次给出总能量、H I、He I 和 He II。红线是冻结的 4816 叶候选，绿线是 9632
组 master，黑色虚线是 $10^{-3}$ 门。多数初始态误差显著较低；速度和宽度变化病例的
收敛态最接近门槛，说明固定点形成后的谱边结构比初始 Planck 样状态更难压缩。[V]

唯一候选失败点已用黑色叉号标出：`signed width change q80` 的收敛态 He II 误差为
$1.000546314\times10^{-3}$。master 在同一点为 $9.785504749\times10^{-4}$，通过。
候选只比门槛高 $5.46314\times10^{-7}$，相对门槛高约 $0.0546\%$；这一差距不能被
四舍五入成通过。[V]

全部最大值为：[V]

| 表示 | 能量 | H I | He I | He II |
|---|---:|---:|---:|---:|
| 4816 叶候选 | $2.31742\times10^{-4}$ | $8.24234\times10^{-4}$ | $2.78001\times10^{-4}$ | **$1.000546\times10^{-3}$** |
| 9632 组 master | $2.28557\times10^{-4}$ | $7.35533\times10^{-4}$ | $2.83232\times10^{-4}$ | $9.78550\times10^{-4}$ |

## 5. 频率叶分配

![Phase 7B5o hierarchy allocation](../outputs/phase7b5o_hierarchy_allocation.png)

上图显示每个基父带最终保留 1、2 或 4 个叶；主要细化集中在约 1--13 eV、20--35 eV 和
约 55--65 eV 一带，对应热谱弯曲和 H/He 连续边附近。约 100 eV 以上大部分父带保留单叶，
因为开发谱对联合目标的局域贡献迅速下降。[A/V]

下图给出被选层级仍保留的开发集归一化局域缺陷。采用 4 叶的父带在 master 表示上局域
缺陷为零；非零曲线来自 1 叶或 2 叶父带。这个图解释了自由度投向哪里，但不能证明新留出
误差；后者只能由上一节独立验证决定。[V]

## 6. 算子和资源控制

12 个候选/master 正式算子都从相应参考收敛态的守恒投影开始，并重新迭代到固定点。最大
联立残差为 $7.4136\times10^{-11}$，最大相对能量账本残差为
$1.8810\times10^{-11}$，最大最终固定点变化为 $9.7287\times10^{-11}$；全部非负性门
通过。[V]

![Phase 7B5o resource costs](../outputs/phase7b5o_resource_costs.png)

4816 叶候选的单单元中位一步时间为 $0.04070\,\mathrm{s}$，9632 master 为
$0.07689\,\mathrm{s}$。返回数组分别为 $2.1313\,\mathrm{MiB}$ 和
$4.2624\,\mathrm{MiB}$；按完整 256 深度单元线性外推分别为 $0.5328\,\mathrm{GiB}$
和 $1.0656\,\mathrm{GiB}$。这些只是返回数组，不是进程峰值内存。[V/O]

## 7. 严格判定与下一边界

| 判据 | 结果 |
|---|---|
| 冻结协议、材料和旧留出排除哈希 | 通过 |
| 新病例未参与构网 | 通过 |
| 参考源求解 | 通过 |
| 恰好 4816 叶和冻结网格哈希 | 通过 |
| 映射、投影、率求积 | 通过 |
| 正式收敛算子 | 通过 |
| 9632 master 联合门 | 通过 |
| 4816 候选能量、H I、He I | 通过 |
| 4816 候选 He II | **失败** |
| 单单元生产频率表示 | **未选择** |
| 角度--辐射子网格门 | **未授权** |
| 全轨道、物质反馈、Phase 4 替换、UVOT | **仍关闭** |

7B5o 不能用同一 12 个验证状态重新改动态规划目标或父带选择。现有证据给出一个清楚的资源
分叉：[A/O]

1. 保持 4816 叶上限：必须提出另一个预先定义的表示族，并建立全新留出协议；
2. 修改资源假设：9632 组 master 已通过本轮联合门，可在明确批准新预算后进入角度--辐射
   子网格单单元成本与收敛门。

不能因为失败只高 $0.0546\%$ 就跳过授权，也不能把 He II 从联合目标中删除。[V/O]

## 8. 复现

```bash
PYTHONPATH=scripts uv run python scripts/phase7b5o_preregister_protocol.py
PYTHONPATH=scripts uv run python scripts/phase7b5o_initial_converged_validation.py --force
uv run pytest -q tests/test_phase7b5o_initial_converged_validation.py
uv run pytest -q
```

机器产物为 `outputs/phase7b5o_summary.json`、三个 CSV 和三张已目视检查的英文图。[V]
本阶段收尾后的现场完整回归为 `616 passed in 60.35s`。[V]

- `[V]`：协议/材料/网格哈希、12 个新状态、联合误差、算子控制和资源账本；
- `[A]`：4816 预算、分位病例、初始/收敛态和 $10^{-3}$ 门；
- `[O]`：是否提高资源预算、角度/辐射子网格、全轨道与物质反馈。
