# Phase 7B5o：初始态/收敛态独立验证预注册

> [!summary] 协议状态
> `[A-preregistered]` 7B5o 保留 7B5n 的 1--2--4 分层 P0 家族、整数动态规划目标、
> 4816 叶预算和联合能量/H/He 门。为避免再次预猜不存在的源迭代编号，新验证对每个全新
> 几何病例使用按构造必然存在的“初始态”和“参考收敛态”。

导航：[[eccentric_tde_observer/docs/phase7b5n_preregistered_protocol|Phase 7B5n]] ·
[[eccentric_tde_observer/docs/phase7b5m_actual_multiresolution_validation|Phase 7B5m]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

---

## 1. 与 7B5n 的关系

7B5n 的失败只说明固定的 $n=12$ 状态并非所有病例都存在，不构成 1--2--4 表示的数值
结论。其六个病例已经被打开，因此 7B5o 明确排除这些病例，并选择新的物态分位点。[V/A]

表示与优化目标完全不变：每个父带使用 $k_{p}\in\{1,2,4\}$ 个 P0 叶，在

$$
\sum_{p} k_{p}=4816
$$

下，用整数动态规划最小化开发集能量、H I、He I 和 He II 归一化局域缺陷的和。[A]

## 2. 新验证病例

病例继续只由 `phase7b4r_depth128_phase2048.npz` 的几何和物态字段确定，不读取任何新
频率误差：[A]

1. 下一时刻表面温度的 40% 和 60% 分位；
2. 有符号单元中心速度的 20% 和 80% 分位；
3. 有符号单元宽度变化的 20% 和 80% 分位。

选择时排除开发集三个病例和 7B5n 六个旧留出病例。每个目标分位取差值最小的未占用
`(phase, depth)`；平局按 NumPy 行主序。[A]

## 3. 两个保证存在的源状态

每个病例只验证两个由参考算子定义的状态：[A/V]

- `initial`：第一次源更新前观察器保存的 $n=0$ 强度；
- `converged`：参考求解器收敛时观察器保存的最后一个强度状态。

协议不预先指定收敛需要多少次迭代。参考求解必须自身通过固定点、能量和联立残差门，最后
一个观察器状态才有资格进入验证。这样状态存在性由求解过程保证，不需要读取候选误差后
修改编号。[A]

六个病例共形成 12 个全新验证状态。它们不得反馈到频率网格、动态规划目标或预算。[A]

## 4. 判定门

7B5o 沿用 7B5n 的冻结门：[A]

- 候选恰好 4816 个物理叶；
- 候选和 9632 组 master 的总能量相对误差严格小于 $10^{-3}$；
- 两者的 H I、He I、He II 光致电离率相对误差均严格小于 $10^{-3}$；
- 投影误差小于 $2\times10^{-13}$，独立率求积误差小于 $2\times10^{-6}$；
- 参考源迭代、正式候选算子和 master 算子都必须收敛；
- 验证前后网格哈希不变；
- 不删除失败点，不使用 `nan_to_num`、任意 `clip`、floor 或事后重归一化。

通过只授权下一项角度--辐射子网格单单元门；不直接授权全轨道、物质反馈、Phase 4 替换
或 UVOT。[A/O]

## 5. 冻结命令

```bash
PYTHONPATH=scripts uv run python scripts/phase7b5o_preregister_protocol.py
```

该命令只读取材料轨道、几何和已经冻结的 7B5n 排除清单，不运行新病例的辐射求解。[V]

冻结后的 7B5o 协议文件为 `outputs/phase7b5o_preregistered_protocol.json`，SHA-256 是
`ff63f6f46cd71c96089c714a600f8ef7a31d71bf92afd306aec743a89e94a176`。正式验证必须在运行
任何新病例前核对该值。[V]

- `[V]`：7B5n 失败状态、排除病例、材料哈希和确定性索引；
- `[A-preregistered]`：新病例、初始/收敛状态、表示、预算和判据；
- `[O]`：角度、辐射子网格、全轨道和物质反馈。

## 6. 执行结果

正式验证已经完成：协议、参考源、9632 master 和全部算子控制通过；4816 叶候选在 He II
留出点以 $1.000546\times10^{-3}$ 严格失败。完整数字、三张英文图和后续边界见
[[eccentric_tde_observer/docs/phase7b5o_initial_converged_validation|Phase 7B5o 验证报告]]。[V/O]
