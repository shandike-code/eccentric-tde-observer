# 固定五块短步真实验证78041

2026-09-27 07:49:39提交并开始，anode02，Students/qos_stu_cpu_long，32CPU128GiB、16worker、4h硬限。数值提交837c52f，启动HEAD4d9ad85（后者仅规范讲义公式）。Mac30tests0.67s、学校30tests15.86s，compile/bash-n通过。

run为 `outputs/hpc/step21-five-short-validation-20260927`。入口 `operations/validate_step21_five_short.py/.sbatch`，协议 `handoff/protocols/step21-five-short-validation-v1.md`。固定t=0.3615903661179739，全/半真实映射、20%L2收益、最大非增、双范数预测复现和其余原门先行；成功才两轮反馈和八map漂移检查。最多11map两反馈，无物质接受、r20替换或时间推进。

监督tmux `step21-five-short-78041`，`handoff/audit_tools/watch_five_short.py --mode short-step-validation --seconds 16200`，回执目录 `outputs/review-20260925/five-short-watch-78041`。监督CLI只有只读JSON输入、无工具；数值代码和协议冻结。首次观测preparing、stderr0，不是已经通过科学门。

已保存启动回执 `handoff/evidence/20260927-five-short-78041-launch.json`，Mac备份pre-five-line-review.bundle、automation-before-five-short.toml，学校备份pre-five-short-validation.bundle。78039、78040工件不改，新的大场不传Mac。

下次先看状态、control/validation、pair02/pair10和归档清单。首阶段独立审计可参考review_step21_short_validation_first.py与review_step21_five_global.py，必须改78040来源、十块范围、0.8成本门及两项预测复现门；最终反馈审计参考review_step21_convex_feedback.py，改source key为five_short_validation。不要把旧硬编码job/源目录直接套进新判定。完成后取小包+SHA，核有限值、全域归约、端点身份、反馈门、八map四组合/原r20、资源与实际结论。失败停下诊断不盲重交。
