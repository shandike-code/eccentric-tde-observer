# 79878：双参考全域检验已启动

2026-09-28 22:04:46提交，22:04:47开始，Slurm79878/anode19，qos_stu_cpu_long，32CPU128GiB，16单线程worker；硬限6小时至次日04:04:47，不是ETA。22:05:22实测RUNNING35秒/preparing，父stderr为空。输入SHA/native核验尚在运行，不能把启动当作全域通过。

冻结数值提交e31d88b354a34cb5ce1dc51ba4437f997668fd15，Mac、GitHub、学校一致。Mac57passed1.12秒；Linux55passed2skipped14.12秒，两个跳过是Mac接收目录缺失；学校另对真实源source_pair和require_array_review实核通过。编译、bash语法、diff检查通过。

run：outputs/hpc/step21-population-defect-global-20260928。入口operations/validate_population_defect_global.py/.sbatch；协议handoff/protocols/population-defect-global-v1.md。先对20–33局部修正拼出的full/half各做真实全域映射，同时核对当前79631 q和原79151 x的21门。half只属于当前q→full线段，不能用原x构造仿射门。任一失败即停止，保全旧拒绝；全部通过才按control2/population2/control10/population10执行，最多21map、4反馈对，不自动接受第21物质步。

学校只读监督tmux population-defect-global-79878，脚本handoff/audit_tools/watch_population_defect_global.py，输出outputs/review-20260925/population-defect-global-watch-79878。7小时监督上限，每60秒读状态，仅关键新阶段调用无工具CLI；调度器终态先落盘。当前CLI实际模型为deepseek-v4-flash[1m]；其解释必须由Codex核查，不允许改文件、调度或读凭据。

自动化“USTC HHe 运行审阅与决策”已更新到79878，30分钟ACTIVE。健康进展静默，实质变化、完成、失败或需SSH重连时通知。SSH断开不影响Slurm任务，不重复提交。

两端备份outputs/review-20260925/pre-population-defect-global-20260928.bundle及pre-population-defect-review-20260928.bundle。Mac另备份automation-before-defect-global-20260928.toml。79850原数组审计、79747局部报告和讲义第70节已入Git；大dat/localNPZ留学校。新启动证据见handoff/evidence/20260928-population-defect-global-79878-launch.json。

下一审计必须适配双参考schema，而非直接跑旧79631审计脚本：current四列raw/full/half/affinity，original三列raw/full/half，各核完整9632频率，原参考不添假半步门。若进入反馈，再核control累计窗口、完整512维S=P−C持续性及原16物质门。没有新正式反馈时不得宣称加热响应或物质收缩改善。
