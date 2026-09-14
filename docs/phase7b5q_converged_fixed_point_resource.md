# Phase 7B5q：完整固定点单单元资源包络

> [!summary] 阶段结论
> `[A/V/O]` 20 个隔离进程全部通过。投影收敛源和默认初值分别需要 29 和 43 次迭代；
> 4816/9632 在较保守默认初值下的中位完整固定点时间为
> $0.1822/0.3668\,\mathrm{s}$，中位进程峰值为
> $163.03/198.45\,\mathrm{MiB}$。所有运行中的最高峰值
> $209.44\,\mathrm{MiB}$ 被保留。两种初值的最终强度只差约
> $2\times10^{-10}$。这进一步支持 9632 的单单元资源可行性，但仍不是全柱峰值，
> 也没有修改频率预算。

> [!warning] 角度标签更正
> 冻结输入实际含 8 个覆盖 $[-1,1]$ 的 Gauss--Legendre 方向；早期讲义把它误写成 S16。
> 这只是标签更正，不改变任何 7B5q 数值。真正的 8/16/24 方向比较见
> [[eccentric_tde_observer/docs/phase7b5r_joint_convergence|Phase 7B5r]]。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5q_preregistered_fixed_point_resource_protocol|7B5q 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5p_isolated_resource_profile|Phase 7B5p]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

## 1. 收敛结果

两种表示的投影收敛源都恰好在 29 次迭代收敛，默认初值都在 43 次收敛。全部 20 次运行的
最大联立残差不超过 $5.676\times10^{-11}$，最大绝对能量账本残差为
$1.838\times10^{-10}$，最小强度为严格的 0。[V]

4816 和 9632 的两种初值最终实验室系强度最大相对差分别为
$2.081\times10^{-10}$ 和 $1.985\times10^{-10}$，远低于预声明的 $10^{-8}$ 门。
初值改变了迭代成本，没有改变最终固定点。[V]

## 2. 资源结果

| 表示与初值 | 中位/最大峰值 RSS | 中位/最大算子时间 | 中位算子内存增量 | 迭代数 |
|---|---:|---:|---:|---:|
| 4816，投影收敛源 | $162.80/163.36\,\mathrm{MiB}$ | $0.1406/0.1649\,\mathrm{s}$ | $33.58\,\mathrm{MiB}$ | 29 |
| 4816，默认初值 | $163.03/165.75\,\mathrm{MiB}$ | $0.1822/0.2205\,\mathrm{s}$ | $34.30\,\mathrm{MiB}$ | 43 |
| 9632，投影收敛源 | $199.14/209.44\,\mathrm{MiB}$ | $0.2552/0.2952\,\mathrm{s}$ | $68.69\,\mathrm{MiB}$ | 29 |
| 9632，默认初值 | $198.45/206.55\,\mathrm{MiB}$ | $0.3668/0.3838\,\mathrm{s}$ | $68.30\,\mathrm{MiB}$ | 43 |

投影初值下，master/candidate 的中位总峰值、算子增量和时间比分别为
$1.223$、$2.046$ 和 $1.815$；默认初值下分别为 $1.217$、$1.991$ 和 $2.014$。[V]

![Phase 7B5q converged fixed-point resource](../outputs/phase7b5q_fixed_point_resource.png)

**左图怎么看。** 每列五点来自五个新 PID。完整固定点相对 7B5p 的一步映射只略微提高
峰值，因为迭代循环重复使用主要工作数组，而不是为 29 或 43 次迭代同时保留副本。9632
投影初值中出现的 $206$--$209\,\mathrm{MiB}$ 高水位点被完整保留；资源规划应参考最大值，
不能只看约 $199\,\mathrm{MiB}$ 的中位数。[V]

**右图怎么看。** 默认初值比投影收敛源需要更多迭代，因此两种表示都明显变慢。默认初值
下 9632/4816 时间比约为 $2.01$，与频率组数翻倍一致；投影初值下的比值约 $1.81$，反映
固定开销和短运行抖动，而不是 9632 获得了物理捷径。[V]

## 3. 与 7B5p 的关系

7B5p 给出“一步算子”的干净成本比例；7B5q 给出“完整固定点”的实际迭代包络。两者共同
说明：[A/V]

- 9632 的单单元算子数组和时间代价大致是 4816 的两倍；
- 共同解释器/模块基线使完整进程峰值比例只有约 $1.22$；
- 迭代次数增加主要增加总时间，不使峰值按迭代次数倍增；
- 当前证据支持下一单单元角度--辐射子网格门，但不支持直接外推完整柱或全轨道。

## 4. 尚不能推出什么

本阶段仍没有测量或授权：[O]

1. 多深度单元同时驻留时的峰值和求解器工作空间；
2. 角阶、辐射子网格与频率组的联合收敛；
3. 全轨道时间步和温度--布居反馈；
4. Phase 4 替换、真实 UVOT 采样或动态 NLTE 线形成。

因此预算判定仍为 `frequency_budget_changed=false`。[O]

## 5. 复现

```bash
PYTHONPATH=scripts uv run python scripts/phase7b5q_preregister_fixed_point_resource_protocol.py
PYTHONPATH=scripts uv run python scripts/phase7b5q_converged_fixed_point_resource.py --force
uv run pytest -q tests/test_phase7b5q_converged_fixed_point_resource.py
uv run pytest -q
```

机器产物为汇总 JSON、20 行运行 CSV 和一张已目视检查的英文图。[V] 本阶段收尾后的
现场完整回归为 `634 passed in 62.68s`。[V]
