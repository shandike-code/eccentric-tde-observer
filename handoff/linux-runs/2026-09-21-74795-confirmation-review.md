# 74795第二步同态确认审阅

## 18:38巡检快照

SSH正常，74795在anode17继续使用32CPU/128GiB，stderr为空。顶层status仍为`confirmation`且计数0，是阶段边界才刷新的快照，不是作业没有工作。`confirmation/status.json`实际为6map完成、2pair完成、1pair待结算，current_case=`confirm4`。

control2map1pair已通过内层/五反馈稳定性及两端物质域检查。第一确认组confirm2原16门、accepted决策及新控制四组合三范数均通过：

|量|第二步首次接受|confirm2|
|---|---:|---:|
|原子加热变化|0.0003570874667|0.0002178620648|
|内层噪声/试步信号|0.0552715850|0.0348906765|
|L2/本步冻结基态|0.9821055554|0.9814829737|
|质量加权/本步冻结基态|0.9706945632|0.9693000457|
|最差单元/本步冻结基态|0.9937960157|0.9939251147|

最差单元比值略升，仍在1以下，不称全部指标单调改善。confirm2最小气体热能previous/final为`8.8261190623e12`、`8.8071367767e12 erg/g`，均0/128失败。

confirm4两张map已完成；map2辐射残差`3.1109125699e-5`、边界L1`9.2831379412e-5`、bolometric`6.5141527282e-5`。18:38快照时previous反馈76块完成、final刚开始；18:41仍欠最后反馈。此快照不能提前宣布确认通过。作业内条件转换已实现，无须重新提交或手动启动第三步。

## 只读审阅器改进与保全

新增`operations/review_confirmation_stage.py`，保留逐文件manifest、全门、四组合、气体域、456map/912process资源审阅，并加入source trial SHA、协议trial SHA和trial内base_residual与正式分母逐位比较。绘图基准从本批`source-gate-replay.json`读取，不再写死74751对应的首次接受数值；图标题由参数指定。旧审阅器及已冻结作业源码未改。

先在74751历史完整包回归：2691文件、456map、912process均核验通过，与原审阅一致；输出在`outputs/review-20260921/generic-confirmation-review-regression.json/png`。这是已完成工件的读取/核验，不重求物质响应或辐射映射。

本次改前备份：`outputs/review-20260921/pre-74795-phaseA-review.bundle`和`automation-before-74795-phaseA-review.toml`。第一确认组已有学校自动包`confirmation/archives/confirm2-complete-1789986540411617812.tar.gz`（140140931字节，SHA256 `0c91a6acd3f0f34bad1df2eba7bc0e644d835f01b92f0434a7ce785d59196784`）；待完整确认包落地后直接取完整包，避免重复下载中间包。旧74760/74751已核包保持不动。

## 18:42实际完成并自动进入第三步

确认6map/3pair全部完成，无active/pending，`precision_confirmation_passed=true`。两组原16门与各自新控制四组合三范数均通过。confirm4原子加热`1.569309606312945e-4`、噪声/信号`0.021604578057771558`；L2/质量加权/最差单元比为`0.9813819070822378 / 0.9688403651302023 / 0.9940410459149804`。最差单元比仍略升，未越门。

confirm4两端最小气体热能`8.790481203566703e12 / 8.776141650366602e12 erg/g`；控制及两组确认共六个端点全部0/128失败。456份map报告强度有限非负/native峰3501.14453125MiB；912份进程收据全过/proc峰4039660KiB，stderr为空。

同态相对第二步首次接受的残差漂移，confirm2/confirm4分别为：L2 `0.05226245 / 0.08579155`、质量加权`0.00327510 / 0.00545632`、最差单元`0.01353010 / 0.02250277`。这些是向量差范数，不是误差界，不是新外层步。已接受物质步数量仍为2。

18:42:13顶层已实际变为`next_step`，并已有持久化`transition.json`：确认报告SHA `2aa1ec9519931e2aa789f1292591d78b8e32cc3cbeb279bbf64fe86a0bbc1dc4`、confirm4状态SHA `457674f018ffd1b2e517ee2f72ad33791d617dc33d9819347b31e6ffee69960d`、摘要SHA `f22d1924e7a1890f4be9acb06045b14441fc061ceab96890b8bfd2cde5c1ee20`，index3、physical_time_advanced=false。没有人工重交或等待heartbeat启动下一阶段。

18:43:04第三步`source-gate-replay.json`已落地：真实响应与确认4保存残差逐位相同，9派生门重算全true。新的$R_2$范数为L2`14.964594827177155`、质量加权`0.570058277341267`、最差单元`3.4369149496023157`。这与首次接受时的向量不同是同态精度确认的有限漂移，不是改变物理时间。该新向量将作为第三步方向和正式分母，原历史分母不改写。

最终确认包：学校`outputs/hpc/confirm2-then-step3-20260921/confirmation/archives/complete-1789987299295073583.tar.gz`，171221002字节，SHA256 `dd3cba73589a25b71ba323ad01aba05bebabec8de57ccf08e92705e6d11b9076`。Mac `outputs/review-20260921/74795-confirmation-complete.tar.gz`及`74795-confirmation-received/`，整包及2695份manifest文件大小/SHA全核，trial来源SHA/正式分母一致。实际新包与74751旧包两次端到端审阅均成功。

Git小证据：`handoff/evidence/20260921-74795-confirmation.json/png`，图已目视检查，无裁切，明确不是收敛柱。转换记录副本在Mac `outputs/review-20260921/74795-transition.json`。原大态未传未改。

POST-RUN：第二步同态确认通过，实际自动阶段衔接与第三步来源重放均成立，无物理域/有限性/资源异常。第三步尚在执行，不提前增加接受步数或宣布耦合柱完成。仍维持24map/8pair总预算及原停止条件。
