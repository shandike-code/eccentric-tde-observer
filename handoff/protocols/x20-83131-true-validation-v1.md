# 已审83131候选：两张真实原映射

83131七文件、源码/来源、完整301片80位归并通过，原11预测门全过；full/half L2比0.7122464043391925/0.8479422364134811，Linf0.8309346076095544/0.9154528337092244，四minima0。c=[-2.5857236634643006,-1.0142763365356995,.45]。这是候选资格，不是T(q)或自洽解。

新run outputs/hpc/x20-83131-true-validation-20261002；32CPU128GiB/cpu_long，16workers，2h硬限，USR1提前300s。只生成新候选并各做full/half真实map一次，最多2map、0反馈/物质步。保留全部失败，不自动恢复/续交。所有字段写入只在学校，不下载或Git提交dat。

完整8场顺序为82989H16(previous,final)、82989H8(previous,final)、82518H16(previous,final)、82273H16(previous,final)。锚点是82989H16的previous→final，即原iteration15，不是final→mapped_final的iteration16。原82989归档、trial/config/state/manifest/feedback_protocol逐一核；冻结物理旧层、base和r20，trial三重逐位核及native物质/phase/dt核，phase1367、dt889.419892762322秒。先保存正确trial再初始化，防止pipeline.migrate_trial静默换回0.0625。

复用write_candidates原表达式，合成跨block边界测试核已写full/half与筛查表达式逐位一致；所有76块全域统一同c。真实映射仍用原worker/算子。保留原16门：完整真实缺陷L2/Linf/边界/原残差门，以及真实输出同预测和full/half仿射一致性；不把最后一个仿射一致性小量当候选缺陷比。预测p不是T(q)，正式观测/反馈需后续阶段。

源/代码前后SHA、种子与实际输出SHA、152worker回执、native与内存守卫；父进程<6GiB、每worker<6GiB，生成前free>=10*STATE_BYTES。原r20不换，accepted20不增加。输出declaration/candidate-claims/full&half state/maps/validation/summary及自动complete或failed/interrupted小归档（排除dat），需要Mac独立审计后再决定后续工作。
