# Phase 7B5y：增大频率搬移列批次的性能候选失败

上游：[[phase7b5x_full_depth_block_probe|Phase 7B5x 整深度单块实测]]  
下游：[[phase7b5z_lean_source_map|Phase 7B5z 精简源映射]]

## 正式结论

`phase7b5y_gate_passed=false`，候选没有保留。协议只把互不相干列的批处理元素预算从
2,000,000 增到 16,000,000，不改变任一频率区间内部的加法顺序。[A-preregistered]

- `[V]` 两次最坏块输出哈希与 7B5x 完全相同，四个标量误差均为 0；
- `[V]` 但算子时间为 10.309 s 和 10.111 s，中位 10.210 s，慢于 9.659 s 基线并失败
  预注册的 9.176 s 门；
- `[V]` 最大峰值 RSS 上升到 3222.02 MiB，虽低于 6 GiB 资源门，却没有换来加速；
- `[V]` 正式代码已恢复 2,000,000 的原批次预算，源文件 SHA-256 回到
  `363c179e8aae73ea74f9ed15c17c24a6efc84be580ac37436ec7a6b85a4dc08c`。

![Phase 7B5y remap batch performance](../outputs/phase7b5y_remap_batch_performance.png)

左图比较算子时间并显示候选没有越过性能门；中图显示额外内存；右图确认两个输出哈希
精确相同。失败说明当前瓶颈不能靠简单扩大 Numpy 批次解决。[V]

机读协议：`outputs/phase7b5y_preregistered_remap_batch_performance.json`；结果：
`outputs/phase7b5y_remap_batch_performance_summary.json`。
