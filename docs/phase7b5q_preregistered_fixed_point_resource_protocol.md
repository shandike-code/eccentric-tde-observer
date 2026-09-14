# Phase 7B5q：完整固定点单单元资源审计预注册

> [!summary] 协议结论
> `[A-preregistered/O]` 7B5q 不修改 4816 预算，也不进入角度、辐射子网格或全柱门。
> 它只在 7B5p 的冻结输入上比较两种表示、两种预声明初值的完整固定点资源。协议在打开
> 结果前冻结为 SHA-256
> `055005e2d3285744be531c06a0f08cea02f22de6af9979fce3dbc2d754b04143`。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5p_isolated_resource_profile|Phase 7B5p]] ·
[[eccentric_tde_observer/docs/phase7b5q_converged_fixed_point_resource|Phase 7B5q 结果]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]

## 1. 要回答的问题

7B5p 测量的是一次诊断映射，不能给出完整源迭代的运行时间和高水位。7B5q 保持同一
`signed width change q80` 收敛压力状态、8 个全区间 Gauss--Legendre 方向、4816 候选和
9632 master，只问：[A]

1. 完整固定点是否在两种初值下都收敛；
2. 收敛需要多少次迭代；
3. 完整固定点的隔离单单元峰值 RSS 和时间是多少；
4. 两种初值是否回到同一最终强度。

## 2. 两种冻结初值

- `projected_converged`：把独立高分辨率参考的收敛源守恒投影到目标表示，模拟生产中较好的
  时间步 warm start；[A]
- `default_initial`：不传入源迭代猜测，采用算子默认初始辐射场，给出较保守的迭代路径。[A]

每个“表示×初值”配置各运行 5 个全新进程，共 20 个；顺序在协议中预先交错。[A/V]

## 3. 预声明门

- 固定点容差为 $10^{-10}$，最大 8192 次迭代；
- 全局联立残差和绝对能量账本残差都必须严格低于 $10^{-9}$；
- 最小强度不得低于 0；
- 两种初值的最终实验室系强度最大相对差必须严格低于 $10^{-8}$；
- 20 个 PID 必须全异，同配置结果哈希必须确定，边界哈希不得改变；
- 最大内存和最大时间必须保留，不能删除高水位运行。[A/V]

$10^{-8}$ 的跨初值门比固定点容差宽 100 倍，用来验证两条有限迭代轨迹回到同一数值解，
不是调节物理输出的后验阈值。[A]

## 4. 不授权内容

协议明确保持 `frequency_budget_changed=false`，也不授权角度/辐射子网格、完整柱、全轨道、
物质反馈、Phase 4 替换或 UVOT。[O]

## 5. 复现

```bash
PYTHONPATH=scripts uv run python scripts/phase7b5q_preregister_fixed_point_resource_protocol.py
PYTHONPATH=scripts uv run python scripts/phase7b5q_converged_fixed_point_resource.py --force
```

机器协议为 `outputs/phase7b5q_preregistered_fixed_point_resource_protocol.json`。[V]
