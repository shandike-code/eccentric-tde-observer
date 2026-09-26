# 77577：32核真实热投影验证已启动

2026-09-26 13:13:25提交并RUNNING，anode02，Students/qos_stu_cpu_long，实际32CPU、申请128GiB，
4小时硬上限（17:13:25），16worker。运行目录`outputs/hpc/step21-heating-validation-20260926`。
数值提交`e197b8f5963c2aa15aadcb2ced174f1475fea18f`，Mac/学校/GitHub同步。
Mac47测试0.97s，Linux同组47测试20.61s通过；shell语法通过。

首张真实场通过才map2/pair02；原七门、物理域、实际热代理比<0.8及六项预测精度门<0.001
全部通过才map3..10/pair10。合计最多10map、2pair、一个辐射候选，零新物质接受。
细节以`handoff/protocols/step21-heating-validation-v1.md`为准，不更换原r20。

启动检查：status=preparing，stderr为空。完整来源/大态SHA在allocation内核验，
所以准备阶段不代表算map或卡死。目前不报告实际加热收益或完整耦合解。
当前数值依赖冻结；后续Git元数据提交只增加handoff审计/说明，不改变运行代码。

平台监督tmux `step21-heating-validation-77577`，输出
`outputs/review-20260925/heating-validation-watch-77577`及同前缀.log；
使用`watch_readonly_scan.py --mode heating-validation --seconds 18000`。
只读CLI无工具，不提交/取消/修改科学门。CLI模型以自身modelUsage为准，不把命令名当独立科学验证。
30分钟Codex heartbeat `USTC HHe 运行审阅与决策`已更新到77577，SSH断线时只提醒重连，
不把掉线当Slurm停止。没有额外启动无独立科学目的的4核map任务。

下一次重点检查`control/validation.json`与`control/pair02/heating_validation.json`。
终态传完整原包/receipt和调度状态，独立重算热代理、逐端点精度、8map四组合三范数。
旧审计脚本硬编码11map/[3,11]，需新审计入口，不允许直接套用旧结论。
本批完成不等第21步被接受；最终整盘I_nu仍取决于代表柱、全定义域和观察者接入的后续验证。
