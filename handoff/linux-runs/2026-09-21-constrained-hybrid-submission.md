# 74472：全场约束步长批次起跑记录

2026-09-21 11:59:01北京时间提交，11:59:03在anode16起跑，qos_stu_cpu_long，32CPU/128GiB、16原map worker、6小时上限，调度EndTime17:59:03。run为`outputs/hpc/constrained-hybrid-20260921`。上限不是完成时间预测。

执行提交`437acdd254b77e156659cf9c28f060d0fdc37e5d`，提交前Mac、学校、GitHub SHA一致且工作树干净。Mac合成/回归67通过、4个Linux专用案例跳过；学校71项全通过，21.85秒，包含实际进程退出码、USR1完成当前worker、TERM传递、独立/proc内存守卫。sbatch语法检查通过。开发测试捕获的两处路径推导式括号错误在提交前修正。

PRE-RUN：Code PASS（接口及上述测试），Logic PASS（7图/2pair账本、预测与实测分离、连续已测端点），Physics WARNING（较小辐射步是否通过原门仍待实测）。旧物理核、原正式门、物理时间步、能量定义及旧结果冻结。真实trial与输入大场SHA核验在allocation内先执行，未通过不跑首图。

11:59:33现场RUNNING，父状态preparing、0completed/0active maps、0completed/0pending pairs；不把准备中说成科学通过。轻量worker中继本身通过Linux测试，实际native worker峰值需在后续process receipts与原报告中复核。

终态只读watcher PID181388，每30秒、最多24小时，输出`outputs/review-20260921/scheduler-74472/`，日志`watch-74472.log`；无提交/取消权限逻辑。Mac起跑快照`scheduler-74472-start.txt`已保存。阶段小工件由运行目录archives自动归档。

预算与数学声明见`2026-09-21-constrained-hybrid-batch.md`：复用已存局部方向，基态先求全场Linf可行步；若可行则独立真实选定/半步图；候选物质先补1张全步诊断图再做相同检验。两态均通过后各续1图，原反馈与独立账本自动衔接，总上限7图、2pair。父计数从子状态重算，即使故障也不再显示旧0值。无合格方向或任一前置门失败即停止，不调门、不补跑凑额度。

改前备份：Mac pre-constrained-hybrid.bundle、automation-before-constrained-hybrid.toml；学校pre-constrained-hybrid-school.bundle。增量包constrained-hybrid-code.bundle保留，旧74437/74454已核验归档不改动。下一次只审阅74472现场，不重复准备同名目录或重提作业。
