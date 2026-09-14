# Phase 7B5h：固定点单步注入与已有误差传播分解

> [!summary] 阶段结论
> `[A/V/O]` Phase 7B5h 在 P0 参考固定点的同一输入状态上分别执行一次 P0 与
> log-P1 映射，并把候选谱原有误差的传播单独记账。全部 15 个截面逐位复现原固定点的
> 下一步，标量 H I 率账本闭合到不超过 $1.81\times10^{-16}$。最大速度与最大宽度变化
> 状态中，单步新注入占两个绝对分量之和的最低比例仍为 $95.3\%$；已有误差传播不是主因。
> 因而下一步应拆分同一输入下的频率网格误差与组内表示误差，不授权 Jacobian--vector
> 放大审计、算符修正或生产路径替换。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5g_fixed_point_feedback_audit|Phase 7B5g 固定点反馈]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

---

## 1. 为什么需要这一步

Phase 7B5g 验证了 H I 率误差会随源迭代增长，但增长本身不能区分两种机制：[O]

$$
\delta \Gamma^{(n+1)}
=
b^{(n)}
+
p^{(n)}.
$$

这里 $b^{(n)}$ 是 P1 与 P0 在同一参考输入上的单步离散差，$p^{(n)}$ 是把候选谱中已经
存在的差异送入同一 P1 映射后产生的传播项。若 $p^{(n)}$ 主导，才有必要优先估计固定点
映射的 Jacobian--vector；若 $b^{(n)}$ 主导，应先找每一步为什么重新写入偏差。[A]

## 2. 同一输入与精确账本

在输入迭代 $n=0,1,2,4,8$，保存细 P0 状态 $R_{n}$ 与候选 log-P1 状态 $C_{n}$。将 $R_{n}$
守恒投影到候选 log-P1 网格，记为 $P R_{n}$。然后只执行一次映射：[A/V]

$$
R_{n+1}=T_{0}(R_{n}),
$$

$$
C_{n+1}=T_{1}(C_{n}),
$$

$$
\widetilde C_{n+1}=T_{1}(P R_{n}).
$$

相对于同一步 P0 率，定义：[A/V]

$$
b^{(n)}
=
\frac{\Gamma(\widetilde C_{n+1})-\Gamma(R_{n+1})}
{\Gamma(R_{n+1})},
$$

$$
p^{(n)}
=
\frac{\Gamma(C_{n+1})-\Gamma(\widetilde C_{n+1})}
{\Gamma(R_{n+1})}.
$$

于是实际下一步误差严格满足：[V]

$$
\delta\Gamma^{(n+1)}=b^{(n)}+p^{(n)}.
$$

这是标量 H I 率分解，不是完整谱向量的线性化，也没有构造稠密 Jacobian。[A/O]

## 3. 单步分解图

![Phase 7B5h recurrence decomposition](../outputs/phase7b5h_recurrence_decomposition.png)

**上排。** 蓝色实际下一步误差几乎与橙色同输入注入重合。绿色传播项在最冷表层和最大
速度状态中常与主误差异号，略微抵消；最大宽度变化状态的后期传播同号，但仍远小于注入。
[V]

**下排。** 为避免异号抵消使比例超过 1，图中采用绝对分量和归一化：[A-classification]

$$
f_{b}=
\frac{|b|}{|b|+|p|},
\qquad
f_{p}=
\frac{|p|}{|b|+|p|}.
$$

绿色虚线是预声明的 $50\%$ 主导阈值。两个移动状态全部截面的 $f_{b}$ 都高于 $95.3\%$；
最大速度后期约为 $99.0\%$，最大宽度变化后期约为 $95.6\%$。[A-classification/V]

代表性数值如下：[V]

