# 17:34 巡检：73308 第二轮 final 反馈的局部耗时异常

四张 map 均已完成，第二轮 previous 76/76；final 在 17:33:18 为 40/76，17:36:30 已启动 block42/43。作业仍 RUNNING，尚未生成第二轮反馈判决，不能补造结果或宣告卡死。

final 的 block0–17 多为 14–16 s；block20/21 为 152 s；block22/23 为 554/617 s；block24/25 为 1031/1350 s。随后 block26–39 为约22–46 s。逐块耗时差异显著，不能按前段平均速度外推剩余完成时间。

在原 73308 allocation 内做两次 `srun --overlap` 只读探针，每次 timeout 20 s，没有新增科学 worker或修改协议：

- 17:35:40：block40/41，elapsed 141 s，CPU time 141/140 s，CPU 99.5%/99.1%，各一个线程；RSS约2.05/2.34 GiB；允许CPU为41–42,105–106。此刻两个进程的 `/proc/PID/io` read_bytes/write_bytes均为0（缓存命中可如此，不代表此前没有读取）。
- 17:36:30：block42/43已启动，elapsed与CPU time均13 s，约100% CPU。原始第二次探针见 `handoff/evidence/73308-round2-live-probe.txt`。ps 自身瞬时高CPU行属于探针，不是科学 worker。

这是采样时正在耗用CPU而非停在等待的证据，不是完整性能归因。不能从当前block的采样倒推先前block24/25的全部行为。未检查硬件频率、浮点次正规数、具体调用栈或各子程序计时，故不声称这些因素已被排除或已找到根因。

调用链检查：`run_worker_adapter` 复用 `phase7b7j_second_assembled_feedback.run_worker`，调用 formal diagnostics、halo、共动群重映射和 Milne 群微物理；该运行声明 transport/source iteration=False。因此耗时不能直接解释为“多做了很多张 map”或外层物质求解。尚未定位到具体子程序，不改物理实现或冻结运行代码。

Slurm检查时起点15:10:58，时限3:50h，截止19:00:58，USR1提前300s；保持原预算。final_manifest 的当时快照存Mac `outputs/review-20260919/73308-round2-final-manifest-1737.json`（实际获取约17:36，文件名为标签，不当精确时间戳）。文件仍为未完成态，不作为最终反馈。

决定：不取消、不重复提交、不加map；继续监督块进展，完成后按原计划归档对比。若触及声明资源门或时限，先保留半态与失败信息，再按pending反馈恢复规则评估，不能默默提高阈值。cpu_long保持空闲直到有明确独立任务。
