# 联合核心的全频验证已提交

2026-09-26 21:15:34，Slurm 77843；32CPU128GiB、16worker、Students/qos_stu_cpu_long，4小时硬限。run outputs/hpc/step21-joint-block-global-20260926；数值提交fd796a104a0c9d7e3562efd787bcb57800351171，三方已同步。启动观测另存evidence，初回执PENDING不冒充RUNNING。

Mac36测试1.11s/Linux36测试14.06s，编译及sbatch语法通过。预运行检查通过，物理局限为外侧块响应尚未知。本批固定77577输入、77817两组三块候选、原x20/r20/dt，先full/half真实map全域检查，失败停；全部通过才条件继续map2/pair02、maps3..10/pair10，最多11map两反馈。0新物质接受，协议step21-joint-block-global-v1.md。

tmux step21-joint-global-77843，outputs/review-20260925/joint-global-watch-77843，watcher mode joint-global-validation、最长18000秒，学校CLI只读无工具。定时审阅每30分钟，未知/错误不盲重试。运行冻结operations/src/scripts/hpc/diagnostics和声明测试、协议。

备份Mac outputs/review-20260925/pre-joint-global-validation.bundle、automation-before-joint-global-validation.toml，school /home/scc/pb24511938/pre-joint-global-validation.bundle。取第一阶段或完整包后须新审计入口；旧单块/短步入口硬编码不同实验，不能原样套用。全频source/block/slab/半步/身份/资源/原门都要保留，若进入反馈仍固定原r20四组合三范数。
