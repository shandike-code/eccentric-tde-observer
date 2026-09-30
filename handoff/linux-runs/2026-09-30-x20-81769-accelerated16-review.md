# 81769加速分支16−8窗口：独立复算通过，最终跨初值资格仍未评估

本报告补充同日cross08报告的待审事项。新归档`accelerated-map16-feedback-1790743625821043503.tar.gz`，227634064 bytes，SHA256 `ef9b1218ca3baab81131ce474d8502324691b426d2d42d7fcd3629cffcaedd67`。解包目录`outputs/review-20260925/x20-feedback-81769-accelerated16-received`；证据`handoff/evidence/20260930-x20-81769-accelerated16-review.json`。

## 方法与结果

复用本轮新增、独立于运行驱动的`handoff/audit_tools/review_x20_feedback_snapshot.py`。此次累计核验6447文件、1824份map worker与456份feedback worker回执，涉及A16/H8共24张map和3对反馈。全部声明、输入、trial/native记录、频率所有权、反馈归约、响应能量账本和完整残差检查通过。原反馈门使用原核，完整向量范数独立归约。Mac未重跑大场、native核或物质ODE。

对A16与A8的previous/final作四组合，先减完整512维残差，再分别取三范数；下表每一列独立取四组合最大，不在未归一化的不同范数之间混取最大。

|分母|L2|质量加权|最差单元|门|
|---|---:|---:|---:|---:|
|原r20同一范数|5.7090383279e-5|2.2780546608e-4|3.6685721852e-5|0.001|
|冻结80195同一范数信号|0.01592543868|0.03833743204|0.006204029138|0.1|

所有组合均通过。A16原七门也全部通过；最小目标气体热能previous/final为7.02275561411875e12/7.022759791567258e12 erg/g。相邻原子加热比较1.6197341715e-6。

耦合残差本身的质量范数是0.2825752922/0.2825773409，原r20为0.2619104205。窗口差小没有使残差为零。与旧80554 late16的比较依然失败，最大质量差/r20=0.0030160454、/信号=0.5075709465；这不是本次同支16−8窗口，不混用两个比较。

## PRE/POST-RUN与边界

PRE-RUN：Code PASS（哈希/索引/部分与终态判定及8项测试）；Logic PASS（不可变档案到四端点完整向量）；Physics WARNING（历史支与最终跨支未完成，有限窗口不是严格误差界）。Decision RUN。运行了审计，未新增Slurm作业或更改冻结生产代码。

POST-RUN：反馈和响应数组有限、物理域合法；最大worker观测4043288 KiB，低于6 GiB约束；审计stderr为空。8项审计范围和失败路径测试通过。窗口结果与平台逐项一致；不是以测试通过替代科学门。继续原81769预算，禁止重复提交、换r20、改物理步长或接受第21步。

部分归档`reference_calibration_eligible=null`。必须等待H16窗口、cross16全四组合及原率门，再用完整归档与COMPLETED/0:0调度证据验收。accepted20、new_material_steps0、baseline_replacedfalse、strict_error_boundfalse保持不变。

讲义§95由平台无工具CLI草稿后独立改写。实际模型deepseek-v4-flash[1m]；草稿将A8/A16误作两初值、把迭代端点称为物理时刻、把三种原始范数混取最大、把cross8当相邻门、把本次窗口当跨初值检验，均已纠正。原草稿和纠错JSON保留。该模型仅辅助写作，不作科学接受决定。
