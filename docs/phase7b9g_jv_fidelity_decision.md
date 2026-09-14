# Phase 7B9g：严格全频 $Jv$ 保真度决策

上游：[[phase7b9f_converged_feedback_residual|Phase 7B9f 基准物质残差]]

## 为什么不直接做有限差分 $Jv$

矩阵自由有限差分需要

$$
J\boldsymbol{v}
\simeq
\frac{\boldsymbol{R}(\boldsymbol{u}+\epsilon\boldsymbol{v})
-\boldsymbol{R}(\boldsymbol{u})}{\epsilon}.
$$

若两个“内收敛”辐射残差之间的剩余变化大于分子中的真实差分信号，所得方向主要测到内层
噪声而不是 Jacobian。本阶段因此先比较信号可辨识度，不运行昂贵的伪 $Jv$。`[V]`

最后两个基准辐射态产生的编码残差相差 $3.27416\times10^{-2}$。7B9a 冻结的相对步长
$10^{-7}$ 对应编码态位移 $5.00058\times10^{-5}$；用唯一真实割线的增益估计，期望差分
信号只有 $1.11564\times10^{-4}$。实测内层变化/估计信号比为 $293.48$，故信号不可
辨识。即使用理想逆方向作诊断，该比值也为 $650.56$。`[A-diagnostic/V]`

![Phase 7B9g Jv fidelity decision](../outputs/phase7b9g_jv_fidelity_decision.png)

图 (a) 回顾基准辐射收敛；图 (b) 直接比较内层剩余变化和割线尺度差分信号；图 (c) 是
保持最近收缩率不变的资源敏感性，不是收敛定理：把噪声/信号降到 $1$、$0.1$、$0.01$
分别约需额外 29、41、52 次全频映射，即约 3.74、5.29、6.71 小时；图 (d) 冻结决策。
`[A-resource-projection/V]`

## 决策

当前保真度下严格全频 $Jv$ 被拒绝且没有执行。低秩方向与旧方向余弦为 $0.999406$，其
保持物理域的最大离散松弛为 $0.125$；因此只授权一次有限、受保护的准 Newton 真残差
试探。该试探不能称为 $Jv$，也不能因候选仍在物理域就接受。`[V/O]`

