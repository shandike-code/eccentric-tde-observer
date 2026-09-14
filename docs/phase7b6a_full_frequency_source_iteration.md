# Phase 7B6a：完整 9632 组单次源迭代实测

预注册：`outputs/phase7b6a_preregistered_full_frequency_source_iteration.json`  
上游：[[phase7b5z_lean_source_map|Phase 7B5z 精简源映射]]

## 1. 正式结论

`phase7b6a_gate_passed=true`，但 `full_column_fixed_point_authorized=false`。

两个隔离进程各执行 38 个交错频率块，并把互不重叠的核心结果写入同一临时 float64
memmap。76 个块无缝覆盖全部 9632 物理组；临时文件精确为 10,099,884,032 bytes，即
9.40625 GiB。完成 SHA-256 后文件已自动删除。[A/V]

- `[V]` 总墙钟时间为 244.877 s；两个进程各运行约 238.00 s，负载平衡；
- `[V]` 两进程峰值 RSS 为 2952.61 MiB 和 2968.78 MiB，均低于 6144 MiB；
- `[V]` 76 块算子时间总和为 426.30 s；并发将总墙钟压到约 4.08 min；
- `[V]` 全频输出非负且有限，最小强度为 0；零值来自当前物理边界/频带状态，没有作
  floor 或删除；
- `[V]` 第一次全频映射的最大相对变化为 0.282899，明确没有收敛。

## 2. 图像逐图解释

![Phase 7B6a full-frequency source iteration](../outputs/phase7b6a_full_frequency_source_iteration.png)

- **(a) All 76 frequency blocks**：蓝点为含微物理和输入场的总块时间，橙点为源映射时间；
  halo 最宽的中段更慢，端部块更短。
- **(b) Two-process load balance**：两个进程的总时间几乎相同，交错分块没有形成明显拖尾。
- **(c) Per-process memory**：两进程各约 2.9 GiB，均低于 6 GiB 单进程门；图中不是两者
  相加后的系统内存。
- **(d) Full-frequency source iteration**：实测墙钟约 245 s，低于 900 s 门。

## 3. 物理和权限边界

这只是冻结物质状态、boosted-Planck 初始场上的一次线性源映射。它没有形成散射固定点，
没有更新温度或布居，也没有产生可替换 modified-blackbody 的连续谱。[O]

若普通源迭代保持单次约 4 min，几十次迭代将达到小时级。下一阶段必须先验证收敛加速或
更合适的线性求解架构，并要求最终完整残差和能量账本复验；不得凭一次映射外推成收敛谱。
[A/O]

机读结果：`outputs/phase7b6a_full_frequency_source_iteration_summary.json`；逐进程记录：
`outputs/phase7b6a_worker1.json` 与 `outputs/phase7b6a_worker2.json`。
