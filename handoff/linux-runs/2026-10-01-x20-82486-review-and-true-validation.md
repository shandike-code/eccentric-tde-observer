# 82486预测通过：独立审计及两张真实映射方案

82486于Oct1 01:42:29–01:49:58 CST完成，Slurm COMPLETED/0:0，4CPU16GiB，7分29秒；程序443.276309秒，峰值884322304B，stderr空。0新map/反馈/物质步，不写候选dat。数值版本db08fcdfc620a124a13d33573b453efde3b71f01。

八文件小包`82486-boundary-prediction-review.tar.gz`，148028B，SHA256 `daee05d7967838de75839a8a7852035c0604afff8e27d03c0e731b508e0397b3`；本地`outputs/review-20260925/x20-boundary-prediction-82486-received`。专用审计未修改、真实工件一次通过，证据`20261001-x20-boundary-prediction-82486-review.json`。全部301片、76块、9632组完整，源声明/代码/前后八场哈希/终态/资源核验通过；80位Decimal独立归约，并以实际binary64逐块系数重算Gram二次型与完整边界谱，和实际全场统计一致。Mac只读小工件，没有下载或重算大场。

|指标|锚点|full|half|
|---|---:|---:|---:|
|缺陷L2比|1|0.422420343356|0.668799081815|
|缺陷Linf比|1|0.499136231889|0.646831024351|
|radiation|2.66207900082e−7|1.32869658641e−7|1.72188710391e−7|
|boundary L1|6.86424701323e−9|6.52103333115e−9|5.82920258589e−9|
|boundary bolometric|1.80504437201e−9|1.71479146627e−9|1.75991792179e−9|

四个候选/预测场最小值均为0，无负强度；全部11项原门通过。有限性、量级和矩阵/全场一致性无异常，尚无真实映射或物质响应结果。上游SLSQP的200迭代失败记录仍保留，预测成功不追认其最优性。

下一批新增`operations/x20_boundary_validation.py`、`x20_boundary_validation_fields.py`及sbatch。复用82214已验证的真实映射流程，但改为当前82486的76×3系数、82441八源场以及82273原trial/config/端点协议；几何仍按声明使用81769旧路径。每128组自然块选择自己的系数，每32组流式构造full/half，短尾保留；负值和非有限直接拒绝，临时文件不提升。候选写入顺序和82486预测一致。

真实入口先核完整82273归档对应trial/config/state/endpoint16/pair16，再核两支算子配置相同、x20 encoded/base/direction/r20/relaxation/native及物理old/phase/dt逐项身份。先复制trial再初始化子run，避免旧migrate_trial陷阱。候选/真实输出SHA前后核验。每支只一张map，16worker，76回执全部必须正常、各RSS<6GiB，父进程<6GiB。

资源Students/qos_stu_cpu_long，32CPU128GiB2h，沿82214脚本排除anode01，USR1提前300秒；新目录`outputs/hpc/x20-boundary-validation-20261001`。最多2map、0反馈、0物质步。真实收益/非负/边界门不变；新增的四个full/half真实输出减预测的L2/Linf偏差门仍为原缺陷归一化≤1e−6，half真实缺陷相对端点平均的L2/Linf亦≤1e−6。不得用预测输出冒充T(q)。

本地26项定向测试通过，覆盖跨128组系数切换/短尾/输出与可知仿射算子对照/故意预测偏差拒绝/负候选不提交/来源和预算篡改拒绝。shell和编译检查通过。学校复验、实际job另记。独立审计入口`review_x20_boundary_validation.py --job JOB --base ARCHIVE_BASENAME`已准备并过语法，复用已验证的独立统计归约；不能称未来结果已E2E通过。

两端`pre-82486-review-20261001.bundle`已保存；运行前发出具体Code/Logic/Physics检查。旧核、旧数据、旧判定不动。真实map通过独立审计后才考虑有界反馈窗口，当前没有足以声称自洽大气、整盘I_nu、剩余物理误差界或模型无解的证据。

## 82503起跑

学校26项复验通过（20.43秒），代码三端同步`84fd8b4c9607200b90c0342d91e7c8f83d256206`。02:28:00 CST提交82503，qos_stu_cpu_long、32CPU128GiB、2小时。回执`20261001-x20-boundary-validation-submit.json`。学校另存`pre-boundary-validation-launch-20261001.bundle`。运行中数值代码与协议冻结；后续提交仅记审计和回执。

只读watch `outputs/review-20260925/x20-boundary-validation-watch-82503`，PID101338仅启动记录，每60秒观察、最多8400秒。CLI显式采用既有Node PATH、无工具，终态先保存再请求意见，不提交/取消/改动。当前源码终态归档由原`reused.archive`写在run/archives，含全小工件及完整SHA清单，不含dat；取complete归档和终态/原日志独立审计。如为failed/interrupted，先审失败而不是运行假定成功的入口。
