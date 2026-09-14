# Phase 7B5p：4816/9632 隔离进程资源测量

> [!summary] 阶段结论
> `[A/V/O]` 冻结协议和 10 个新进程完整性门全部通过。4816 叶候选与 9632 master 的
> 单单元进程峰值 RSS 中位数分别为 $158.86\,\mathrm{MiB}$ 和
> $190.44\,\mathrm{MiB}$，最大值分别为 $159.17\,\mathrm{MiB}$ 和
> $191.50\,\mathrm{MiB}$。扣除共同加载基线后的算子高水位增量与单步时间约放大
> $2.04$ 倍和 $1.94$ 倍。该证据支持 9632 组在下一**单单元**门上的资源可行性，
> 但不等于完整 256 深度柱的峰值内存，也没有自动修改频率预算。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5p_preregistered_resource_protocol|7B5p 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5o_initial_converged_validation|Phase 7B5o]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]

## 1. 测量定义

每次运行都启动新的 Python 子进程，加载冻结的一个单元输入，再执行与 7B5o 资源账本完全
相同的一次 P0 固定点映射。进程峰值 RSS 包含解释器、数值模块、输入和一步结果；算子高水位
增量则是算子完成时峰值减去输入加载后的进程高水位。[V]

被计时的操作只有一次诊断映射，因此结果里的 `fixed_point_iterations=1` 和约
$1.5\times10^{-2}$/$2.3\times10^{-2}$ 联立残差**不是收敛门**。输入源另由参考求解器
在 43 次迭代收敛，其联立残差和能量账本残差分别为
$5.689\times10^{-11}$ 和 $1.839\times10^{-10}$。[V]

## 2. 结果

| 量 | 4816 叶候选 | 9632 master | master/candidate |
|---|---:|---:|---:|
| 中位进程峰值 RSS | $158.859\,\mathrm{MiB}$ | $190.438\,\mathrm{MiB}$ | $1.199$ |
| 最大进程峰值 RSS | $159.172\,\mathrm{MiB}$ | $191.500\,\mathrm{MiB}$ | $1.203$ |
| 中位算子高水位增量 | $29.641\,\mathrm{MiB}$ | $60.578\,\mathrm{MiB}$ | $2.044$ |
| 最大算子高水位增量 | $30.891\,\mathrm{MiB}$ | $62.203\,\mathrm{MiB}$ | $2.014$ |
| 中位单步算子时间 | $0.03520\,\mathrm{s}$ | $0.06813\,\mathrm{s}$ | $1.935$ |
| 中位完整子进程墙钟 | $0.66498\,\mathrm{s}$ | $0.70234\,\mathrm{s}$ | $1.056$ |
| 返回数组 | $2.13131\,\mathrm{MiB}$ | $4.26241\,\mathrm{MiB}$ | $1.9999$ |

共同 Python/模块基线约为 $128$--$130\,\mathrm{MiB}$，所以完整进程峰值比只有约
$1.20$；扣除该基线后，增量内存和算子时间都接近组数翻倍预期。[V]

![Phase 7B5p isolated resource profile](../outputs/phase7b5p_isolated_resource_profile.png)

**左图怎么看。** 每个点是一条独立 PID 的进程高水位，不能把它解释成 256 深度全柱的
并行峰值。两组点完全分离，且 9632 的 5 次运行都低于 $192\,\mathrm{MiB}$；这说明当前
机器上的单单元压力测试没有出现数量级资源跃迁。[V]

**右图怎么看。** 9632 的一次算子映射约需 4816 的两倍时间，符合物理组数翻倍。完整
子进程墙钟没有翻倍，是因为导入模块和准备过程占据共同固定成本；正式全柱运行不能用这个
$1.056$ 倍墙钟比估算。[V/O]

## 3. 完整性和数值控制

- 10 个 worker 全部退出为 0，PID 全异；同一表示的结果哈希在 5 次运行内完全一致。[V]
- 4816 边界哈希保持不变，投影能量误差为 $1.235\times10^{-16}$；9632 为
  $2.126\times10^{-16}$。[V]
- 返回数组逐字节匹配 7B5o；没有 `nan_to_num`、任意 `clip`、floor、删点或事后归一化。[V]
- 图内标题、坐标和标签均为英文，且已目视检查无裁切或标签重叠。[V]

## 4. 决策含义和剩余限制

7B5o 提供的是科学精度证据：9632 通过、4816 严格失败。7B5p 提供的是本机单单元资源证据：
9632 的实测绝对峰值低于 $192\,\mathrm{MiB}$，相对 4816 的算子增量资源约翻倍。这使
“批准 9632 后进入角度--辐射子网格单单元门”成为当前最直接路线。[A/V]

它仍不能证明：[O]

1. 256 深度单元同时驻留时的真实峰值；
2. 角度阶、辐射子网格和固定点迭代次数已经收敛；
3. 全轨道动态非局域谱可在目标资源内完成；
4. 已经可以替换 Phase 4、生成可信 X-ray 或进入 UVOT。

因此 `frequency_budget_changed=false`，需要显式批准后才能把 9632 作为下一门的新预算。[O]

## 5. 复现

```bash
PYTHONPATH=scripts uv run python scripts/phase7b5p_preregister_resource_protocol.py
PYTHONPATH=scripts uv run python scripts/phase7b5p_isolated_resource_profile.py --force
uv run pytest -q tests/test_phase7b5p_isolated_resource_profile.py
uv run pytest -q
```

机器产物包括 `outputs/phase7b5p_resource_profile_summary.json`、10 行运行 CSV、两份冻结输入
和一张已目视检查的英文图。[V] 本阶段收尾后的现场完整回归为
`627 passed in 61.04s`。[V]
