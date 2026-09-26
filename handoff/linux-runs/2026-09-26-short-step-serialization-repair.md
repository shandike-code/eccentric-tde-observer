# 77747结果序列化故障与v2修复

77747在17:35:12–17:39:58运行4分46秒，FAILED1:0。不是资源故障或科学门拒绝。
完整扫描返回后、输入/代码SHA后验通过后，在写prediction.json时抛出
TypeError: Object of type int64 is not JSON serializable。
根因是np.unravel_index产生的NumPy整数放入witness.index，旧测试未覆盖含限制点的完整结果序列化。
本缺陷由Codex新增扫描器引入；此前23测试通过不足以覆盖真实输出契约。

归档failed-1790415598602110767.tar.gz，93727字节，SHA90eaeec5170d381fee0e9d16d17f6cb3a6a722eb2b666b29a1ff828a95318552。
Mac核2清单文件、695代码声明，状态错误和FAILED1:0终态一致，未有prediction.json。
包内只保存声明与失败状态，不能填入任何未持久化的步长/上界数值。
stderr另存outputs/review-20260925/block-short-step-77747.stderr.txt，失败包解到block-short-step-77747-failed-received。
审计摘要handoff/evidence/20260926-short-step-serialization-failure-review.json。

## 修复与范围

保留旧源码、测试、协议、运行目录字节；新scan_step21_block_short_step_v2.py只将三个索引int64转Python int。
其余差异仅声明的新sbatch/测试/协议路径；用源码差异回归断言这一范围。
新目录outputs/hpc/step21-block-short-step-v2-20260926，4CPU16GiB，1小时，最多3遍只读扫描，零新map/反馈/大候选/接受。
仍使用77701相同已存源，所有正性/最大范数/边界/物理时间/原r20门不改。

Mac新增回归重现旧witness序列化TypeError，覆盖零上界、正上界、无最限制点的完整结果JSON往返，
28项合并测试通过（0.81s），Python编译/sbatch语法通过。学校同组通过后才提交。
备份Mac pre-short-step-serialization-repair.bundle、automation-before-short-step-repair.toml在review目录。

[PRE-RUN CHECK]

Code: PASS — 显式整数类型转换；复现故障且检查完整输出JSON契约，源码差异范围受测。
Logic: PASS — 未保存结果不能原地补写，另开新目录重算同一有界只读任务；旧现场保全。
Physics: PASS — 无物理公式/门/时间步/物质态变更。

Key Issues:
1. 该失败没有科学判决。
2. 新旧版本并存，历史哈希保持可核。
3. 仍须新结果独立审计；预测可行不等真实映射过门。

Decision: RUN — 学校回归通过后提交一次明确修复的v2，不是监督器盲重试。
