# 77648独立复核与全频验证计划

2026-09-26 SSH重新核实可用，队列空。77648于15:46:29至15:51:55完成，4CPU16GiB，ExitCode=0:0。
小包94318字节，SHA 8c9f461c1417503c3a641dd68a2839541b5b8feac9ae2cdd264f97a257d3af61。
Mac核11清单文件、692代码声明、77577 map10来源，以及2个局部NPZ（各268435992字节）和进程回执。
独立按频率longdouble平方和+fsum重算候选真实缺陷L2/Linf，并核全部数组有限非负。

|块|L2/旧局部L2|Linf/旧局部Linf|计算秒|进程峰值KiB|
|---|---:|---:|---:|---:|
|24|0.1142579757|0.3029073226|216.055|3219656|
|48|0.0979145876|0.4112406497|231.361|3241700|

原算子重放逐位一致是学校代码/报告证据；Mac没有原始输入输出块，未独立重算旧L2或边界通量，未重解算子。
两例16次GMRES迭代、info=2、linear_audit_passed=false；“有限方向有效”不等“线性问题收敛”。
两例line_fraction=1，所以生产预测误差零只重复端点；必须增补真实半步，才能独立检验插值。
完整数值见`handoff/evidence/20260926-heating-block-pilot-review.json`及同名PNG，PNG已目视检查。

## 决策与备份

不重复扫描同一组三历史，不直接继续未改善的八map窗口。登记新全频验证，详见
`handoff/protocols/step21-heating-block-global-v1.md`。全步和半步实际map两次，全部旧composite门通过才
自动继续full到pair02与pair10；上限11map、2反馈。若全步失败，不临时挑半步宣布成功，保留两端点可供下一次有界线段研究。
固定物质20/r20/旧物理层/dt，不进入第21步或整盘。旧物质代码/协议/工件不修改。

Mac备份`outputs/review-20260925/pre-heating-block-result.bundle`、`automation-before-heating-block-result.toml`；
原77648包和两个局部NPZ保存在同一review目录，大文件不入Git。
数值驱动全新文件，历史核不改；监督器增加新模式，只读、无工具，无自动改门或重试。

## 运行前审查

[PRE-RUN CHECK]

Code: PASS — 50项合成/失败路径回归通过；Python编译、sbatch语法和diff空白检查通过。
Logic: PASS — 输入绑定77648声明与77577配对、trial先写后初始化、原有限模板正确构造零控制；真实协议工件构造复核通过。
Physics: WARNING — 局部缺陷收益不保证全频耦合或物质反馈收益，需本批实算；没有改变物理问题。

Key Issues:
1. 原范数固定；全频Linf和边界同时非增；不能靠新候选尺度掩盖增长。
2. 半步只在选中块运算，其余逐位复制，保留次正规弱尾；全部频点参加检查。
3. 全步未过即止于两map；首次反馈未过不再派发八map；最后窗口门失败不能写成功。

Decision: RUN — 先学校同组回归通过，再提交32CPU/128GiB、16worker、4小时有界任务。

Post-Run Check（已有77648）：stderr无异常，候选与真实映射全有限非负，源重放/身份未变；
局部L2与最大缺陷共同下降、单例计算约19.28次局部map成本、RSS低于6GiB；不能推断全域收敛。
新全频任务结果尚未产生，不能预填Post-Run科学结论。
