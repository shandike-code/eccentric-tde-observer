# 85800真实full输出后的有限正式反馈窗口

85800在数值4d1a8314e272063bc79021d152dbc4c8fe6b08fb下完成full/half各一次真实映射，并经独立审阅325工件、152进程回执和原16门全部通过。新种子只用full真实输出，SHA d7ced0397fa1a446e9e1571c575ec1b06fef4867c6a19b49a72c788eef026d83；不是候选q或预测p。full真实缺陷L2比0.5865597261082087不是物质残差或反馈一致性指标。

新目录outputs/hpc/x20-85800-seed-feedback-20261006。固定x20、原物理旧层/base/r20、相位1367、dt889.419892762322秒、原频率/角度/深度网格与率/转移/响应核。trial先写再初始化，所有encoded/base/direction/r20/relaxation逐位核，并核native镜像与物理相位。无clip/floor/nan_to_num、删失败点或修改能量。

只演化historical一支，最多16张新map，第8/16张各一对原正式反馈，共最多2对、0物质更新。比较一：同支16−8的完整512维响应向量差；比较二：新支对加速前84026 historical pair16；比较三：新支对保存82518 accelerated pair16的四组合响应与率/加热。84026取原previous→final迭代15为锚点；不再用82989当直接加速前来源。保存A未重算，不是新等长双支实验。

84026数值工件已审但Slurm终态缺失：新入口直接核其已审归档SHA/清单/实时小工件/源码，不借新作业成功补造原调度COMPLETED。source_84026_scheduler_terminal_verified=false保持。当前85800则必须有真实COMPLETED证据和完整16门独立审计。

32CPU128GiB、16worker、4h硬限、USR1提前900秒。父/单worker<6GiB，空闲磁盘至少14个完整场。原内层门、零步七门、物理域、资源、来源失败立即停止归档；单纯新窗口或对保存参考差异未过，只完成已声明第二窗口，不扩预算，不自动续交。学校可写dat，不下载或Git提交。

沿用r20三范数及冻结80195四P−C向量各范数最小信号，门0.001与0.1不换分母。先完整向量相减再取范数；质量范数和Max-cell定义不变。率/加热保留四组合最差值，不选好看的一个端点。

reference_calibration_eligible=false、reference_recomputed=false、matched_new_two_branch_experiment=false、accepted20及0新物质步保持。即使单窗口通过仍须独立审阅，不能直接接受21或宣告自洽大气/整盘I_nu。

自动归档pair08/pair16与complete/failed/interrupted排除dat。shell在Python退出后另外写batch-exit；watch先保存真实scheduler-terminal后调用无工具CLI。无真实调度终态时保留unknown，只凭child成功不算COMPLETED。备份、数值提交、实际job与资源回执随阶段保存。

## PRE-RUN

Code：新代码只改源身份、归档校验和运行封装；继承原16map/两次反馈/物理失败立即停止，测试覆盖错job/数值提交、缺门/失败门、错真实输出、源终态缺失与伪造、配置/trial和完整向量比较。Logic：85800真实T(q)作为新辐射初值，重新映射后在8/16测正式反馈；84026前态与82518保存参考分开。Physics：固定物质背景的内层稳定性实验，不推进物理时间，不改能量或物质接受标准。Decision：两端测试、源审核与备份通过后运行上述有界窗口。
