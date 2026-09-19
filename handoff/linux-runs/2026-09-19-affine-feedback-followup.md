# 真实外推映射验证完成，转入有界反馈比较

## 已核实结果

73435、73436均已退出队列，`validation_status.json`为complete，各完成一张真实原算子map，四项验证门全过，stderr为空。`state.json`仍写radiation是单map预算结束后的状态，不能据此说作业仍在运行。旧job已不在scontrol缓存，sacct未返回记录；完成证据来自完整的运行结果及无活动map状态。

| 历史 / job | 原残差 | 新实际残差 | 边界L1 | 总能流变化 | map墙钟 | worker峰值MiB |
|---|---:|---:|---:|---:|---:|---:|
| base / 73435 | 2.11212029e-4 | 1.2217637159185642e-4 | 1.37744879e-4 | 3.43204826e-5 | 132.42s | 3500.44 |
| old / 73436 | 3.14358496e-4 | 2.4115754152100052e-4 | 2.32552570e-5 | 2.32262176e-5 | 866.15s | 3501.11 |

实际减预测残差分别为-1.90e-16和-5.90e-15。候选最小强度为0；完整映射聚合已核频率所有权、非负和有限量。实际残差改善成立，但两条均未达到严格1e-4。本轮没有新反馈或物质接受，标量吻合不证明全场算子仿射。旧两历史加热差0.660889与55个失败层的结果不能直接套用到新外推态。

完整小包`affine-validation-73435-73436-small.tar.gz`：311407 bytes，186文件，SHA256 `78817dac772545f5e42f2b6f75db3c4df266d8ab579cf296cbee46273cc43f38`。学校家目录与Mac `outputs/review-20260919/`均保留；Mac核整包及全部文件SHA，解包目录为`affine-validation-73435-73436-received/`。排除dat、lock和partial，原大态全部保留。两个validation_result的原值另存`handoff/evidence/20260919-affine-{base,old}-validation.json`。

## 下一轮设计与边界

新增`operations/prepare_affine_feedback_precision.py`与`affine_feedback_precision.sbatch`，不修改任何已钉住的旧代码。每条验证链的最新真实映射输出分别作为新种子：

- base：`affine-base-map-validation-20260919/state_1.dat`，SHA256 `9ddbfebb466aab9da406b6fce87e389c2196df448058a180137af29b66307996`。
- old：`affine-old-map-validation-20260919/state_1.dat`，SHA256 `1ffa7f25edc1fde49ed30bd89f8c65566a457b50fba592631690fc6634b2dcaa`。

各新目录最多2张新map，每2张执行一轮正式反馈与能量账本，墙钟90min、USR1提前300s，无自动续交。不拼接旧history；反馈消费新run中两个连续映射的输入态，每个都有对应的真实后继及残差。两条候选全部物质字段保持一致，alpha=0.00390625；物理时间步、网格、率与能量定义不变。严格1e-4，2.5e-4只作比较。初始化前复制trial并核全字段、native消费，防止默认迁移替换候选。

计划base用cpu_long32CPU/128GiB、16worker，old用默认4CPU/16GiB、2worker。固定`NUMPY_MADVISE_HUGEPAGE=0`，只改本作业环境，不改节点全局。两条原run保持停止和不变。准备脚本拒绝既有目录；若超时，只可审计后恢复已有执行阶段，不可盲重跑准备。

Mac20项相关测试通过：真实输出选择、不修改来源history、未完成/半态/待反馈/错槽/错SHA/旧摘要/错误候选拒绝，以及已有全物质身份与外推非负有限性测试。shell语法与git whitespace检查通过。变更前Git备份`outputs/review-20260919/pre-affine-feedback-4330b45.bundle`。

## 本轮结束后的决策要求

先备份并双端核小工件，再核输入SHA、native物质、正式反馈血缘、所有门。既比较相邻两个端点，也比较两种历史的完整反馈向量；同时给加热、率分量、目标正热能、方程L2/质量加权/最差层和encoded正式接受指标，不能只挑残差变小。

如果反馈仍强烈依赖辐射历史，不接受物质步；根据测得的慢模和反馈敏感性制定下一项有限诊断，不机械追加map。若完整正式门通过，才讨论一个非线性物质步的接受；这仍远小于代表柱收敛及完整定义域角分辨强度表。当前没有依据承诺整盘自洽光谱日期，也没有证据证明模型无解。