| 状态 | 输入迭代 | 实际下一步误差 | 同输入注入 | 已有误差传播 | $f_{b}$ |
|---|---:|---:|---:|---:|---:|
| 最大速度 | 0 | $-1.9810\times10^{-4}$ | $-1.9799\times10^{-4}$ | $-1.0710\times10^{-7}$ | $99.95\%$ |
| 最大速度 | 8 | $-5.6818\times10^{-4}$ | $-5.7377\times10^{-4}$ | $+5.5847\times10^{-6}$ | $99.03\%$ |
| 最大宽度 | 0 | $-3.7957\times10^{-5}$ | $-3.7970\times10^{-5}$ | $+1.3437\times10^{-8}$ | $99.96\%$ |
| 最大宽度 | 8 | $-1.7872\times10^{-3}$ | $-1.7086\times10^{-3}$ | $-7.8509\times10^{-5}$ | $95.61\%$ |

## 4. 单步注入出现在哪些能段

![Phase 7B5h injection-region evolution](../outputs/phase7b5h_injection_region_evolution.png)

**左图。** 最冷表层的单步注入稳定集中在 H I shoulder 到 He I 阈值之间，比例约
$85\%$；它不是移动网格特有误差。[V]

**中图。** 最大速度状态在第 0 次仍有 $60\%$ 位于 shoulder，但第 1 次起 H I Doppler
阈值带成为主导，第 8 次达到 $62\%$。[V]

**右图。** 最大宽度变化状态的注入更持续地向 H I Doppler 带集中，从 $28\%$ 增到
$89\%$。这说明每次重新注入的误差形状会随固定点状态改变，不能只诊断初始 Planck 谱。
[V/O]

图中省略了始终为 0 的 H I 阈值以下列；CSV 保留完整五段，逐截面比例和为 1。[V]

## 5. 数值门与授权边界

| 判据 | 结果 |
|---|---|
| P0 与 P1 单步映射复现原下一截面 | 15/15 逐位通过 |
| P0 到 log-P1 投影能量误差 | 最大 $4.64\times10^{-16}$ |
| H I 率分解账本相对残差 | 最大 $1.81\times10^{-16}$ |
| 8/16 阶率定位差 | 最大 $4.16\times10^{-16}$ |
| 两个移动状态的共同主导项 | 同输入单步注入 |
| Jacobian--vector 放大审计 | **未授权** |
| 同输入注入拆分 | **授权** |
| 针对算符修正 | **未授权** |
| 生产频率表示 | **未选择** |

固定次数接口允许有意返回未收敛的一步状态；所有这些产物都带
`fixed_point_converged=False`，不得被误当成正式输出谱。[V]

下一小阶段应在同一输入上加入候选网格的 P0 中间控制，把注入拆成：[A/O]

1. 细 P0 到候选分区 P0 的频率网格项；
2. 同一候选分区上 P0 到 log-P1 的组内表示项；
3. 两项相加是否逐点闭合原始单步注入。

在同分区与同自由度控制都完成以前，不能把误差归咎于某个 Lorentz 系数或直接修改算符。

## 6. 代码、产物与证据边界

新增或扩展：[V]

- `src/eccentric_tde_observer/mixed_frame_ale.py`：任意合法固定点初值与固定步数诊断；
- `src/eccentric_tde_observer/mixed_frame_ale_log_p1.py`：对应的 log-P1 诊断接口；
- `scripts/phase7b5h_recurrence_decomposition.py`：单步映射复现、率账本和英文图；
- `tests/test_phase7b5h_recurrence_decomposition.py`：账本、主导分类和授权边界。

运行：

```bash
PYTHONPATH=scripts uv run python scripts/phase7b5h_recurrence_decomposition.py --force
uv run pytest -q
```

主要产物为 `outputs/phase7b5h_summary.json`、两个 CSV 和两张经过目视检查的英文图。[V]

本阶段完成后的现场完整回归为 `483 passed in 55.55s`。[V]

- `[A]`：参考状态守恒投影、固定截面与 $50\%$ 主导阈值；
- `[V]`：逐位单步复现、闭合账本、率定位与未收敛状态标志；
- `[O]`：单步注入内部的频率分区、组内表示和算符来源；
- `[L]`：本阶段没有新增文献物理。

Phase 7B5h 仍是数值表示诊断，不是物理时间演化、动态大气或 NLTE 输出谱。[A/V/O]
