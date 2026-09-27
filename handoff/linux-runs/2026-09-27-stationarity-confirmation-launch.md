# 78594持续性确认启动与审计入口

2026-09-27 22:53:31提交78594，22:53:32 RUNNING/anode17，qos_stu_cpu_long 32CPU128GiB/16worker，4h至2026-09-28 02:53:32为硬上限，非大气ETA。数值源码e6935344da00598aac1f370818e737e0307e4dcb。Mac49tests1.10s、Linux49tests15.15s、compile/bash-n通过；真实小工件source_seed预检通过。

22:55:43实测仍RUNNING、preparing、stderr为空，declaration已经生成并固定78548最新后继SHA21e17d2fc6382b35471f0e514bb52f47222ea1279e8dd36333af4dd681ef16b0。源身份/声明已落地不表示第一map或反馈已完成。run outputs/hpc/step21-stationarity-confirmation-20260927，confirm_step21_stationarity.py/.sbatch，协议step21-stationarity-confirmation-v1.md。

最多16map、8/16反馈。首段任何原反馈/窗口条件失败立即停止；第二段还检查累计16map相对78548末反馈的漂移，四组合三范数除以原r20均<.001。接受仍20，零新候选/接受、零基准替换/物理dt改变。若通过也只是持续性见证，不能自动接受第21步。

平台只读监督tmux step21-stationarity-78594；watch_step21_stationarity.py --mode short-step-validation --seconds 18000，输出outputs/review-20260925/stationarity-watch-78594，启动rc0。mode名称是兼容现有解析器，新脚本的提示已改为16map持续性确认，无half是正常，不引用旧短步系数。实际CLI模型按回执记录，不把CLI意见当数值证据。

预备审计handoff/audit_tools/review_step21_stationarity.py已语法核验，尚无本次工件E2E结果，不能预报通过。它独立核8/16窗口和累计量，支持首段8map失败终态；map审计上限16，而旧review_step21_wide_validation.audit_maps上限11不能原样调用。原cw.audit_pair复用逐块反馈/能量/身份核验，窗口用独立fsum。若物理或原七门自身失败，需要对应失败审计，不删断言。

收到pair08或complete包后运行参数：--archive/--receipt/--received/--output按实际文件；--prior outputs/review-20260925/seven-refresh-short-78548-complete-received；--reference outputs/review-20260925/common-step21-76808-received/inputs；--physical-old outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz。完整包必须另给--terminal，包含job_id78594、COMPLETED及scontrol ExitCode0；旧调度记录清理时读取watch的scheduler-terminal.json。只读报告比较源78548，不再使用78161作为本窗口直接基准。

备份Mac/学校pre-seven-refresh-short-complete-review.bundle，源码/审计/讲义已快进同步并正常push。启动记录与准备审计单独提交，不改运行中operations、测试和协议。大场留学校，旧文件不覆盖、不清理。
