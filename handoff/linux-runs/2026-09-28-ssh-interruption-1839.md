# 2026-09-28约18:39 SSH断连，暂停本地跟进

本轮只读连接返回255/Permission denied (publickey)，随后`ssh -O check`返回255，明确报告`/Users/shandike/.ssh/tde-control/ustc.sock`不存在。证据`handoff/evidence/20260928-ssh-interruption-1839.json`，记录时间18:39:54。与此前Master仍存活的单次暂错不同，本次需要用户重建交互认证连接。

无法确认79151当前是否已完成population反馈或按晚期门停止。最后实测为18:01:20 RUNNING/anode18、control和thermal各8完整map、population initializing/0完整map。thermal首个晚期窗口已审计通过，原三个收缩门仍失败；此前control历史累计质量门失败也保持不变。没有新接受或完整批次终态的新增证据。

本轮未发送取消、重交或修改远端文件命令。SSH断连本身不能证明Slurm作业已停止或失败，学校只读监督是否仍存活也需重连后核实。

暂停本地自动化`ustc-hhe`，保留30分钟周期及原科研协议，避免无连接空查。只需用户在Terminal运行既有`~/.ssh/tde-control/connect-ustc.command`，在那里输入学校密码和动态码，保留窗口并回复“已连接”；不得在聊天索取密码。

重连后先查原79151的squeue/scontrol、run/status、各child、pair08/16判决、stderr及watch/scheduler-terminal.json。优先取最新population08或complete包，已审control08/thermal08不重下。不重交原作业，不扩大预算，待核实原状态再恢复ACTIVE。

本地备份`outputs/review-20260925/pre-disconnect-20260928-1839.bundle`及`automation-before-disconnect-20260928-1839.toml`。断连记录先提交Mac/GitHub，学校当前记录仍为8ad8fd1；恢复后按clean检查、备份、增量bundle、ff-only同步本次记录，不能覆盖运行中的数值源码或旧工件。
