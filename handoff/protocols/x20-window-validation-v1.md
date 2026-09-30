# 82187已审唯一候选：32核真实full/half映射v1

前置：82187全场预测独立审计通过，绑定原八场/系数/完整301片11门。此处不再次选系数、不再优化。新锚点是A16与T(A16)，索引0/1；不能使用旧expanded的索引1/2。

来源直接从81769 accelerated/H16的config/state/trial/endpoint16/protocol及原归档逐字节绑定。验证trial encoded_state、base_encoded_state、finite_direction、base_residual、relaxation和native解码；对outer_base、冻结r20、physical_old、phase1367及dt889.419892762322逐项同一。先复制既有trial，再初始化子run；不得让migrate_trial代入另一候选。新run只改变辐射初值，16worker与原物理算子、频率归属、全部76块不变。

资源：Students/qos_stu_cpu_long，32CPU128GiB2小时，父RSS<6GiB，每worker<6GiB，16worker。新目录outputs/hpc/x20-window-validation-20260930拒绝覆盖。唯一raw/full/half系数继承已审result；只在学校生成full.dat/half.dat及原映射输出，绝不下载Mac。最多2张map、0反馈对、0物质步，不提升r20、不接受21。至少10份完整态的可用磁盘空间前置。

原门全部保留：full真实L2比≤0.8，full/half Linf不增、half L2不增；原radiation<1e−4，boundary L1/bol<0.001且相对A16真实原map不增。半步真实缺陷与端点平均的L2和Linf差/原缺陷≤1e−6。

另直接完整扫描八源场与两个真实输出，重建同系数预测p_full与p_half，要求真实输出减预测的L2和Linf/原A16缺陷均≤1e−6，保留所有301分片。这是额外验证，不是放松原门。高频黑尾保留，不删除自相对变化大的块。

前后SHA、源配置及声明代码核验；full/half输入SHA必须等于已写候选，实际worker回执各76、全部正常/内存守卫过。失败或信号保留状态与小归档，不自动重交或更改系数。完成后独立审计、图及讲义，再决定反馈/窗口任务，不能把两张真实map称为耦合自洽或整盘I_nu完成。
