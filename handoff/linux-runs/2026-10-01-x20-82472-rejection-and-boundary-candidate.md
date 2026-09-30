# 82472拒绝审计与边界约束有限候选

82472于2026-10-01 01:19:32–01:27:13 CST运行，Slurm COMPLETED/0:0，4CPU16GiB；程序457.807800秒，峰值890130432B，stderr空。所有旧场前后哈希通过，301片/76块/9632频组完整；0新map、反馈、物质步，不写候选dat。作业正常结束而科学失败，两件事分别记录。

小包`82472-block-prediction-review.tar.gz`共8文件、147264B，SHA256 `e2bc74a7fa1ee6e7a50a2973812b050d908fbf04b8593b1e04071a87f63d45b3`。独立审计`review_x20_block_window_prediction.py`真实工件一次通过，证据`20261001-x20-block-prediction-82472-review.json`。核全部源码/来源/系数/终态；80位Decimal逐片重组，并从原basis与实际binary64系数独立预测平方缺陷和边界统计，均一致。Mac未重读9.41GiB场，不能把小工件审计称为Mac全场重算。

## 拒绝原因和第一个不值得跑的修改

只有第65块的4片出现负值（起始频组8320、8352、8384、8416），full输入/预测输出均有负值，half均非负。首片最负值约−5.90425e−56，原场该片尺度3.25318e−55；绝对数很小，但约占其局部尺度18%，不能按舍入噪声裁掉。生产判定只给`full_field_nonnegative=false`，其余门未评估；原始失败不改写。

新筛查把第65块full改用已经测过的half，其余块保持full。直接拼接既有统计，得到full缺陷L2比0.285084106314、Linf比0.293662180159，非负和辐射门通过。但边界L1从6.864247013e−9升到1.385397438e−8，bolometric从1.805044372e−9升到9.022949731e−9，不满足原“不增加”门。证据`20261001-x20-block65-half-proposal.json`，明确新half没测、重算顺序不同；因此没有为这个已知不合格方案提交作业。

## 边界约束选点：优化失败与有限点资格分开

每块在原锚点和上述非负混合端点之间取t_b∈[0,1]，原三个系数同乘t_b。没有重新外推更远，cap17保持，所有块保留；精确算术下输入和预测输出都在两个非负场之间。实际binary64重算仍必须查非负。

目标为存储Gram总平方缺陷。对完整9632组边界谱加入L1和有符号总通量约束；归一化使用各组端点最小通量累加所得的保守分母下界，再向下留1e−12数值余量。内部目标为原边界变化的0.95。SLSQP一个0.5起点、最多200迭代，达到迭代限，`solver_success=false`、原`eligible_for_full_field_scan=false`保留。L1内部约束末点超1.8557171e−7归一化量，因此不宣称严格满足5%内部目标，亦不宣称最优性。

该失败末点本身是有限数据，是否满足原科学预测门是另一问题。另立`certify_x20_boundary_candidate.py`，核所有系数来源、[0,1]范围、精确有理数cap17，再以独立80位Decimal重算。这不调用优化器，不改优化退出码，不延长搜索预算。原科学阈值未变；得到：

|量|锚点|full预测|half预测|
|---|---:|---:|---:|
|缺陷L2比|1|0.422420343356|0.668799081815|
|边界L1|6.864247013e−9|6.521033319e−9|5.829202573e−9|
|边界bolometric|1.805044372e−9|1.714791482e−9|1.759917930e−9|

独立筛查支持“一次全场预测值得做”，不支持“优化已成功”“真实映射已通过”或“物质解已改善”。原搜索失败、另立可行性决定均存档，不能只展示后者。证据`20261001-x20-boundary-constrained-selection.json`和`20261001-x20-boundary-candidate-feasibility.json`。

## 下一次有界执行

新入口`operations/x20_boundary_candidate_prediction.py/.sbatch`，新目录`outputs/hpc/x20-boundary-candidate-prediction-20261001`，4CPU16GiB1h；最多三遍八场读取，0map/反馈/物质步，不写dat。沿用原逐单元full/half检查核，来源绑定82441 basis、82472拒绝审计、block65提案、失败优化末点和独立可行性记录。逐位检查系数=提案系数×t。不触碰旧数值文件或科学核。

25项定向测试通过，含拒绝身份/SHA/系数/范围/预算/最优性声明篡改；bash语法与py_compile通过。所有小工件数值有限，量级与源矩阵/边界统计一致，负值判定保持，无任意修正。运行前具体PRE-RUN另见任务记录；学校复验和实际作业号另存提交回执。若预测通过且独立审计，再用32CPU真实full/half映射；失败则先诊断，不自动扩预算。

Mac和学校均保留`pre-82472-review-20261001.bundle`。CLI监督原报告曾写“需独立复核，并另跑真实映射”，缺少“仅合格候选才可进入”的条件；本审查明确纠正。CLI实际模型为deepseek-v4-flash[1m]，其意见不是验收依据。额外讲义调用首次因非登录SSH的PATH没有claude失败，未改数值；确认已有`opt/node-v22.18.0-linux-x64/bin/claude`后仅对该进程补PATH重试。

## 82486提交回执

学校复验25项通过（15.69秒），Mac/GitHub/学校同步至数值版本`db08fcdfc620a124a13d33573b453efde3b71f01`。01:42:28 CST提交82486，4CPU16GiB1h；回执`20261001-x20-boundary-candidate-submit.json`。学校另存`pre-boundary-candidate-launch-20261001.bundle`。只读watch为`outputs/review-20260925/x20-boundary-candidate-prediction-watch-82486`，PID3724843仅为启动记录，最多4800秒；显式补已有Node目录PATH以便CLI可执行。运行中不修改声明的数值代码、测试或协议。

独立审计入口`review_x20_boundary_candidate_prediction.py`已准备并通过语法检查，复用已测的独立归约/Decimal对照；新工件尚未E2E。终态包约定为`82486-boundary-prediction-review.tar.gz/.json`，8项：declaration、prediction、summary、status、scheduler-terminal、claude-review-01及tde-x20-cpred-82486的out/err；缺项或调度失败如实保全。命令`PYTHONPATH=.:src:scripts OPENBLAS_NUM_THREADS=1 .venv/bin/python handoff/audit_tools/review_x20_boundary_candidate_prediction.py --job 82486 --commit db08fcdfc620a124a13d33573b453efde3b71f01`。不得把语法检查或预先准备的审计入口写成真实结果已通过。
