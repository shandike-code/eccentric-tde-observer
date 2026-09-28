# 79747：按实际辐射缺陷选块的局部探针已启动

2026-09-28 21:06:30提交，21:06:31开始，Slurm79747/anode19，32CPU128GiB、qos_stu_cpu_long，2小时硬限至23:06:31。21:07:22实测RUNNING/preparing，stderr0，尚无局部结果。冻结数值提交`c5626fe6c5dd7eab2b25e1d03410350f9b573d11`，已同步Mac/GitHub/学校。

run为`outputs/hpc/step21-population-defect-pilot-20260928`；入口`operations/pilot_population_defect_blocks.py/.sbatch`，协议`handoff/protocols/population-defect-pilot-v1.md`。从79631实际full输入及后继态出发，固定同一population物质，选择20–26与27–33两个七块核心。预算、原局部门、物理旧层、r20、dt均保持；0全域map、0正式反馈、0新物质接受。79631原L2与bolometric拒绝不改写。

Mac39项测试通过（1.06秒）；学校30 passed、9 skipped（14.91秒），跳过均因Mac接收目录不在学校，学校真实源端点和评分选择预检另通过。编译与bash语法通过，完整大态哈希及native消费在allocation内核验。

只读监督tmux `population-defect-79747`，脚本`handoff/audit_tools/watch_population_defect_pilot.py`，输出`outputs/review-20260925/population-defect-watch-79747`，3小时监督上限。每60秒读状态，仅关键节点调用无工具学校CLI；终态先落盘，再等待模型。模型解释由Codex审查，不授权其改文件、提交、取消或读取凭据。

自动化`USTC HHe 运行审阅与决策`已切换79747，30分钟ACTIVE；健康进展静默，完成/实质失败/重要决策/需重连时通知。两端预备份`pre-population-defect-pilot-20260928.bundle`，Mac自动化备份`automation-before-defect-pilot-20260928.toml`，位于`outputs/review-20260925`。

结果出来先取小归档，独立核验79631源、23/30中心、平方评分、真实重放、两例原局部门及资源；通过才新声明4核原数组扫描，之后才另声明完整全域实际验证。后续必须同时对照79631数值起点及原79151参考，不能用换参照把旧失败变成通过。不会恢复79631原本未执行的反馈预算，也不保证这一局部方法一定有效。
