# 78548首阶段真实映射13门独立核验通过

本报告只覆盖本轮首阶段的short及half两张真实map；作业78548仍在运行，不能把首阶段包的feedback_pairs=0读成当前作业始终没有反馈。学校21:30左右已经进入pair02。后续条件续跑由已冻结协议控制，本轮不提交新作业、不改运行代码。

归档full-half-validation-1790515559175697982.tar.gz，2870661bytes，SHA 60c105ccf828aafff0c272c6ca88777d98f56d8baae6905028421eea05a49768；received outputs/review-20260925/seven-refresh-short-78548-first-received。新audit review_step21_seven_refresh_short_first.py验证324files、730codeclaims、152processreceipts，301片平方和用math.fsum独立归约，再以76自然块最大值核对control/half及原78161map10。完整源链78161/78253/78411/78516、t=.7878307756816162、x20trial逐位、config/seed、全频所有权与有限非负报告均核对。

short/half实际L2比0.5200968554386884/0.7545701952466926，Linf比0.9128625462222164/0.7741872222512552；半步仿射偏差/原L2=3.899309084329648e-10，最大偏差/原M=8.497270749777064e-10。short对78516第三遍预测相对差L2=2.360919225707345e-13、Linf=3.580138799057223e-11，均远小于事先1e-6门，未调公差。实际L2降低47.9903%、最大缺陷降低8.71375%，完整13门通过，包括辐射<1e-4和边界<1e-3且不增。

POST-RUN：归约值有限，152worker回执returncode0且内存守卫通过，峰3584664KiB（约3.419GiB）、parent2212093952bytes<6GiB。读取时父stderr为空；运行目录未找到非空*.err，但首阶段归档不含worker stderr，故不将其说成逐worker警告原文均已审空。图20260927-seven-refresh-short-first-review.png已目视：最大峰仍在核外block20且低于原全域最大值；half主峰在另一块，不能用其中一条曲线代表另一条。全部频率参与，未删除小频尾。Mac未重读大场、重算候选数组或重解算子，相关false字段保留。

结论限于：78516预测的数值短步在原真实算子下确实降低辐射缺陷，并通过既定内层检验；不是仅检查实现一致性，也不是未知真解的严格误差界。下一阶段需原七门/物质正域及八map四组合三范数/r20的反馈稳定性；非零物质残差本身仍须另行求解。无新物质更新、物理dt与r20均不变。

只读CLI草稿actual deepseek-v4-flash[1m]，原稿outputs/review-20260925/seven-refresh-short-first-lecture-draft.json；正式讲义56节纠正三个推理边界：实际缺陷收益不只是代码一致性；首阶段反馈0不等正在运行的作业没有反馈；没有新物质更新不意味着不能在固定x20上计算新的物质残差。已准备对应新source键的反馈审计脚本review_step21_seven_refresh_short_feedback.py，只有语法核验，未对未收到的反馈数据宣称E2E通过。

Mac备份pre-seven-refresh-short-first-review.bundle；学校快进前同名备份。新审计代码/图/报告/讲义入Git，运行数值文件不变。接受计数仍20，不是20个物理时间步，尚无自洽柱或整盘I_nu。
