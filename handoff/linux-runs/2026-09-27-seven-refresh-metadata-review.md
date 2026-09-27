# 78253刷新外侧场的七块探针：元数据审计通过，原数组待查

78253于2026-09-27 14:14:29–15:04:20运行，COMPLETED0、49:51，32CPU128GiB/两个worker。重连时scontrol已清理、sacct为空；证据为只读监督器当时保留的scheduler-terminal.json，不以当前空队列推测成败。监督器正常终止，无新map/反馈/物质接受。

完整小包complete-1790492660158109702.tar.gz，98944bytes，SHA256 bf65f6357f16a116085dd014575f836dd0998ba14de48a39ee4cb321f019bfe2。Mac目录outputs/review-20260925/seven-refresh-78253-received。新审计review_step21_seven_refresh_metadata.py核对13files、726代码声明、源78161十map连续历史、实际输入输出、trial/config/state哈希、旧77577对排除及两worker回执。源输入21c2e92324d2dac19d13e532d65c1d98683c225a8b99e2858b1c31ebb1e7ff00，输出99fdb1331f197d78d115f1b0e6dba602d9ee6eef966ce10e8cb6036fe2868f89；各10099884032bytes，不传Mac。

|核心|实际局部L2比|Linf比|独立半步仿射误差/原L2|观测峰KiB|
|---|---:|---:|---:|---:|
|21–27|0.3548285088282914|0.42674801487247704|3.851677032148447e-10|21213520|
|45–51|0.23235419853963563|0.2886860951151553|5.491575659949575e-10|20832652|

两组先原算子逐位重放，场/缺陷误差均零；九局部门均通过。各16GMRES、info2、linear_audit_passed=false，不能称线性收敛。两个candidate及mapped均正且有限的声明已核，Mac尚未独立读取数组。prediction_error=0在full step1时是同一端点的比较，不把它当独立证据；独立半步另算真实映射，误差如表。两组分别2785.15/1510.86秒局部计算，worker进程2837.79/1559.75秒，都低于3600秒硬限。

block48保留两行RuntimeWarning，来自affine_krylov.py:250正性步长上界的正比值除法。代码随后要求最小上界有限正值；本次最后eta=1，正性检查通过。部分极大比值溢出不等于物理场溢出，但不能用此解释代替原数组扫描。block24与父stderr空。原核不修改、不压制warning。CLI终报实际deepseek-v4-flash[1m]；其“峰≈20.7GiB”混淆MiB/GiB的十进制缩写，真实/proc峰为20.2308/19.8676GiB，以上述KiB为准。

下一步默认4CPU16GiB/30分钟只读原数组审计，operations/scan_step21_seven_refresh_arrays.py/.sbatch，协议step21-seven-refresh-array-audit-v1.md。两份1879048728bytes局部NPZ仅学校，逐1792频率检查全部32角4096深度的非负有限、L2/Linf，读取前后SHA；Mac独立fsum，小统计对比2e-13、旧整数组L2比较2e-11预定公差保持。0map/反馈/全域候选/接受，先核实再安排全域真实检验。

Mac E2E审计通过并目视图；5项新扫描测试通过0.07s、compile/bash-n通过，无测试warning。Linux测试和具体job另记启动回执。备份pre-seven-refresh-review.bundle与automation-before-reconnect-20260927-163242.toml，原记录保留、只添加新代码和审计。当前仍20次接受物质更新，第21未接受，不能推出耦合柱或整盘I_nu完成。
