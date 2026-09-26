# 77927复核：渐消方向未通过，先分解失败机制

77927于2026-09-26 23:50:16 COMPLETED0，墙钟27:15，2map/0反馈/0新接受，true_map_not_validated；stderr零字节。完整包complete-1790437815275524374.tar.gz2350737bytes，SHAd7dff1fcbfdfcc02ce6a169ecf7c77b998119bbc9c4e27ad26b119d5e8817a41。

新审计review_step21_tapered_joint.py真实端到端通过，325文件705代码声明152worker回执，峰3586492KiB，父进程1150435328bytes。Mac独立301分片fsum、76块最大值与边界归约、来源与trial/半步身份核对；不冒称Mac重算大场或原算子。图峰位置已核验。

full L2比0.8227658651867918（改善17.7234%）、half0.829365749082181；full/half Linf比3.19677453650255/1.7824643457141254。半步仿射误差/原L2=1.0430910691468959e-10。失败正是full 20%L2成本、full/half Linf三门；严格rad、边界、半步门过。最大缺陷在所选核心block25的group3264分片，3.4406493353705825e-7；不是上一轮外侧block50。渐消减弱了外侧问题，但仍有核心内放大，不支持简单以更软边界继续猜权重。

POST-RUN：所有数值归约有限；残差尺度与原M1.0762877694636686e-7一致；无物理域裁剪，原频率尾完整保留。仅两map，失败后控制流没有反馈。仍20物质接受，第21未接受，无模型无解结论。

下一任务operations/diagnose_step21_taper_commutator.py/.sbatch，协议step21-taper-commutator-v1.md：读取77577原x/y、77843 q/v、77927 z/Tz六场。一遍统计a=Tz-z、p=(1-w)(y-x)+w(v-q)、c=a-p，按全域/核心/核外分解平方范数与交叉项，保存最大点有符号账本，逐点检查候选公式。c是代数差额，只有精确仿射模型才严格解释成算子交换子，不忽略浮点或非仿射。

默认4CPU16GiB、1h，0新map/反馈/候选/物质接受。先取得机制证据，再定下一算法；不凭一次taper失败改门或放弃物理模型。备份pre-taper-review.bundle。学校只读CLI监督由新taper-commutator模式解释，避免套用旧步长筛选门。
