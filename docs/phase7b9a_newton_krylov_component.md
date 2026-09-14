# Phase 7B9a：物理域矩阵自由 Newton--Krylov 组件门

上游：[[phase7b8f_backtracked_feedback|Phase 7B8f 回溯三重真残差失败]]

## 为什么不能继续扫描步长

Phase 7B8 已证明，质量加权残差可以显著下降，而表层局域残差仍会增大。逐单元割线和端点
仿射回溯都不能表示辐射在不同深度之间的非局域响应。Phase 7B9a 因而不再生成新的全频
候选，而是先验证一个能同时闭合温度、H/He 布居并允许非局域 Jacobian--向量积的求解器
组件。`[V/O]`

## 物理域编码

每个深度单元使用四个无约束变量：

$$
\boldsymbol{u}_{k}
=
\left(
\ln e_{{\rm th},k},
\ln\frac{x_{{\rm H\,II},k}}{x_{{\rm H\,I},k}},
\ln\frac{x_{{\rm He\,II},k}}{x_{{\rm He\,I},k}},
\ln\frac{x_{{\rm He\,III},k}}{x_{{\rm He\,I},k}}
\right).
$$

其中 $e_{{\rm th},k}$ 是扣除 H/He 基态电离能后的正热比能。H 使用稳定 logistic 反演，
He 使用三态 softmax 反演，因此正温度和两个 simplex 由参数化本身保证。softmax 是未知量
坐标，不是求解后的事后重归一化。任何严格为零的布居都直接拒绝，不加入 population floor。
`[A/V]`

对物质响应算子 $\mathcal{P}$，四分量固定点残差定义为

$$
\boldsymbol{R}(\boldsymbol{u})
=
{\rm encode}\!\left[
\mathcal{P}\!\left({\rm decode}(\boldsymbol{u})\right)
\right]
-\boldsymbol{u}.
$$

本阶段实际 128 单元控制冻结 Phase 7B7j 的辐射反馈，因此只验证物质响应与非线性求解器，
不冒充新的耦合解。`[V/O]`

## 矩阵自由线性化与全局化

Jacobian--向量积使用前向差分：

$$
\boldsymbol{J}(\boldsymbol{u})\boldsymbol{v}
\simeq
\frac{
\boldsymbol{R}(\boldsymbol{u}+\epsilon\boldsymbol{v})
-\boldsymbol{R}(\boldsymbol{u})
}{\epsilon}.
$$

线性子问题由 GMRES 求解；候选步必须同时通过实际残差 Armijo 回溯与温度、物质比能、
布居变化信赖域。失败候选被拒绝，不做逐点裁剪、floor 或事后重归一化。`[A/V]`

## 数值结果

| 量 | 结果 | 判定 |
|---|---:|---|
| 编码未知量 | $512$ | $128\times4$ |
| 最大温度往返误差 | $1.935\times10^{-15}$ | 通过 |
| 最大布居往返误差 | $3.331\times10^{-16}$ | 通过 |
| 最大物质能往返误差 | $9.191\times10^{-16}$ | 通过 |
| 实际冻结反馈 Newton 迭代 | $15$ | 收敛 |
| 实际冻结反馈 GMRES 迭代 | $15$ | 收敛 |
| 实际冻结反馈 $Jv$ 次数 | $30$ | 组件成本 |
| 最终编码残差范数 | $3.024\times10^{-11}$ | $<10^{-9}$ |
| 最小接受松弛 | $0.0625$ | 严格为正 |
| 制造非局域系统末残差 | $7.378\times10^{-10}$ | $<10^{-9}$ |
| 制造系统最大状态误差 | $9.597\times10^{-11}$ | $<10^{-8}$ |

Phase 7B8f 的完整固定时间层候选在至少一个单元留下小于电离能的总物质比能，因而没有正
热能。该候选继续以 `PhysicalDomainError` 被拒绝；7B9a 没有用温度 floor 修补它。`[V]`

![Phase 7B9a Newton--Krylov component gate](../outputs/phase7b9a_newton_krylov_component.png)

图 (a) 显示实际 128 单元的四类编码残差，证明物质固定点不只是单一能量标量。图 (b)
给出冻结反馈 Newton 历史和为满足信赖域发生的回溯；图 (c) 用含跨分量非局域耦合的制造
系统验证矩阵自由路径；图 (d) 明确本阶段没有运行新的全频残差，也没有宣称动态 NLTE 解。
`[V/O]`

## 成本与决策

由 Phase 7B8e 映射和 7B8f 正式反馈测得，一次“全频映射加正式反馈”的方向性评估约需
$682.70\,\mathrm{s}$。若直接照搬组件控制中的 30 次 $Jv$，仅方向性一映射下界就约为
$5.69\,\mathrm{h}$；真正把辐射消去后，每个物质扰动态还要先把辐射内迭代收敛，成本会
更高。这个乘法成本说明下一步必须先建立可恢复残差接口和预条件准入门，而不是立即盲跑
完整 $Jv$。`[V/O]`

7B9a 只授权[[phase7b9b_recoverable_full_frequency_residual|Phase 7B9b 可恢复全频残差接口]]。
它不授权全轨道、Phase 4 替换、UVOT、真实线形成或动态 NLTE 结论。`[V/O]`
