# Phase 7B5r：9632 组单单元角度--辐射子网格联合门

> [!summary] 阶段结论
> `[A-preregistered/V/O]` 七个 9632 组完整固定点全部收敛，守恒、非负性和冻结频率边界
> 均通过；但 16 对 24 方向、16 对 32 辐射子单元以及 16×16 对 24×32 联合比较的最大
> 误差分别为 $5.448\times10^{-3}$、$1.482\times10^{-2}$ 和
> $9.589\times10^{-3}$。三者均严格高于预声明的 $10^{-3}$ 门，因此不接受任何单单元
> 生产配置，也不进入全柱、全轨道或物质反馈。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5r_preregistered_joint_convergence_protocol|7B5r 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5q_converged_fixed_point_resource|Phase 7B5q]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

## 1. 运行完整性

七个配置分别在新进程中运行，物理频率组均严格为 9632，频率边界 SHA-256 保持为
`026d64479b28f36ab42bf05a2a1ecf087609aa21aaa44976c9b5f83cc67b60a6`。全部固定点在
35--45 次迭代内达到 $10^{-10}$ 容差；最大全局联立残差为
$5.671\times10^{-11}$，最大绝对能量账本残差为 $1.838\times10^{-10}$，最小强度为 0。
`[V]`

8 方向×1 单元的结果哈希为
`5336b224e4ad8d3b5d3c2ab01902a03cba243d9c8529fab57fbb9cfd202a62b6`，与 Phase 7B5q
的 9632 组默认初值结果逐位一致。这验证了新审计没有悄悄改变原算子或基线输入。`[V]`

## 2. 预声明收敛结果

| 比较 | 最大误差 | 最敏感量 | 判定 |
|---|---:|---|---|
| 8 对 24 方向，1 单元 | $3.148\times10^{-2}$ | H I 光致电离率 | 失败 |
| 16 对 24 方向，1 单元 | $5.448\times10^{-3}$ | H I 光致电离率 | 失败 |
| 8 对 32 子单元，16 方向 | $4.322\times10^{-2}$ | H I 光致电离率 | 失败 |
| 16 对 32 子单元，16 方向 | $1.482\times10^{-2}$ | H I 光致电离率 | 失败 |
| 16×16 对 24×32 联合 | $9.589\times10^{-3}$ | H I 光致电离率 | 失败 |

16 对 24 方向时，H I、He I、频率积分平均强度和谱 L1 差仍为约 $0.50\%$--$0.54\%$；
He II 率、双侧逸出通量和物质加热已经低于 $10^{-3}$。16 对 32 子单元时，H I、He I、
平均强度和谱 L1 差仍为约 $1.32\%$--$1.48\%$，而 He II、逸出通量和物质加热已经通过。
`[V]`

这说明失败不是某个坏频率 bin，也不是只有有符号加热量接近零造成的相对误差放大：
bolometric 平均强度、H I/He I 率和全谱 L1 差同时失败。不能只保留已通过的 He II、通量
或加热项来批准配置。`[V]`

## 3. 联合门为什么仍失败

联合候选 16 方向×16 子单元相对 24×32 参考的误差为：

| 量 | 相对误差 |
|---|---:|
| 频率积分体积平均共动强度 | $8.478\times10^{-3}$ |
| H I 光致电离率 | $9.589\times10^{-3}$ |
| He I 光致电离率 | $8.707\times10^{-3}$ |
| He II 光致电离率 | $1.284\times10^{-4}$ |
| 末态辐射面密度 | $8.478\times10^{-3}$ |
| 双侧逸出通量 | $3.188\times10^{-4}$ |
| 积分物质加热 | $3.583\times10^{-4}$ |
| 体积平均共动谱 L1 差 | $8.522\times10^{-3}$ |

低阈值 H I/He I 率和能量密度对角向、深度离散比顶部逸出通量更敏感。这里仅能把它描述为
当前暴露状态上的数值敏感性；单个压力单元不能证明完整柱中哪一频带或空间层最终主导。
`[V/O]`

## 4. 图怎么看

![Phase 7B5r joint convergence](../outputs/phase7b5r_joint_convergence.png)

**左上图。** 蓝柱是 8 对 24 方向，橙柱是 16 对 24；黑色虚线为 $10^{-3}$。角度加密
使误差系统下降，但 16 方向的平均强度、H I/He I 率、辐射能量和谱 L1 仍高于门。

**右上图。** 蓝柱是 8 对 32 子单元，橙柱是 16 对 32。子网格加密同样持续降低误差，
但 16 子单元的能量与 H I/He I 相关量仍约为百分之一，尚不能称为收敛。

**左下图。** 绿色柱是唯一预声明联合生产比较。只有 He II、逸出通量和物质加热落在虚线
下；其余五项失败，所以总门失败。

**右下图。** 横轴是活跃辐射未知量，纵轴是每个新进程的峰值 RSS。最昂贵 24×32 参考有
$7{,}397{,}376$ 个活跃未知量，运行 $37.89\,\mathrm{s}$，峰值
$1046.47\,\mathrm{MiB}$；16×32 为 $758.97\,\mathrm{MiB}$。这是真实单单元资源包络，
不是全柱内存外推。`[V/O]`

## 5. 正式判定与下一门

本阶段正式判定为 `phase7b5r_gate_passed=false`，并设置
`accepted_one_cell_configuration=null`。9632 仍是已经授权且通过频率科学门的新预算；失败
的是角度--辐射子网格生产离散，不是频率预算本身。`[A/V]`

下一步只能继续单单元加密参考，例如增加 32 或 48 方向以及 64 个辐射子单元，并在运行前
重新冻结候选、参考、资源上限和同一组连续量。当前结果不能预先保证 24×32 已经收敛，
也不能把门槛放宽到百分之一。全柱、全轨道、温度--布居反馈、Phase 4 替换和 UVOT 继续
关闭。`[O]`

## 6. 文件与复现

核心文件：

- `scripts/phase7b5r_preregister_joint_convergence_protocol.py`；
- `scripts/phase7b5r_joint_convergence.py`；
- `outputs/phase7b5r_preregistered_joint_convergence_protocol.json`；
- `outputs/phase7b5r_joint_convergence_summary.json`；
- `outputs/phase7b5r_joint_convergence_runs.csv`；
- `outputs/phase7b5r_joint_convergence_errors.csv`；
- `outputs/phase7b5r_joint_convergence.png`。

复现命令为：

```bash
PYTHONPATH=scripts uv run python scripts/phase7b5r_preregister_joint_convergence_protocol.py
PYTHONPATH=scripts uv run python scripts/phase7b5r_joint_convergence.py --force
```

第二条命令会在保存全部失败证据后以非零状态退出，这是预声明科学门失败的预期行为，不是
文件缺失或求解器崩溃。专项测试通过；本阶段收尾后的现场完整回归为
`641 passed in 60.27s`。`[V]`
