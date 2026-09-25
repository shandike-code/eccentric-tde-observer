# 77126：control稳定，thermal物质候选仍被拒绝

## 独立审计范围

Mac对`thermal-feedback-1790325934048091837.tar.gz`核验2950文件、684项代码哈希声明、304条反馈进程回执和532条map回执。
归档含control3张、thermal3张、population1张map；仅control/thermal有完整反馈对，不冒充最终六端点齐备。
文件153,088,442字节，SHA256 `8b78de9f122aa3466771035f195ea4d608c02570acf27f53cd879a2cb697e360`。
Mac目录`outputs/review-20260925/step21-positive-validation-77126-thermal-feedback-received`。

`handoff/audit_tools/review_step21_positive_plane_feedback.py`无需修改即支持这一部分反馈归档路径；真实端到端通过。
逐项核验原trial/$x_{20}$/$r_{20}$/旧物理时间层、四态/有效系数、反馈块数组及替换项、9632组唯一归属、
4096→256→128归层、能量恒等式、四分量响应、trust region、原门和同期control四种端点组合。
Mac未重新积分物质ODE或大型辐射场；解码仍用既定跨CPU8eps尺度，其他身份与科学门未放宽。
证据`handoff/evidence/20260925-positive-validation-thermal-feedback-review.json/png`，图已查看。

## 判决

control零位移控制7门全部通过，两个端点物理响应有效，满足本协议的控制稳定条件。
它不是非零16门候选；审计字段`all_16_pair_gates=False`在control上是分类结果，不是控制失败。

thermal原16门通过14项，失败仍为质量加权和最差单元收缩门：

| 指标 | thermal结果 | 原门 |
|---|---:|---:|
| 对原$r_{20}$的L2范数比 | 0.9976885430825692 | 小于1 |
| 对原$r_{20}$的质量加权范数比 | 1.0069708627632765 | 小于1，失败 |
| 对原$r_{20}$的最大单元范数比 | 1.0032371883703342 | 小于1，失败 |
| 同期control四组合最坏最大单元比 | 1.002955822555633 | 小于1，失败 |
| atomic加热相邻变化 | 0.00015193713507213844 | 小于0.001 |
| 内层噪声/试探信号L2比 | 0.0110448329262857 | 小于0.1 |

thermal最终残差范数为8.15311731680174 / 0.26373616207527883 / 2.713757714768263。
control最终范数为8.22040520154392 / 0.2661139626632066 / 2.705760594942855。
四个反馈端点最小气体热能均为正，最低约7.02e12 erg/g，没有物理域失败。
thermal必须保持拒绝；辐射预测通过、加热与噪声门通过，都不能替代全部物质范数下降。

## 漂移的含义

当前control响应与原$r_{20}$的向量差L2为0.5271576467146694，相邻control差为0.005617021305032154。
76957至当前同物质响应的变化L2，control为0.041431071081119764，thermal为0.055299378635572854。
这些是已观察到的迭代跨度，不是相对于精确解的严格误差上界，也不是发散或无解证明。
物理时间步和旧层始终固定；这里不是物理时间演化。同期control提供相近辐射求解阶段的比较，不能保证完全消除内层偏差。
原$r_{20}$比较与同期control比较同时保留，不改分母使候选过门。

## 现场与下一步

16:52:34快照：77126 RUNNING 2:03:06、32CPU/anode04，三case各3张map、active_map均None；
control/thermal反馈各有76+76块JSON且完整决策已经审计，population反馈尚未开始出块。
root状态precision_maps/population仍可能覆盖后续retention/协议准备，不仅凭该字符串判断计算是否停滞。
stderr0、watcher存活。快照`handoff/evidence/20260925-positive-thermal-feedback-audit-snapshot.json`。

维持原批次完成population反馈，不重复跑thermal、不扩大预算、不提前宣称population失败。
最后一对反馈及Slurm终态完成后，再审完整归档并决定下一有界路线。接受步数20，没有promotion。

## 前后检查与备份

PRE-RUN：只审已完成两对反馈；来源/公式/单位/物理旧层一致；保持全范数和两种基准比较。RUN。
POST-RUN：无审计warning/NaN/Inf/域或资源异常，最大进程4040836KiB低于6GiB；频率覆盖、能量与原门一致，图已核。
本轮不修改活跃数值代码、协议或测试。Claude草稿中的“同期control排时间漂移干扰”已纠正为固定物理时间下的数值比较，不作偏差消除保证。
Mac备份`outputs/review-20260925/pre-positive-thermal-feedback-audit.bundle`及`automation-before-positive-thermal-feedback-audit.toml`；
学校`/home/scc/pb24511938/pre-positive-thermal-feedback-audit.bundle`，历史工件/dat不变。
