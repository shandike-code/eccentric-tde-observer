# 79631：布居候选的全域验证已启动

2026-09-28 20:10:49提交，20:10:50开始运行；Slurm 79631，anode16，32CPU、128GiB、`qos_stu_cpu_long`。16个单线程worker，6小时硬限至2026-09-29 02:10:50，提前900秒USR1；截止时间不是科学完成时间估计。

冻结数值提交为`7f56c529e93aa7929c9e27f45cb7a10e6d29ee8e`，已推GitHub并同步学校。目录`outputs/hpc/step21-late-population-global-20260928`。入口及完整预声明门见`operations/validate_late_population_global.py/.sbatch`和`handoff/protocols/step21-late-population-global-v1.md`。

## 实测启动状态

20:14:11仍RUNNING，程序已完成prepare并写出declaration，进入writing_candidates；population子目录已开始初始化，0张完成map、无active map，stderr 0字节。此时没有全域门或反馈结果，不能提前宣布通过。声明阶段已核实际source pair、完整源/源码SHA及候选物质身份；后续初始化和计算仍按冻结门检验。

本轮先做同一population物质的full/half各一张真实全频map，核全部9632频率的L2收益、Linf、独立半步、正性及边界门。只有全部通过，才执行control2、population2、control10、population10的反馈窗口。最多21张map、4对反馈。任一规定派发门失败停止后续，不自动加预算、重交或提升物质接受。

control来自自己的末态，population经过局部辐射修正，两组并非相同初始辐射历史。第2张相对79151的变化只作为修正跳变；第10相对2张才是一个八map持续性窗口。原16门、历史失败和r20保持，物质接受20不变。

## 验证、备份与监督

Mac针对性测试87 passed/1.11秒；学校85 passed、2 skipped/14.86秒，两项跳过是Mac接收目录不存在。学校实际小源端点及79563审核元数据另行预检通过；编译/bash语法通过。完整大态哈希与native物质核验放在allocation内，未在登录节点运行辐射计算。

两端提交前均保存`outputs/review-20260925/pre-population-global-20260928.bundle`。Mac自动化备份`outputs/review-20260925/automation-before-population-global-20260928.toml`。源码增量bundle为`to-school-population-global-20260928.bundle`，按clean检查及ff-only同步，未改旧数值字节。

学校tmux会话`population-global-79631`，脚本`handoff/audit_tools/watch_late_population_global.py`，输出`outputs/review-20260925/population-global-watch-79631`。每60秒只读状态，7小时监督上限；RUNNING、全域验证、反馈窗口及终态等新节点调用无工具CLI，先保存Slurm终态再调用模型。实测监督活跃，首份回执实际模型`deepseek-v4-flash[1m]`，无工具授权；其概括不能代替Codex独立科学审查。

自动化`USTC HHe 运行审阅与决策`已切换到79631，保持ACTIVE、30分钟。正常进展静默，只通知完成、实质失败、重要决策或需要用户重连；SSH断开不取消学校作业，不以连不上判断计算失败。

## 下次接手

先读`handoff/evidence/20260928-late-population-global-79631-launch.json`、本协议及学校watch最新状态。准备/初始化阶段可主要耗时于大态SHA核验；用状态、I/O及日志证据区分正常工作和挂起。

全域验证完成即可接收`full-half-validation`小归档审计，不必等全部窗口。结束时收完整小归档及receipt，保全terminal/stderr/过程回执；不下载dat或local大NPZ。审计不得机械复用旧control/24,48的假设：本轮是population/37,44，选择34–47，最多21map4对。独立归约完整slab统计、核原门、逐位trial、两态来源与完整S=P-C及16种跨窗口组合。全域收益或持续性失败都要定位后再决策，不能无界续Picard。

当前没有第21次接受、自洽柱或整盘I_nu完成证据。下一步由本轮实测决定。
