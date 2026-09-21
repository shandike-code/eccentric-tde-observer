# 74751精度确认完成；第二个物质步的有界批次

## 已完成且实际核验的结果

74751在anode17使用32CPU/128GiB，16:05:37至16:43:55运行38分18秒，调度终态`COMPLETED`、`ExitCode=0:0`，stderr为空。该批6张map、3对反馈完成，无active map或待结算反馈。它只验证同一个已接受物质态，不计作三个外层步。

|量|74671首次接受|74751追加2张|74751累计追加4张|
|---|---:|---:|---:|
|原子加热变化，门0.001|0.0005477903|0.0003353772|0.0002475914|
|内层噪声/试步信号，门0.1|0.05347376|0.03685588|0.02540643|
|L2/原基态|0.97935634|0.97848046|0.97816577|
|质量加权/原基态|0.95930991|0.95730788|0.95629317|
|最差单元/原基态|0.99435791|0.99451828|0.99465787|

两组全部原16门及两组各自对新控制previous/final的四种组合三范数比较都通过。控制和两个确认组的全部六个反馈端点均为0/128非正气体热能单元。最差单元比值略升，不能写成“所有物质残差单调改善”。确认4最终端点最小气体热能为`9.183248083734715e12 erg/g`；电荷/粒子守恒残差约机器精度。

456份map原报告强度有限且非负；912份map/feedback中继进程收据均退出0且通过独立内存门。map原生峰值3498.6015625MiB，中继观测全体进程最大4038704KiB，均小于每worker6GiB守卫。

同一物质态相对首次接受端点的残差漂移：追加2张L2为0.06905、追加4张为0.11860。这是有限精度下的向量差，**不是误差界**。两组通过支持下一有限外层试验；不证明独立初值历史一致、耦合柱收敛、全盘强度可用。

## 双端备份与复现

- 学校原件：`outputs/hpc/accepted-confirmation-20260921/`，不修改。
- 完整小包：`archives/complete-1789980215711877094.tar.gz`，171102352字节，SHA256 `6c25267432e36fd4d8899450e4bf477c973c2c6d7f87ae7e818b4e098e63a4f4`。
- Mac：`outputs/review-20260921/confirmation-74751-complete.tar.gz`与`confirmation-74751-received/`，整包及2691份manifest文件大小/SHA全核通过。
- 调度原证据：`outputs/review-20260921/confirmation-74751-terminal.json`；stderr同目录`tde-accepted-confirm-74751.err`。
- Git小证据：`handoff/evidence/20260921-confirmation-74751.json`及同名PNG；新图已目视核验，无裁切，明确不是收敛柱。
- 重放审阅：`operations/review_precision_confirmation.py --received outputs/review-20260921/confirmation-74751-received --output handoff/evidence/20260921-confirmation-74751`。
- 改前备份：Mac `pre-74751-review-outer-step.bundle`和`automation-before-74751-review.toml`；学校`pre-second-outer-step-school.bundle`，均在`outputs/review-20260921/`。

## 第二个外层步究竟改变什么

记已接受trial编码为$x_1$，确认4最后反馈重放的物质固定点残差为$R_1=G(x_1)-x_1$。新控制为$x_1$，两个候选为：

$$
x_{2,\alpha}=x_1+\alpha R_1,\qquad \alpha\in\{1/256,1/512\}.
$$

`target_material.npz`是响应目标$G(x_1)$，没有被接受为完整位移；不允许将它当作新基态。新基态取已经接受的trial字节，物理字段逐位保持。新残差来自原响应函数，必须与确认4存储残差逐位一致。

`operations/second_outer_step.py`新增显式基态适配。原`pipeline.feedback_protocol`把最初基态残差写死在模板中；新驱动保留该模板，输出另一份`rebased_feedback_template.json`，将`base_residual`换成声明中的$R_1$并增加基态来源。原诊断轮次构造器随后生成正确的正式`feedback_protocol.json`。新trial元数据中的`base_encoded_state/base_residual/finite_direction`必须分别等于$x_1/R_1/R_1$；正式协议与trial使用同一分母，不能继续拿最初$x_0$作后续接受分母。

这只更新非线性迭代基态。物理旧时间层、phase1367、dt889.419892762322秒、密度、原微物理和16门均不改变。对照新控制的四组合仍保留，原门与新控制比较分别报告。

## 同一allocation自动接续，不等心跳发下一张map

新run预定`outputs/hpc/outer-step2-20260921`，入口`operations/second_outer_step.sbatch`，32CPU/128GiB、16worker、墙钟上限4小时。预算最多18张map、5对反馈：

1. 重放确认4实际反馈与原判据，核全部来源、76块所有权、种子SHA；新基态与两个候选先落盘，原信赖域及native镜像逐字段通过才初始化。
2. 新基态控制2张map、1对反馈。辐射/边界及五反馈稳定性门和物质域通过才继续；零位移不能记为接受一步。
3. 全步候选最多8张，每4张结算1对反馈，共最多2对。每对保留原正式门、独立能量账本与新控制四组合。
4. 全步未被接受时自动进入预先声明的半步，亦最多8张/2对。某候选出现物质域拒绝，停止该候选，允许进入其已声明半步；若新基态本身不合法，整批停止。
5. 首个候选正式接受即停，归档审阅，不自动推进下一物理时间层或无限外层循环。程序/资源故障立即停止；账本不完整先恢复欠账本，不先跑map。USR1完成当前worker批次提交后停止派发。恢复不重置总预算，不自动重新提交Slurm。

源74751所有大态只读；新run独立槽位、协议和声明。保留原6GiB门及独立/proc门、标准库中继与`NUMPY_MADVISE_HUGEPAGE=0`。每阶段自动打小包及SHA manifest，不能为占满allocation补无关任务。

按近期成本，预计本批约1–2小时加排队；4小时是上限，不是完成预报。新物质态可能需要不同内层成本，实际状态优先。这仍不能据此给出最终整盘$I_{\nu}$日期。

## 启动前验证

Mac 64 passed、4项Linux专用skip：新基态/分母/方向/物理旧时间、篡改、恢复接口、正式轮次端到端路径、总预算、反馈优先、接受即停、原信号及内存守卫。Linux专用项须学校端通过后才提交。真实源重放作为allocation内第一阶段，失败不能开始map。提交信息随后追加，不预写虚构job ID。

POST-RUN：74751无NaN/Inf、无负强度、无正气体热能失败，所有原门/对照/资源证据一致。加热与噪声改善、最差单元比值略升均如实保留。一个接受物质步及同态精度确认成立，完整耦合柱与观测强度尚未成立。
