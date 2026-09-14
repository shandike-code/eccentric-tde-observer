# Phase 7B9f：正式 H/He 反馈与基准物质残差

上游：[[phase7b9e_science_functional_continuation|Phase 7B9e--7B9e2 科学泛函续算]]

## 从辐射态到物质残差

最后两个辐射态分别重新执行 76 个频率块的正式共动 H/He 率、直接源加热和逆变换实验室
系四力装配。频率所有权逐组恰好一次，两个状态各用两个并发短寿命进程完成。`[V]`

对固定物质态 $\boldsymbol{u}$，完整物理时间层响应记为
$\boldsymbol{u}_{\rm target}(J[\boldsymbol{u}])$。在保持正热能及 H/He simplex 的编码
$\mathcal{C}$ 中，基准残差定义为

$$
\boldsymbol{R}_{\rm N}(\boldsymbol{u})
=
\mathcal{C}\!\left(\boldsymbol{u}_{\rm target}\right)
-
\mathcal{C}\!\left(\boldsymbol{u}\right).
$$

这个定义使用完整相位步长，没有通过缩短物理时间来减小残差。`[V]`

![Phase 7B9f converged feedback and residual](../outputs/phase7b9f_converged_feedback_residual.png)

图 (a) 是最终 H I、He I、He II 光致电离率随表面质量坐标的分布；图 (b) 中原子率加热、
直接共动源和逆四力三条曲线重合，验证源项装配而不是重新归一化；图 (c) 显示基准残差主要
由表层热分量控制，$L_{2}$ 范数为 $15.5889$，说明耦合物质态远未收敛；图 (d) 给出最后
两态的反馈变化与禁止的数值修补。`[V]`

最后两态的最大光致电离率 $L_{1}$ 变化为 $2.59189\times10^{-5}$，总复合率为
$3.38678\times10^{-7}$，三种加热比较均为 $4.81721\times10^{-4}$，全部低于
$10^{-3}$。最终原子率/直接加热的体积 $L_{1}$ 差为 $1.97675\times10^{-12}$，原子率/
正式四力差为 $8.05002\times10^{-6}$。`[V]`

## 决策

可恢复基准残差状态机状态为 `complete`，因此“合法基点残差存在”已经验证。残差很大并不
等同于辐射内迭代失败；它表示外层物质--辐射耦合仍需非线性求解。本阶段未计算 $Jv$、
未迈 Newton 步，也未得到动态 NLTE 输出谱。`[V/O]`

