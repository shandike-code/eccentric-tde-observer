# 第二个有限物质步接受；确认通过后同allocation推进第三步

## 74760实际结果

2026-09-21 16:58:50至17:44:45 CST，anode17、32CPU/128GiB，45分55秒，`COMPLETED`、`ExitCode=0:0`，stderr为空。父状态`formal_acceptance_requires_review`、candidate=`full`，10map/3pair、无active/pending。full第二对反馈（map7/8）原16门全过；half按“接受即停”未运行，不是预算耗尽。

|量|新冻结基态$x_1$|接受的$x_2$|本步比值|
|---|---:|---:|---:|
|编码残差L2|15.2484926808|14.9756293738|0.9821055554|
|质量加权|0.5883923687|0.5711492733|0.9706945632|
|最差单元|3.4575181415|3.4360677533|0.9937960157|

对新控制final，三个比值分别为0.9820718837、0.9710390981、0.9936810735；candidate previous/final与control previous/final全部四组合三范数均小于1。上述是log/simplex编码残差，不是能量。

相对最初冻结基态，$x_2$三个比值为0.9606620369、0.9282685840、0.9884870239。这是统一旧参考下的有限精度趋势，不替代本步正式分母。只有两次有限步，不能据此外推最终柱收敛时间；最差单元累计改善仅约1.15%，不能称接近完成。

原子/直接/正式加热变化约`3.570874667e-4`，门`1e-3`；内层噪声/试步信号`0.0552715850`，门0.1。两辐射端点残差`5.1526967858e-5`及`4.3658034913e-5`，均小于`1e-4`。最小气体热能分别`8.8642432322e12`、`8.8452162141e12 erg/g`，两端均0/128失败。第一轮14/16门的拒绝判决保留，不追溯修改。

## 证据与核验

整包学校`outputs/hpc/outer-step2-20260921/archives/accepted-review-1789983868215895877.tar.gz`，140726256字节，SHA256 `ae7aa1e027c9891a098431b4b8750bb0ad30316cc23c3b65563e25aa4e9a152d`。Mac `outputs/review-20260921/outer-step2-74760-accepted.tar.gz`及`outer-step2-74760-accepted-received/`；整包和3134份manifest文件全核。

只读审阅器复核新基态/分母/trial位移定义、physical old来源、76块partial和连续端点SHA，重算保存残差的三个范数，重现正式接受比值。没有在Mac重求物质响应；下一批source预检仍在allocation内逐位重放。

760份map报告强度有限非负，原生峰值3500.9375MiB；1216份map/feedback中继收据全部退出0且通过独立内存门，proc峰值4036428KiB。调度终态在Mac `outputs/review-20260921/outer-step2-74760-terminal.json`。Git证据`handoff/evidence/20260921-outer-step2-74760-accepted.json/png`，图已目视核验，标题仅标有限步接受。

POST-RUN：第二个有限物质步成立，全部原判据、同尺度控制比较及气体物理域相互一致；暂无耦合柱收敛、独立初值历史无关或整盘$I_\nu$就绪证据。

## 下一组合批次（运行前声明）

入口`operations/confirmation_then_outer_step.py/.sbatch`，run预定`outputs/hpc/confirm2-then-step3-20260921`。32CPU/128GiB、16worker、6小时上限；总预算**24张map、8对反馈，最多新增一个接受物质步**。按近期成本预计约1.5–2.5小时加排队；若确认未过则更早停止，墙钟上限不是预计耗时。

### 阶段A：确认第二步，最多6map/3pair

在`confirmation/`中复用原确认流程：控制$x_1$2map/1pair；已接受$x_2$在同一物质下追加2map/1pair，再从其最新输出追加2map/1pair。候选原基态仍为$x_1$、正式分母仍为$R_1$。不能在这一步先改成$x_2$分母，更不能把固定物质确认计成新的物质步。

源必须是74760/full第二轮接受，8张history、无active/pending、16门全true；方向明确取74760声明的`outer_baseline.residual`。预检源config/trial/protocol、全部partial/端点来源及实际原响应，逐位重放最终残差，原九项派生门重新计算。大态hash只在allocation。两确认组需原16门及新控制四组合三范数全部支持，不能只看总状态。

