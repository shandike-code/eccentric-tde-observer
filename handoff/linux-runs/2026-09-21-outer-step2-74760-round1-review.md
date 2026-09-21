# 74760第二个物质步：第一对反馈14/16门通过，按原预算继续

2026-09-21 17:34至17:39 CST现场审阅，SSH正常，74760仍在anode17使用32CPU/128GiB。控制2张及1对反馈已完成并通过控制准入；候选full已自动完成第一轮反馈，并继续后四张映射。没有重新提交、改阈值或增加18map/5pair总预算。

## 该轮结果与决策

第一对实际评价的是full map3、map4的输入辐射态，两者有连续SHA链。原16门通过14门；失败仅为：

- `two_inner_radiation_residuals_pass`：map3为`1.119660375538122e-4`，高于原`1e-4`；map4为`9.033458310213668e-5`，已低于门。两个端点必须一起过，不能只挑较新的端点。
- `inner_noise_resolved_pass`：噪声/试步信号为`0.12922785589582342`，高于`0.1`。

三项加热变化均约`9.6011102323e-4`，低于`1e-3`但余量较小；率、边界、全频正式反馈、物质域、有限性和三个物质残差收缩门均通过。这证明有限精度下候选残差下降，尚不足以接受该步。第一轮正式判决仍为`accepted=false`。

|范数|新冻结基态|候选最终反馈|候选/新冻结基态|候选final/新控制final|
|---|---:|---:|---:|---:|
|L2|15.2484926808|15.0440381983|0.9865918234|0.9865579978|
|质量加权|0.5883923687|0.5757168479|0.9784573671|0.9788046572|
|最差单元|3.4575181415|3.4361013374|0.9938057291|0.9936907857|

上述范数来自原log/simplex编码残差，无能量单位，不能当成总能量或剩余热能。candidate previous/final对新控制previous/final的全部四组合三范数都小于1；这排除了“只相对最初旧基态下降”的误读，但不构成严格内层误差界。

两候选端点均0/128非正气体热能单元；最小气体热能分别`8.9370315474e12`和`8.9247356211e12 erg/g`。控制两端亦全部正。

决策：继续已经预声明的full后四张map，在map7/8结算第二对反馈。17:38:49时已完成候选map7，第8张76块均已产出日志，尚不能用日志替代原子提交后的state。若full接受则归档停；未接受则原驱动自动进入预声明half。程序/资源故障按原守卫停，不因期待通过而隐藏故障。

## 独立检查了哪些内容

新只读审阅器`operations/review_outer_step_snapshot.py`读取归档快照，核包内每文件SHA、反馈protocol/summary/round记录、76块partial来源、连续端点SHA与历史行。核新协议`base_residual`和`outer_base_material`与声明一致，trial的base/direction/encoded位移定义逐位正确；物理旧时间层来源、dt/phase/density未变。新冻结基态分母确实已实际用于本轮，不只是配置上写了一个字段。

从保存的候选残差向量和原cell mass重新计算三个范数，重现正式三个比值（相对容差`1e-12`，只用于跨平台复核，不更改接受门）。没有在Mac重新求解反馈或物质响应；`physical_response_replayed=false`明确记录此范围。下一阶段若用该端点作为新来源，仍须allocation内真实响应重放。

456份control/full映射报告有限、强度非负，原生RSS最大3499.53515625MiB；760份映射/反馈中继收据均退出0且通过独立6GiB门，观测最大4036428KiB。运行stderr为0字节。新审阅PNG已目视核验，明确标记NOT ACCEPTED，无裁切或误标收敛。

## 保全

- 学校包：`outputs/hpc/outer-step2-20260921/archives/full-round1-1789982909102806418.tar.gz`。
- 大小109668163字节，SHA256 `17393cdbfaaf67c0b08dfdc54dc9c40a3e1048139551afe9205632ff7c338274`。
- Mac：`outputs/review-20260921/outer-step2-74760-round1.tar.gz`与`outer-step2-74760-round1-received/`，整包及2052份manifest文件全核通过。
- Git小证据：`handoff/evidence/20260921-outer-step2-74760-round1.json/png`。
- 改前Git与定时任务备份：`outputs/review-20260921/pre-74760-round1-review.bundle`及`automation-before-74760-round1-review.toml`。
- 复核命令：`.venv/bin/python operations/review_outer_step_snapshot.py --received outputs/review-20260921/outer-step2-74760-round1-received --source-run outputs/hpc/outer-step2-20260921 --round 1 --output handoff/evidence/20260921-outer-step2-74760-round1`。

POST-RUN：本次只读审核成功，字节、归属、范数、资源及气体物理域相互一致。第一轮未接受原因是两项内层精度门，不能解释成方向无效，也不能提前宣布第二轮必过。尚只有此前一个正式接受物质步，耦合柱及整盘强度仍未完成。
