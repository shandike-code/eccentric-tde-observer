# 14:40 SSH中断，暂停巡检等待重连

2026-09-28 14:40巡检先连接原学校账号，`BatchMode=yes`返回255：`Permission denied (publickey)`。随后`ssh -S /Users/shandike/.ssh/tde-control/ustc.sock -O check pb24511938@107.ustc.edu.cn`返回255，确认control socket不存在。连接记录见`handoff/evidence/20260928-ssh-interruption-1440.json`。

远端检查命令没有执行，因此78950当前是否仍运行、control16及两个方向16map反馈是否完成均未知。最后实际核验是14:06:16：RUNNING 2:35:00，control16正式反馈尚无decision、父stderr空。SSH断连不是Slurm失败证据，没有取消或重交任何作业，没有新增数值判决。

定时任务`ustc-hhe`已通过应用工具更新为PAUSED，并回读确认；原30分钟节奏和线程绑定保留。更新前配置备份`outputs/review-20260925/automation-before-ssh-pause-20260928-1440.toml`，Git备份`outputs/review-20260925/pre-ssh-pause-20260928-1440.bundle`。仅提醒用户一次在Terminal运行`~/.ssh/tde-control/connect-ustc.command`、在Terminal输入密码及动态码、保留窗口并回复已连接，不在聊天收集凭据。

重连后先检查原78950的squeue/scontrol、run/status、监督器保存的scheduler-terminal、最新归档与父stderr。若已完成，优先下载最新完整小工件包并审计；若仍运行，继续原48map/6对反馈的声明预算。不得因失联重新提交、覆盖旧r20、接受第21次物质更新或放宽门。

学校最后已核对的Git HEAD为70401eeab8d333b8280fb5bdce060f972db691f4。本次断连记录只能先在Mac提交并推GitHub，学校同步待连接恢复；恢复时检查实际HEAD及工作树，备份后快进，勿假定三端已同步。本次没有改正在运行的数值源码。之后再恢复定时任务ACTIVE。
