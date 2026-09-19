# 单块剖析结果与大页请求对照

## 73385 已完成且数值复现

同一冻结协议与final block24，`outputs/hpc/profile-round2-final-block24-20260919`，1worker、cpu_long2CPU/8GiB、anode16。剖析worker墙钟1294.14s，原worker内部计时1030.90s；二者计时范围不同（原计时不含_context），且剖析有开销，不把比值当速度退化或加速比。

输入哈希前后校验通过，重放与原块10个数值字段逐字节一致且全部有限。未修改原run，未重跑map，无科学接受。

累计函数耗时：`_context`679.04s，其中`_load_material`521.51s；NumPy `read_array`23次累计493.12s；`ground_state_milne_multigroup`三次累计300.73s；`assembled_block_diagnostics`245.78s。这些调用相互嵌套，不能相加当总耗时。原始累计和自身耗时表见`handoff/evidence/73385-feedback-profile.txt`。耗时跨输入读取、数组构建和数值运算，不能仅以“物理迭代慢”解释。

完整小包双端保存为`feedback-profile-73385-small.tar.gz`，300183 bytes，SHA256 `c0fe55b65931937f202f4c198b8a9cf73e76376e5a834dae25a50f9a5e904a64`。Mac目录`outputs/review-20260919/`，解包`feedback-profile-73385-received/`；10文件逐一大小/SHA通过，含declaration/protocol/profile/块报告和数组比较。stderr为空。

## 节点检查与尚未证实的原因

18:45探针：节点约1TiB内存、available约796GiB，两个NUMA节点均有大量空闲内存。73308 cgroup约4.3GB内存、memory.max/high=max、无OOM/high/max事件、无CPU配额节流；当时其memory.pressure full avg10约99%，但这是采样窗口统计，不等于已识别原因。节点swap已满，但采样vmstat无持续swap-in/out；不能以swap满直接宣称本任务在换页。

THP enabled和defrag均为madvise；节点自开机累计compact_stall约9384万，allocstall_movable约4402万。这是节点历史总计，不能当成本作业增量或因果证明。结合数组分配普遍慢和内存压力，透明大页/内存整理值得做进程级对照；不改节点设置、不调整物理。后续采样保存在`handoff/evidence/73308-memory-pressure-probe.txt`。

NumPy官方文档支持在导入前用`NUMPY_MADVISE_HUGEPAGE=0`关闭其大页请求：[Global configuration](https://numpy.org/doc/stable/reference/global_state.html)。也核对了学校实际安装的NumPy `__init__.py`确实读取该环境变量。

## 独立对照 73395

同一个已冻结剖析脚本、同一block24/协议/输入，独立目录`outputs/hpc/profile-round2-block24-nohuge-20260919`。固定anode16，cpu_long2CPU/8GiB，30分钟，USR1提前120s。唯一声明的执行设置变化为`NUMPY_MADVISE_HUGEPAGE=0`；提交命令含显式export，已保存`handoff/evidence/73395-nohuge-submission.txt`。运行时段、CPU分配与缓存状态仍可能不同，不是完全消除干扰的随机对照。

预检保留原协议、继承源和前后SHA校验；输出不并入正式反馈。现已complete：同一剖析计时范围22.8339s，对照73385为1294.1374s，观测墙钟比约56.7。10个数值字段仍全部逐字节一致。它支持进程大页请求与本节点严重性能退化相关，但单次不同时段对照不证明所有节点、所有频块都得到同样加速，也没有独立观测内核调用栈来证明具体整理机制。

73395小包`feedback-profile-73395-small.tar.gz`已双端备份，300119 bytes，SHA256 `f27d420348855769b42cc20e0ee8c1e26abd5a610a1facc62d3d9859039a1a7d`，Mac逐项核10文件和比较结果通过。新profile中个别字体调用累计时间超过总墙钟，故不将所有函数累计排名视为可直接相加的精确时间账本；主要比较独立外层墙钟、原worker计时、输入与结果身份，进一步定位仍需谨慎。

## 有界完整反馈重放 73396

代码`a5e3c78`，`operations/replay_pair_nohuge.py/.sbatch`；Mac/Linux各5项测试通过（含协议变换只能改变声明字段）。run `outputs/hpc/paired-base-round2-nohuge-replay-20260919`，cpu_long32CPU/128GiB、16worker、30分钟、无自动续交。只重算第二轮previous/final两份反馈，0张新map；显式`NUMPY_MADVISE_HUGEPAGE=0`。变更前代码备份`pre-pair-replay-3c2a5f0.bundle`。

新协议仅改输出路径及并发2→16；全部科学sources、正式科学与资源门保持逐项原值，前后再次验证原源哈希。两态全部重新计算，不复用旧partial，不清零旧记录，不伪造旧运行成功。旧73308照原时限退出，其资源消耗和半态仍原样保留。新pair.run_pair将给出正式物质步判决，若不通过则如实保留；完整反馈完成后还需要双端归档、两历史向量/能量比较，不能把性能修复当作大气解完成。

## 原作业的边界

18:44时73308仍在第二轮final48/76块，累计5849.82s，四张map已完成。原截止19:00:58与7200s正式状态资源门保持不变。即便随后超过资源门，其已计算块也只作为留存诊断，不能将资源门改为通过。若被时限停止，先完整保全现场，再按pending反馈机制或独立新协议恢复；不盲目重跑新run准备阶段。
