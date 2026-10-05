# 85861真实输出后的有限正式反馈窗口

85861完整独立审阅325工件、799源码、34直接小来源、152worker回执及301片80位归并，原16门全过；真实Slurm于2026-10-06 05:51:18 COMPLETED0:0。数值68452895c7953a4540d285a02e200b61f5b0cf3d。新种子唯一为full真实输出state_1.dat，SHA 64992a047808bc99eed6463d11fba4cff655970b426f1141ee2efbdf164135de；不是候选q或仿射预测p。真实缺陷L2比0.43799316541626593不能直接解释为物质反馈稳定。

新目录outputs/hpc/x20-85861-seed-feedback-20261006。固定原x20/trial、物理旧层/base/r20、相位1367、物理dt889.419892762322秒、9632×32×4096网格及原转移/率/响应核。trial先写后init，再逐位核encoded/base/direction/r20/relaxation及native镜像；不clip/floor/nan_to_num、不删失败单元、不调整能量。

只演化historical一支，最多16张新map，第8和16张后各一对原正式反馈，共2对、0物质更新。分别比较新16−8完整512向量四组合、新支对加速前85821 historical pair16，以及新支对保存82518 accelerated pair16的四组合响应及率/加热。85821源锚点previous→final为iteration15，不是map16输出；本次种子则确实为85861 full新输出。保存A没有重算，reference_recomputed=false、matched_new_two_branch_experiment=false、reference_calibration_eligible=false。

85861必须真实COMPLETED、childexit0、16门及全来源/字段/资源独立审计通过。85821必须核完整1216map/304feedback审计和原真实终态，以及原归档清单与学校实时小文件字节；更早84026 scheduler仍false/null，不能借后续成功补造终态。

预算为32CPU128GiB、16worker、4h硬限、USR1提前900秒；父与每worker<6GiB，free>=14完整场。依据85821同类完整窗口实际1h50m08s、85861含来源核验的两映射整体1h10m17s，4h只是有限硬限，不保证耗时，也不从166/195秒单map推算整个作业。新种子inode/size/mtime、全部来源/代码SHA和clean/exactHEAD前后核验。

原七门、物理域、内层、资源、来源或完整性失败停止并归档；单纯新16−8窗口或跨保存参考漂移失败只完成既定第二窗口，不自动扩预算、恢复或追加。沿用原r20三范数和冻结80195四P−C向量各范数最小信号，门0.001/0.1不变。完整向量相减后取L2、质量、Max-cell范数；率按原逐点max分母积分，四组合都保留。accepted20固定，任何有限窗口均不自动接受21、校准或宣告耦合柱/整盘I_nu完成。

自动归档pair08/pair16及complete/failed/interrupted不含dat；学校可写新dat，不下载或Git提交。shell在Python结束后写batch-exit，须另外取；watch先保存原scheduler-terminal再调用无工具只读CLI。仅child退出时保留调度未知，不能伪造COMPLETED。

## PRE-RUN

Code：继承已审16map/两对反馈核，仅新增本轮源绑定及种子/checkout前后完整性。测试需覆盖真实种子、错job/commit、缺门/失败门、来源终态/回执缺失与84026伪造、固定trial/operator和完整四组合。

Logic：先完成85861原16门独立审阅，再用真实T(q)作新辐射初值；8/16两次反馈用于新窗口、原85821端点和保存A三个不同问题，不能互换。

Physics：同一物理时间步内固定x20的辐射历史与正式响应稳定性检验；新小QP加热指标不替代正式加热，原85821窗口及保存参考加热失败保留。

Decision：两端测试、实际小来源/trial/native预检、备份与代码同步通过后，仅运行本协议有限窗口；物质更新和额外预算DO NOT RUN。
