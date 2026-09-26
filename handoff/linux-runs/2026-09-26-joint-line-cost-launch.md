# 联合方向只读步长成本筛选已提交

2026-09-26 22:34:01 Slurm77905，默认Students/qos_stu_default，4CPU16GiB，一小时硬限。run outputs/hpc/step21-joint-line-cost-20260926，数值commit600c30359a852185bdd8791933d9b6915a662f58。初回执PENDING，实际启动观测另存evidence。Mac31测试0.91s/Linux31测试17.28s通过；编译、sbatch语法通过。前检已完成。

读取77843四个完整端点，最多三遍；固定原最大缺陷约束、0.9步长裕量、至少20%预测L2改善成本门。0新map/反馈/候选/物质接受，不减物理dt，不改r20。协议step21-joint-line-cost-scan-v1.md。若预测门未过，不启动该方向昂贵真实map；通过仍需独立审计和新实际算子验证。

监督tmux step21-joint-line-77905，outputs/review-20260925/joint-line-watch-77905，mode joint-line-scan，最长7200秒。CLI无工具仅摘要。30分钟定时审阅转向此任务，32核目前不重复提交。

备份Mac pre-joint-line-cost-scan.bundle与automation-before-joint-line-cost-scan.toml；school /home/scc/pb24511938/pre-joint-line-cost-scan.bundle。运行冻结声明源码和tests/protocols。77843错误日志已核实0字节。

近期用户授权Mac清理16份旧大场共150.5GiB，保留7个关键完整检查点与全部review审计数据；清理记录480c396/2781a6f/b37a365已同步。不自动恢复已删除历史场，学校数据不受影响。
