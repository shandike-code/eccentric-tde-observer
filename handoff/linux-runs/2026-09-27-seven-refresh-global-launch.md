# 刷新七块方向的全域验证78411已起跑

2026-09-27 16:47:05提交、16:47:06开始；16:47:49实测RUNNING/anode16、status=preparing、stderr空。源码c64ee8ac1717ee59ab71b4d20cf9aa65afec4b85。32CPU128GiB，Students/qos_stu_cpu_long，16worker，4小时硬限20:47:06；这不是得到大气解的ETA。

Mac33tests/0.74s、Linux33tests/17.31s，compile/bash-n通过。前提78253元数据及78405实际数组扫描/Mac归约已经独立审查，通过不等全域门通过。源78161 map10、局部候选78253，r20/x20/旧物理层不变。

run outputs/hpc/step21-seven-refresh-global-20260927，operations/validate_step21_seven_refresh.py/.sbatch，协议step21-seven-refresh-global-v1.md。先实际full/half各1map，全域科学门全过才controlmap2/pair02；原七门和物理域过才controlmap3..10/pair10。总最多11map两反馈，0新物质接受；首轮对78161是初值位移，次轮对首轮是八map漂移。失败停止保全，不自动重试或改门。

平台只读监督tmux step21-refresh-global-78411，watch_seven_refresh_global.py --mode joint-global-validation --seconds 18000，目录outputs/review-20260925/seven-refresh-global-watch-78411。启动和终态保存scontrol及CLI回执；CLI实际模型按返回记录，不冒称Claude，不代替科学审计。后续若scontrol失效且sacct空，先读watch的scheduler-terminal.json，不猜作业失败。

启动JSON为20260927-seven-refresh-global-launch.json，首观察20260927-seven-refresh-global-initial-observation.json。备份Mac/学校pre-seven-refresh-global.bundle，自动化快照automation-before-seven-refresh-global-78411.toml；每30分钟定时审阅已恢复，SSH中断提醒用户Terminal重连并暂停重复提醒。运行期冻结声明数值代码、测试和协议，仅添加报告/审计。Mac/学校快进同步及GitHub推送，无强推。

下一次先取full-half-validation或complete小包校验SHA/清单和真实map/worker回执。首阶段审计可参考review_step21_seven_global.py，但必须替换为78411/78253/78405及78161原全域参照，selected=seven-refreshed-cores21-to27-and45-to51-full；不能套77577基准。若反馈已开始，审计用seven_refresh_global_validation源键、from_78161_comparison，并保持r20窗口分母不变。当前20次接受，第21未接受，尚无自洽柱或整盘I_nu。