### 阶段B：仅A通过后进入第三步，最多18map/5pair

同一进程先持久化`transition.json`，固定确认报告、confirm4状态、反馈摘要SHA，才创建`next-step/`。新基态$x_2$取确认4的trial编码，$R_2$取确认4实际原响应并逐位重放。

$$
x_{3,\alpha}=x_2+\alpha R_2,\qquad\alpha\in\{1/256,1/512\}.
$$

第三步先零控制2map1pair，然后全步最多8map2pair；全步未接受才半步最多8map2pair。保留每4map反馈、原16门、独立能量账本和新控制四组合。新协议明确`outer_iteration.index=3`和确认4来源，正式分母改为$R_2$；旧模板保留，不修改已声明文件。

两阶段都保持phase1367、dt889.419892762322秒、原密度及physical old时间层。所有trial先写再初始化，完整元数据、decoded物理字段、native镜像和seed身份逐项验证；原trust region、6GiB双内存守卫、标准库中继、`NUMPY_MADVISE_HUGEPAGE=0`不变。

### 故障、恢复、预算

顶层`declaration.json`冻结全部代码和源状态/判决，分别记录阶段6/3和18/5上限。预算同时计已提交与活动map、已完成与待结反馈；每阶段内部仍用原守卫，跨阶段总量再核，恢复不能重新领预算。

A不通过时绝不创建B；停止信号在A完成后、B开始前也检查。USR1当前worker批次收尾，不继续派发。账本失败可恢复，但欠反馈先结清。程序/资源故障是终态，不归为普通科学拒绝。第三步首次接受即归档停；若原门接受而新控制不支持，保留原接受并标`fresh_control_corroborated=false`待审，不继续外层。没有自动重新提交、无限循环或物理时间推进。

保留所有74760源和新阶段大态；每个阶段反馈/终态自动归档，Mac继续取小包核验。默认4核仅在有独立审计需要时使用，不重复计算填满额度。

## 代码与验证记录

新准备器保留`accepted_step_confirmation.prepare`和`second_outer_step.prepare`的逐项血缘/响应/种子检查，仅显式改源、声明字段和第三步编号；旧源码不改。新增组合状态机和恢复测试。Mac76 passed、4项Linux专用skip；学校须全部通过后才起跑。真实来源预检是batch第一阶段，失败不得进入新map。

改前Mac和学校均保存`outputs/review-20260921/pre-confirm2-to-step3.bundle`；Mac另存`automation-before-confirm2-to-step3.toml`。后续提交ID、Linux测试和作业ID实测后追加。

## 已提交74795

学校Linux80 passed（20.91秒，无skip）；Mac76 passed/4Linux专用skip。代码`dfbab46bf005a5195709bad29c54bbab341f2d0d`在Mac、学校和GitHub三端核验一致后提交。

2026-09-21 18:03:00 CST提交74795，18:03:04在anode17开始，32CPU/128GiB、`qos_stu_cpu_long`、6小时上限（次日00:03:04）。18:03:27为RUNNING，顶层status=`confirmation`、计数0/0，stderr0字节；源重放正在执行，此时不宣称完成。

只读watcher PID1314194，输出`outputs/review-20260921/scheduler-74795/scheduler-terminal.json`及`watch-74795.log`，30秒检查、最长24小时；独立session与关闭标准输入保证不持有SSH管道。Mac启动证据`outputs/review-20260921/scheduler-74795-start.txt`。

已执行：`sbatch --parsable --export=ALL,TDE_RUN=outputs/hpc/confirm2-then-step3-20260921 operations/confirmation_then_outer_step.sbatch`，不要重复提交。进度须同时读取顶层、`confirmation/status.json`及`next-step/status.json`；顶层只在阶段边界刷新，其内部计数可能落后于子状态。完成此次衔接后heartbeat恢复30分钟，阶段自动转换不等待heartbeat。
