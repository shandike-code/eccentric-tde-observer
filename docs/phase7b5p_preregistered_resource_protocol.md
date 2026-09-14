# Phase 7B5p：4816/9632 隔离进程资源审计预注册

> [!summary] 协议结论
> `[A-preregistered/O]` 本阶段只测量 7B5o 已暴露最坏状态上的单单元资源，不重新检验
> 科学精度，也不修改 4816 预算。协议在测量前冻结为 SHA-256
> `3ccb468e24def10262489a2c02d8124a103ec1fd2aeae035b4b05e7cb164201c`。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5o_initial_converged_validation|Phase 7B5o]] ·
[[eccentric_tde_observer/docs/phase7b5p_isolated_resource_profile|Phase 7B5p 结果]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]

## 1. 为什么需要独立资源门

7B5o 已证明 9632 组 master 通过能量与 H/He 联合精度门，而精确 4816 叶候选在 He II 上
严格失败。此前资源数字只有算子返回数组和一次进程内计时，不能回答新预算在当前机器上的
实际单单元进程峰值。因此 7B5p 在不改变任何科学输入的前提下，增加隔离进程测量。[V/O]

## 2. 冻结对象

- 状态固定为 7B5o 已暴露的 `signed width change q80` 收敛源；它是资源压力状态，**不是**
  新的科学留出。[A]
- 表示固定为精确 4816 叶候选和完整 9632 组 master；候选边界哈希固定为
  `2f905d8ad0df879df3cba4311921a37233f082d5022e1630ace1934f8053bad7`。[V]
- 每种表示各运行 5 个全新子进程；顺序预先交错为
  `candidate, master, master, candidate, candidate, master, master, candidate, candidate, master`。[A]
- 报告进程峰值 RSS、加载后到算子完成的高水位增量、单步算子时间、完整新进程墙钟时间
  和返回数组大小。[V]

## 3. 完整性门

必须同时满足：[A/V]

1. 10 个子进程全部正常退出且 PID 各不相同；
2. 同一表示的数值结果哈希在 5 次运行中一致；
3. 返回数组字节数逐位匹配 7B5o；
4. 4816 候选边界哈希不变；
5. macOS 的 `ru_maxrss` 按 byte、Linux/BSD 按 KiB 显式换算，未知平台直接拒绝；
6. 最大值必须保留，不能只报告中位数或删除高水位运行。

## 4. 明确不授权的内容

该协议不改变频率预算，不授权角度阶、辐射子网格、全轨道、物质反馈、Phase 4 替换或
UVOT。它也不允许用已暴露状态再次调整 4816 候选。[O]

## 5. 复现

```bash
PYTHONPATH=scripts uv run python scripts/phase7b5p_preregister_resource_protocol.py
PYTHONPATH=scripts uv run python scripts/phase7b5p_isolated_resource_profile.py --force
uv run pytest -q tests/test_phase7b5p_isolated_resource_profile.py
```

机器协议为 `outputs/phase7b5p_preregistered_resource_protocol.json`。[V]

