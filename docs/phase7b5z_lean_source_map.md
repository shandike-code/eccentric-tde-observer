# Phase 7B5z：精简中间源映射性能门

预注册：`outputs/phase7b5z_preregistered_lean_source_map.json`  
上游失败：[[phase7b5y_remap_batch_performance|Phase 7B5y 批次候选]]

## 1. 候选边界

block-Jacobi 的中间迭代只需要新强度、变化量和非负性。旧路径在每个块的一次映射后又
重新计算共动角场、散射发射率、联立残差、能量账本和四力诊断；这些量不反馈到已经得到的
强度更新。7B5z 新增 `source_map_only=True`，只把这些末态诊断延后到全局收敛后。[A]

它不改变 Lorentz 搬移、频率加法顺序、空间特征扫掠、turning-ray、碰撞系数或边界条件。
正式收敛结果仍必须另跑完整诊断，不能只保存精简映射。[A/O]

## 2. 正式结果

`phase7b5z_gate_passed=true`：

- `[V]` 两次最坏整深度块的最终强度哈希都与 7B5x 完全相同；最小强度和固定点变化误差
  也都是 0；
- `[V]` 算子时间为 6.196 s 和 6.077 s，中位 6.137 s，相对 9.659 s 基线加速
  1.574 倍；
- `[V]` 最大峰值 RSS 为 2784.73 MiB，低于 6 GiB 门；
- `[V]` 7B5y 的正式失败仍保留，未把它改写为通过。

![Phase 7B5z lean source map](../outputs/phase7b5z_lean_source_map.png)

左图显示完整诊断基线、精简映射中位时间和冻结门；中图确认内存没有超门；右图的两个
绿色柱表示强度哈希逐位相同。[V]

本阶段只授权把精简路径接入流式调度，并实测一次完整 9632 组源迭代；不授权完整柱固定点
或全轨道。[O]

机读结果：`outputs/phase7b5z_lean_source_map_summary.json`。
