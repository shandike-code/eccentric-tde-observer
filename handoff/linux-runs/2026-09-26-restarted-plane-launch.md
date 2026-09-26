# SSH恢复后启动有界只读扫描77473

重连后确认学校仍在facc518，工作树干净、队列为空、新run不存在；此前未成功同步或提交。
增量bundle核验后快进到2a76fa36222a8f29c6b3c6e9b84076e0b73014cc。
学校38项测试通过（20.51秒），batch语法通过，才提交新任务，未改数值代码或原门。

77473于2026-09-26 10:23:30启动，anode02、qos_stu_default、4CPU/16GiB，
硬上限11:23:30，USR1提前120秒。run仍采用已声明目录
`outputs/hpc/step21-restarted-plane-scan-20260925`，日期后缀是协议命名，实际提交时间以调度记录为准。
启动快照`handoff/evidence/20260926-restarted-plane-77473-start.json`。

10:24:06快照RUNNING/preparing，stderr为空；大型来源SHA校验在allocation内进行。
尚无新预测或科学结果，不把启动成功当算法有效。接受步保持20，0map/0反馈/0大型候选。
按既定两组各6遍、一小时预算执行；只有合格预测且收益超过20%，再独立审计并考虑32核真实验证。

只读tmux `step21-restarted-scan-77473`，输出
`outputs/review-20260925/restarted-plane-watch-77473`及同名`.log`，预算5400秒。
启动回执is_error=false、实际模型deepseek-v4-flash[1m]，仅作状态摘要。
其“退避正常”没有证据；“候选未写出所以无工件”也不是本任务判据——本任务始终不写大候选，但会产出可审计的小型预测文件。
后续直接检查原始status/prediction/归档/调度，不采纳这些补充解释。

学校备份`/home/scc/pb24511938/pre-restarted-scan-reconnect.bundle`，
Mac保留`outputs/review-20260925/restarted-plane-reconnect.bundle`及
`automation-before-reconnect-launch.toml`，旧备份与77371工件原样保留。
恢复原有30分钟定时任务，仅实质结果、故障或需重连时通知。活跃扫描期间冻结数值依赖与声明测试/协议。
