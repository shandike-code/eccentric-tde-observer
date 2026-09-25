# 76946审计与下一批真实映射检验

76946于2026-09-25 08:06:29—08:14:22在anode18运行，默认4CPU/16GiB，墙钟7:53，COMPLETED/0:0，stderr为空。运行只读取76931各自连续三態，没有写候选或运行新map；正式物质接受数仍20。

归档`complete-1790295259081734442.tar.gz`为45388字节，SHA256 `a99b83daf35e972fb4058ea5f871e47c020b3c9722e1cff00b42849faf14c8f5`。Mac检查归档和全部3个工件SHA、677条源码声明；三个case各4份源元数据与已独立审计76931归档字节相同；连续历史和retained的三态身份一致。独立从Gram复算系数、差分平方及其正定性，核76块无遗漏、无候选写入、峰RSS约1.00GiB。没有在Mac下载大态或重算全场积分。证据见`handoff/evidence/20260925-step21-radiation-scan-review.json/png`和终态JSON；图已查看。

| case | 全局系数 | 原全局残差 | 预测全局残差 | 预测/原 | 最差块自身相对残差 |
|---|---:|---:|---:|---:|---:|
| control | 30.75189677 | 6.96439217e-6 | 5.13688882e-6 | 0.73759327 | 0.16048557 |
| thermal | 28.15916187 | 6.23018565e-6 | 4.80120243e-6 | 0.77063553 | 0.15938984 |
| population | 34.54479822 | 5.90895498e-6 | 4.87457693e-6 | 0.82494738 | 0.15936810 |

全部预测强度非负；预测边界谱变化分别1.01268e-5、1.77224e-5、6.86195e-6。全局残差按整场最大强度归一化，弱尾块按自身强度归一化，故两者差距不矛盾。三者都值得一次真实映射检查，但预测改善只有约18%—26%，不能宣称相当于完成30张map，更不能保证解决加热或物质残差。

## 有界决策

新增`operations/validate_step21_radiation_affine.py/.sbatch`，协议`handoff/protocols/step21-radiation-affine-validation-v1.md`。32CPU/128GiB、16worker、5小时上限，最多9map/3对反馈。

先分别写三个受全场非负限制的全局候选，逐一实际运行原map。除实测残差改善、原内层/边界/资源门外，再逐单元比较真实输出与代数预测，避免标量残差碰巧一致。全场预测误差必须同时小于整场强度尺度1e-7和真实映射增量0.1。后两者是保守的算法续算门，不是新物理误差承诺。

三个真实检验全部完成后，control检验通过才追加两张map及零位移反馈。control反馈稳定且物理域有效时，对检验通过的thermal/population各追加两张map和一对反馈；保留原r20三收缩门及新control四种组合。原门失败可诊断，但物理域失败停止后继。全部结果均不自动接受21。本任务不改变物质候选、原子核、物理dt或既有科学门。

## 运行前检验与备份

[PRE-RUN CHECK]

Code: PASS — 本地65项相关回归通过，含新全场误差检验、坏系数/负值/NaN拒绝、真实检验先于反馈、控制失败停派发、三张硬上限及停止标志；Shell和diff检查通过。
Logic: PASS — 已审计源三态到固定trial，再到候选与真实map，只有实测通过才追加反馈；trial先落盘、native身份复核。
Physics: WARNING — 固定物质的辐射数值加速，不代表耦合解；高频局部误差和完整反馈仍需保留。

Key Issues:
1. 不跨case拼接历史，不把预测场当作已测场。
2. 真实全场差异、原残差与新control比较并存，不只选择最小指标。
3. 单批硬上限9map/3pair，物理域失败或资源故障停止，无盲重试。

Decision: RUN — 学校同组测试及三端Git一致后提交。

Mac备份`outputs/review-20260925/pre-affine-step21-validation.bundle`和`automation-before-affine-step21-validation.toml`；学校备份`/home/scc/pb24511938/pre-affine-step21-validation.bundle`。旧`.dat`、旧代码和协议保持原字节。Markdown机械检查仍只报告既有六份lecture；没有批量重写，也不宣称全库通过。审计画图初次把字典直接传给Matplotlib导致类型错误，已改为显式case列表后重跑完整审计并查看图；不涉及数值结果改动。

## 学校验证与启动记录

Mac65 passed（1.33s），学校同组65 passed（16.61s），Shell/diff通过。数值提交`7096c0434053a7fdf09a7150120466852168b4d5`；仅新讲义下标格式随后提交`bdb4b0f568f1592ee51862d437ba7101a4cd2b1f`。起跑前Mac／学校／GitHub完整SHA一致、工作树干净、队列为空、新目录不存在。

作业**76957**于2026-09-25 09:42:07提交、09:42:08在anode18启动，qos_stu_cpu_long、32CPU128GiB，截止14:42:08。09:43:09实测RUNNING/preparing、stderr空、独立watcher存活；准备阶段包括大态和历史依赖SHA，不等于死锁。运行目录`outputs/hpc/step21-radiation-affine-validation-20260925`。

watcher会话`step21-affine-76957`，21600秒，输出`outputs/review-20260925/scheduler-76957/scheduler-terminal.json`。启动证据`handoff/evidence/20260925-step21-affine-76957-start.json`。30分钟定时审阅切换至76957，原76946不再提交。下一轮取得检验或反馈小归档后独立核SHA、全場差异与原门；尚不把起跑称为通过。

补充讲义`lecture/项目讲义/2026-09-25_辐射慢模外推与真实映射检验.md`已根据真实数据、代码和图重写。Claude初稿中关于整盘范围、只读扫描是否执行map及最大范数的错误均已纠正；最终讲义数学规范只调整该新文件，没有改历史六份文件。
