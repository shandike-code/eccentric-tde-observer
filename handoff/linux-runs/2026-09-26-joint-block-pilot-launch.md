# 三块联合局部试验已提交

2026-09-26 20:34:11，Slurm job77817，run outputs/hpc/step21-joint-block-pilot-20260926，32CPU128GiB/Students/qos_stu_cpu_long，2小时硬限，2worker。实际状态以启动观测与学校watcher为准。

源码提交473ae83ef595df0d2f59d823b4e6093e6b8da79a；提交作业时HEAD为d76c7b2（增加只读watcher说明，数值代码未再改）。Mac19 tests0.88s/Linux19 tests17.59s通过，编译和sbatch语法通过。代码/逻辑/物理前检在对话中完成；真实分辨率replay与局部方向仍待计算，没有预先宣布通过。

协议step21-joint-block-pilot-v1.md固定预算和门槛，原77577输入、三块核心、16次Krylov、独立半步检验，0全频map/0反馈/0新物质接受。每worker30分钟、16GiB门。既有大场与历史源码未改。

只读监督tmux step21-joint-blocks-77817，outputs/review-20260925/joint-block-watch-77817，watcher mode joint-block-pilot，最多10800秒。CLI无工具且不提交或取消作业。Mac每30分钟审阅已改为检查该任务；77817异常不盲重试。

备份Mac pre-short-completion-and-joint-pilot.bundle及automation-before-joint-block-pilot.toml，school /home/scc/pb24511938/pre-joint-block-pilot.bundle。后续需取完成/失败小包与SHA、terminal、replay、进程回执和局部数组，独立审计后才决定全频检验。
