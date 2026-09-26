# 单个热投影候选已起跑：77531

本地36测试通过（最终1.74秒），Linux同36测试通过（20.46秒），batch语法通过。
包括实际P0多普勒重映射及微物理加热负权仿射验证、代理拒绝路径和既有六态流式/血缘测试。
四个真实端点的热发射数组逐位相同，原固定物质假设未改变。

数值代码提交f03bff8a7c0da3206633774be839213aed475e62已三端同步后提交。
77531于2026-09-26 11:50:01启动，anode02/qos_stu_default、4CPU/16GiB，一小时硬上限12:50:01。
run `outputs/hpc/step21-heating-projection-20260926`，一候选一遍全场；0map/0反馈/0大态写入/0接受。
11:50:49快照RUNNING/preparing，stderr为空；仍在allocation内核来源，无新科学判决。
证据`handoff/evidence/20260926-heating-projection-77531-start.json`。

只读tmux `step21-heating-projection-77531`，`--mode heating-projection --seconds 5400`，
输出`outputs/review-20260925/heating-projection-watch-77531`与同名`.log`。
已核存活及首次回执is_error=false，模型实际deepseek-v4-flash[1m]，仅用于状态摘要。

新增独立审计入口`handoff/audit_tools/review_step21_heating_projection.py`：按源归档核四态真实后继，
由原字节账本重算质量加权代理（math.fsum归约），核602片全场/边界/负点记录与所有守卫。
该入口尚无新任务完整工件，未声称端到端通过；若运行失败，另审失败证据，不降低断言。
参数为archive、receipt、source（77371完整received）、physical-old、received新目录、output新前缀。
源77371完整tar应与新包同在`outputs/review-20260925/`以匹配来源定位。
不下载大dat，不声称Mac逐点重算；无实际T(q)/候选Q或物质ODE计算。

若所有筛选通过，另登记32CPU真实映射及反馈窗口；若任一失败，不回溯alpha或变更成本门。
当前冻结数值代码/声明测试/协议，只增handoff审计和记录。备份Mac `pre-heating-projection.bundle`、
`automation-before-heating-projection.toml`，学校`/home/scc/pb24511938/pre-heating-projection.bundle`。
