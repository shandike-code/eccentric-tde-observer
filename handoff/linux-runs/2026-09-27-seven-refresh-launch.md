# 用78161最新外侧场重新求七块方向：78253

2026-09-27 14:14:29提交并起跑，14:14:59实测RUNNING/anode16、preparing、stderr为空。源码0f09611797516de442f7fef9eb35f63eee91abf5。当前准备阶段尚未给出局部科学结果，不把已排上资源说成逐位重放或Krylov已经通过。

资源Students/qos_stu_cpu_long，32CPU128GiB allocation、仅两个worker，作业2小时上限；各worker32GiB/3600s，16次GMRES迭代及最多4次非Krylov局部map。使用78161 map10真实输入输出及外侧场，核心21–27、45–51，保持x20、r20、物理旧时间层和dt。零全域map、正式反馈、全域候选或新物质接受。禁止失败后自动重复、扩9/11块或放松原门。

Mac26tests/1.01s，Linux26tests/30.04s；compile/bash-n通过。测试输出无warning、失败或NaN/Inf证据，合成测试不替代真实场校验。上轮78161的完整数值、资源、图和解释核验见2026-09-27-seven-short-complete-and-refresh-plan.md；本轮POST-RUN科学核验必须等终态工件。

入口operations/pilot_step21_seven_refresh.py/.sbatch，协议handoff/protocols/step21-seven-refresh-pilot-v1.md，run outputs/hpc/step21-seven-refresh-pilot-20260927。两份local NPZ留学校，不下载Mac。运行期间冻结声明过的数值代码、测试和协议。

只读监督已启动，tmux step21-seven-refresh-78253，handoff/audit_tools/watch_seven_refresh.py --mode joint-block-pilot --seconds 9000，目录outputs/review-20260925/seven-refresh-watch-78253。CLI无工具，不自行提交、取消或改参数；实际模型按返回回执核对，不能冒称Claude或用其结论替代审计。

启动回执handoff/evidence/20260927-seven-refresh-launch.json，首观察20260927-seven-refresh-initial-observation.json。Mac与学校均保存outputs/review-20260925/pre-seven-refresh-implementation.bundle，同步为快进，GitHub已含数值提交0f09611。自动化更新前保存automation-before-seven-refresh-78253.toml，保持原30分钟周期。

下一次先查78253末态与complete/failed小包，已有源场与旧审计不重复取回。审查declaration是否声明source_job_id=78161、refreshed_halo=true；两组逐位重放、九门、真实局部范数、GMRES info、warning和资源回执都要保留。通过后使用默认4核对本次两份原数组做只读归约，Mac检查小统计。只有这些均过，才制定新全域真实验证，基场必须改为78161，绝不能把新方向拼回77577；物质参照仍是r20，不随源场刷新。

若局部失败，分析实际门与耦合，不增加同种试验预算。当前20次非线性物质更新接受保持、第21次未接受；未获得耦合自洽柱、整盘大气表或整盘I_nu。SSH断开不代表Slurm停止；须提醒用户在Terminal重连密码及动态码，恢复后先查既有job，不重交。

14:17:49再次观察：78253 RUNNING/3:20，status=local_pilot。声明source_job_id=78161、refreshed_halo=true、核心区间2688:3584与5760:6656、workers=2均吻合，父/两worker stderr暂空；两份逐位重放报告尚未出现，不提前判重放通过。记录见20260927-seven-refresh-startup-observation.json。

只读CLI实际模型deepseek-v4-flash[1m]。其首报称“32CPU但仅2worker，与申请不符”是错误推断：allocation上限与算法实际并发数本来不同，本次协议事先声明两组核心、两个worker；没有越配，也不声称实际用满32核。其“运行1分钟属正常”仅为观察，不能证明进程健康或物理正确。状态与数值以回执和独立审计为准。
