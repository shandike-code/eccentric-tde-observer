# 78513资源参数错误与隔离修复

78513于20:10:02提交，在anode21运行25秒后FAILED/1:0。未创建run目录、未读取大场、无扫描或物理产物；原日志和watch scheduler-terminal已保留在handoff/evidence，启动回执20260927-seven-refresh-line-launch.json。数值提交4a6578a。

错误是Codex把原扫描的pipeline.require_allocation(1)误改为(4)，以为参数是CPU数；实际参数是worker数。该函数要求6GiB/worker+2GiB父进程，所以错误地要求26GiB，而扫描是单进程、配置为4CPU16GiB。原16项测试未覆盖资源接口，不能将测试全过当完整集成验证。Slurm给出了正确的4CPU16GiB，这不是平台资源不足或科学门失败。

隔离修复：新增scan_step21_seven_refresh_line_v2.py/.sbatch与协议v2，原失败版原样保留。调用workers=1，另要求实际CPU>=4、内存>=16384MiB；父峰值6GiB和原1h上限不改。新run outputs/hpc/step21-seven-refresh-line-v2-20260927。wrapper退出前快照改存既有logs目录，避免未建run时再出现第二条路径不存在错误。

新增测试以原4CPU/16GiB环境复现旧函数误用失败，再验证新guard通过；不足CPU/内存/无allocation/无内存字段均拒绝。Mac21passed/0.93s，compile/bash-n通过。修复未触及物理源、步长规则、成本门或输出统计；Linux复测通过后只提交一次新作业，不盲重试原78513。

备份Mac pre-seven-refresh-line-resource-fix.bundle；学校同步前同名备份。尚未提交的未来短步驱动只作准备，只有新扫描实际通过并经Mac独立复核，才有资格投入真实map。20次物质更新接受、第21未接受。
