# 74127真实映射验证通过；推进两map和一对正式反馈

## 已验证的范围

74127完成一张原算子map，六项验证全部通过，`validation_status=complete`，没有active/pending。32CPU/128GiB、16worker；代码1705cd6，随后追加提交记录5ce03c6。候选SHA `273e710640bc6992617cfe99d951f92bbda26b50516ff0d5133d5527766baadb`；真实输出state1 SHA `0d6bb32deebe74e0b94e0f479b08c8ba91d5a51466abaf6d2a48ceb19fc24e19`，每态10,099,884,032 bytes。

实际最大归一化辐射残差2.442668537015916e-5，预测值2.442668537069619e-5；实际boundary L1=3.742192341752979e-5，bol=3.1778905118195284e-5。map墙钟150.1453403858468秒，worker峰值3500.921875MiB。这不是含所有历史数据哈希、初始化和全场验证的完整作业墙钟。

全场真实输出−预测输出L2=1.3151006029739046e-12，relative field L2=3.1224622201116036e-15，最大误差/场尺度=2.3991130779972345e-14；误差/实际映射缺陷L2=3.360395057334232e-10，远低于原1%上限。候选逐位重构一致，未剪裁。说明这一个有界组合的仿射预测被实际算子证实，不能推广成所有状态下算子仿射、固定点唯一或物质响应已收敛。

76块覆盖9632频组、无重叠缺口，block输入SHA与候选一致、同一协议、统计值有限、输入/输出最小值非负。trial SHA保持`07a3700d8767f5bd7addf7b2932d3b44742e803e2aed52c83e2e86b82ce07b86`，初始化后native mirrored material和phase/dt逐位检查通过。stderr空，无本轮绘图。复核时scontrol已无作业记录，不能编造调度退出码、完整墙钟和MaxRSS。

## 新反馈任务

新增`operations/prepare_half_four_map_feedback.py`和`operations/half_four_map_feedback.sbatch`。旧入口和旧run不修改。新run计划为`outputs/hpc/half-four-map-feedback-20260920`，32CPU/128GiB、16worker、上限60分钟，最多2张新map、每2张结算1对反馈，总计1对。调用冻结的`diagnostics/interval_diagnostic.py --maps-per-job 2 --feedback-every 2`。

只允许上述真实输出state1作为新种子，不能使用候选输入或仿射预测。源state/status/result/declaration四份JSON均固定为已核备份SHA。新的`validated_four_map_seed`要求完整六门、候选逐位重构实际证据、数值误差/资源/残差门、源码声明的单map/单候选/无clip范围，以及当前slot确实是最后实际输出。返回seed时不修改历史。

物质保持alpha=0.001953125、phase1367、dt889.419892762322秒及同一冻结base/direction，trial初始化前复制并全字段比对，初始化后再核trial/seed/空history/native。新种子必须重新求自己的map残差，原16项反馈和物质门全部不变。两态正热能或低辐射残差不能代替L2/质量/最差单元三项物质收缩。

Mac96项相关测试通过，包括新的六门/范围/重构检查、旧初始化验证和interval driver恢复/归档/信号测试。真实74127小工件通过新seed入口，确认得到state1而非state0。学校端同组测试及真实工件核验通过后才提交；此报告写入时未提交新作业。

## 保全

`half-four-map-validation-74127-small.tar.gz`学校家目录与Mac `outputs/review-20260920/`双端，19,949,100 bytes、738文件，SHA256 `9a43f7524771601a9d7099b7d79b3df33b352bfd9c881e87c8af9aad85411bfb`，整包和全部文件已核；Mac解包`half-four-map-validation-74127-received`。Git保存validation_result/state。旧dat不删除。

改前Git备份`outputs/review-20260920/pre-four-map-feedback.bundle`，自动任务配置备份`automation-before-four-map-feedback.toml`。后续若反馈通过仍只接受一个有限物质步；若仍失败，按实际门和完整向量决定，不自动续图或放宽门。
