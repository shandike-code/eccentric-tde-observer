# 77648两块局部校正已启动

2026-09-26 15:46:29，77648 RUNNING，Students/qos_stu_default/anode26，4CPU、16GiB、2worker，
2小时硬限至17:46:29（不是ETA）。run `outputs/hpc/step21-heating-block-pilot-20260926`。
数值源`81a897f8e42113c14420e2f9e5bbc67477cb04ed`，Mac/学校/GitHub一致。
本地28项测试最后一次0.91s、Linux同组28项18.97s通过，shell与Python语法通过。

源77577已完整审计，旧物质/原r20保持；本批只读源态，在24/48块各做有限Krylov及原算子重放/候选检验，
保留局部NPZ，零全频map、零正式反馈、零全局候选、零物质接受。
完整预检与物理边界见`2026-09-26-heating-validation-complete-and-local-pilot.md`及
`handoff/protocols/step21-heating-block-pilot-v1.md`。

启动时preparing、stderr为空，完整大SHA在allocation内执行。当前数值依赖冻结；
本启动报告仅增加handoff元数据，不改变运行代码/协议。
监督tmux `step21-heating-blocks-77648`，日志/快照`outputs/review-20260925/heating-blocks-watch-77648`及同前缀.log。
只读CLI无工具；heartbeat已更新到77648。无额外全频盲续任务。

下次审阅：两个worker的JSON及process receipt、局部NPZ SHA、原图重放、正性步/有限GMRES状态、
真实L2/Linf/边界收益、时间和RSS。原包会排除>32MiB的局部数组，必要时另外传NPZ，不伪称已核其全部值。
局部通过不等全频通过；需先检验邻块耦合才能另登记全局候选或32核批次。异常保留并诊断，不自动重试。
