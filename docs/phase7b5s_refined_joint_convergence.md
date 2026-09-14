# Phase 7B5s：更细 9632 组单单元联合参考

> [!summary] 阶段结论
> `[A-preregistered/V/O]` 五个更细的 9632 组固定点全部收敛，守恒、非负性、冻结输入和
> $6\,\mathrm{GiB}$ 单进程资源门均通过；但 32 对 48 方向、32 对 64 辐射子单元以及
> 32×32 对 48×64 联合比较的最大误差分别为 $1.221\times10^{-3}$、
> $7.626\times10^{-3}$ 和 $6.428\times10^{-3}$。三项都严格高于预声明的
> $10^{-3}$ 门，因此 32×32 候选不被接受，生产配置继续为空。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5s_preregistered_refined_joint_protocol|7B5s 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5r_joint_convergence|Phase 7B5r]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

## 1. 运行完整性

五个配置 24×32、32×32、48×32、32×64 和 48×64 分别在全新进程中运行。每个配置都
严格使用 9632 个物理频率组，频率边界 SHA-256 均为
`026d64479b28f36ab42bf05a2a1ecf087609aa21aaa44976c9b5f83cc67b60a6`。全部固定点都在
35 次迭代内达到 $10^{-10}$ 容差；最大全局联立残差为
$1.295\times10^{-12}$，最大绝对能量账本残差为 $8.733\times10^{-11}$，最小强度为 0。
`[V]`

24×32 结果哈希为
`db4f4fde7ea4811757b0466e210cc82d4b92ba4eea50f1403df0a4ec3e3e1994`，与 Phase 7B5r
同配置逐位一致。这确认加密审计没有改动已冻结算子、压力状态或默认初值。`[V]`

## 2. 预声明收敛结果

| 比较 | 最大误差 | 最敏感量 | 判定 |
|---|---:|---|---|
| 24 对 48 方向，32 子单元 | $2.945\times10^{-3}$ | H I 光致电离率 | 控制失败 |
| 32 对 48 方向，32 子单元 | $1.221\times10^{-3}$ | H I 光致电离率 | 生产门失败 |
| 32 对 64 子单元，32 方向 | $7.626\times10^{-3}$ | H I 光致电离率 | 生产门失败 |
| 32×32 对 48×64 联合 | $6.428\times10^{-3}$ | H I 光致电离率 | 生产门失败 |

角度加密已经接近目标，但不能把 $1.221\times10^{-3}$ 向下取整成通过。辐射子网格误差
仍约为 $0.76\%$，并同时出现在平均强度、H I/He I 率、末态辐射能量和全谱 L1 差中；
这不是一个孤立坏 bin，也不是有符号加热量接近零造成的相对误差假象。`[V]`

## 3. 32×32 联合候选

32×32 相对 48×64 的完整误差账本为：

| 量 | 相对误差 |
|---|---:|
| 频率积分体积平均共动强度 | $5.691\times10^{-3}$ |
| H I 光致电离率 | $6.428\times10^{-3}$ |
| He I 光致电离率 | $5.920\times10^{-3}$ |
| He II 光致电离率 | $3.255\times10^{-5}$ |
| 末态辐射面密度 | $5.691\times10^{-3}$ |
| 双侧逸出通量 | $2.307\times10^{-4}$ |
| 积分物质加热 | $2.651\times10^{-4}$ |
| 体积平均共动谱 L1 差 | $5.704\times10^{-3}$ |

He II、逸出通量和物质加热已经通过，但预注册要求所有连续量同时通过。因此不能只选这些
较不敏感的量批准候选。低阈值 H I/He I 率以及辐射能量对当前深度离散更敏感。`[V]`

## 4. 图怎么看

![Phase 7B5s refined joint convergence](../outputs/phase7b5s_refined_joint_convergence.png)

**左上图。** 蓝柱比较 24 与 48 方向，橙柱比较 32 与 48 方向；黑色虚线为严格
$10^{-3}$ 门。角度加密使所有误差下降，但橙色的平均强度、H I/He I 率、辐射能量和谱
L1 仍略高于门，故 32 方向尚不能正式验收。

**右上图。** 32 与 64 辐射子单元的差异由橙柱给出。平均强度、H I/He I 率、辐射能量
和谱 L1 集体处于约 $0.68\%$--$0.76\%$，明显高于角度误差，说明当前主收敛瓶颈是辐射
深度离散。

**左下图。** 绿色柱是唯一预声明的 32×32 对 48×64 联合生产比较。五个能量或 H I/He I
相关量失败，所以即使其余三个量通过，总门仍失败。

**右下图。** 横轴是活跃辐射未知量，纵轴是各全新进程的峰值 RSS。最大 48×64 配置含
$29{,}589{,}504$ 个活跃未知量，耗时 $159.11\,\mathrm{s}$，峰值
$2876.00\,\mathrm{MiB}$；它通过了预注册的 $6144\,\mathrm{MiB}$ 资源门。这只是单单元
实测资源包络，不能直接视为全柱可行性。`[V/O]`

## 5. 对收敛阶与更细暴力加密的限制

Phase 7B5r 的 16 对 32 子单元误差为 $1.482\times10^{-2}$，本阶段 32 对 64 的误差为
$7.626\times10^{-3}$，只缩小约 $1.94$ 倍。这与当前区间内接近一阶的慢收敛相容，但仅凭
两段分辨率不能证明渐近阶数。`[A-inference/O]`

如果误差每次加倍分辨率都近似减半，则要把 $7.626\times10^{-3}$ 压到 $10^{-3}$ 以下，
可能需要约 256 个子单元；这只是资源规划外推，不是收敛保证。按当前数组结构，32 方向与
512 子单元约有 $1.578\times10^{8}$ 个活跃辐射未知量，已经不适合在 16 GiB 主机上盲目
暴力推进。`[A-inference/O]`

因此下一门应先分离检查空间输运离散阶、单元界面误差和方向边界的不连续响应，再决定是否
值得运行 128/256 子单元或改进离散。任何离散改动都必须先预注册，并重新通过相同守恒、
非负性、连续量和资源门；不能通过放宽 $10^{-3}$ 门、裁剪或事后重归一化来验收。`[O]`

## 6. 正式判定与边界

本阶段正式判定为 `phase7b5s_gate_passed=false`，并设置
`accepted_one_cell_configuration=null`。9632 频率预算仍是已经授权的正式预算；失败的是
单单元角度--辐射深度生产离散。全柱、全轨道、物质反馈、Phase 4 替换和 UVOT 继续关闭。
`[A/V/O]`

## 7. 文件与复现

核心文件：

- `scripts/phase7b5s_preregister_refined_joint_protocol.py`；
- `scripts/phase7b5s_refined_joint_convergence.py`；
- `outputs/phase7b5s_preregistered_refined_joint_protocol.json`；
- `outputs/phase7b5s_refined_joint_summary.json`；
- `outputs/phase7b5s_refined_joint_runs.csv`；
- `outputs/phase7b5s_refined_joint_errors.csv`；
- `outputs/phase7b5s_refined_joint_convergence.png`。

复现命令为：

```bash
PYTHONPATH=scripts uv run python scripts/phase7b5s_preregister_refined_joint_protocol.py
PYTHONPATH=scripts uv run python scripts/phase7b5s_refined_joint_convergence.py --force
```

第二条命令会在保存全部结果后以非零状态退出，因为预声明科学门失败；这不是求解器崩溃。
本阶段专项测试为 `10 passed in 0.29s`；现场完整回归为
`648 passed in 60.30s`。`[V]`
