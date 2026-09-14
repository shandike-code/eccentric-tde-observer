# Phase 7 收敛后分支决策合同

关联：[[eccentric_tde_observer/docs/phase7b_periodic_column|Phase 7 周期柱]]、
[[eccentric_tde_observer/docs/phase4b_observer_atlas|Phase 4 观察者 atlas]]、
[[eccentric_tde_observer/docs/phase5a_observer_frame_flambda|Phase 5A 观察者坐标谱]]。

## 1. 当前定位

[V] 当前 $0.0625$ 固定物质候选只覆盖 $a=3.87457\times10^{14}\ {\mathrm{cm}}$、
$e=0.6$ 的一个轨道相位。即使正式 H/He feedback pair 通过，它也只接受一个非线性物质步，
不等于全盘耦合解，更不会自动授权 Phase 4 或 UVOT。

机器可读合同位于 outputs/phase7_post_convergence_branch_contract.json。它把三个科学分支写成
互斥判据，同时保留 not_ready 状态；缺失证据不会被误当成“静态近似失败”。合同生成不读取
.dat、不运行 Phase 4 atlas，也不选择分支。

## 2. 依赖链与判决顺序

正式依赖链为：固定 $0.0625$ 物质态的连续辐射对
$\rightarrow$ 正式 H/He feedback pair $\rightarrow$ 全径向/全轨道连续谱闭合
$\rightarrow$ Phase 4 local-intensity adapter $\rightarrow$ Phase 5A 观察者坐标谱
$\rightarrow$ Swift/UVOT 仪器与采样。

前两节点的既有预注册门保持不变：两次原算子残差均小于 $10^{-4}$，两个边界指标均小于
$10^{-3}$；feedback rate/heating 的相邻态 $L_{1}$ 差小于 $10^{-3}$，inner-noise/signal
小于 $0.1$，三个候选/基准物质残差范数比均小于 $1$。这些门只决定一个物质步是否接受，
不能替代后面的全定义域连续谱判据。

判决顺序如下：

1. [V] 先完成当前固定物质辐射收敛、连续两个合格辐射态和正式 H/He feedback pair。
2. [O] 再扩展到完整径向和轨道相位定义域，完成频率、角度、深度、能量及历史依赖检查。
   证据不全时状态只能是 not_ready。
3. [A-classification] 若任何静态有效性指标失败，进入周期动态 NLTE 柱。
4. 静态有效性全部通过后才比较新局域连续谱与当前 Phase 4 局域闭合。全部差异指标都小，
   进入 UVOT 仪器层和观测采样；任一指标不小，建立有限大气表并替换 Phase 4。

当前没有执行第 3--4 步，因此没有提前选择任何科学分支。

## 3. 静态有效性指标

[A-classification] 完整源定义域的物理静态根覆盖率必须为 $1$。最大准静态比必须满足

$$
\max\left(\frac{|{\rm d}\ln H/{\rm d}t|}{\sqrt{Q_{\mathrm{pressure}}}}\right)\leq0.1.
$$

最大热时间比必须满足

$$
\max\left(\frac{t_{\mathrm{th}}}{P_{\mathrm{orb}}}\right)\leq0.1.
$$

正向/反向或相邻周期得到的归一化历史回线差必须满足

$$
\max D_{\mathrm{hysteresis,L1}}\leq0.1.
$$

这些是分类门，不是文献定理。必须同时完成全定义域审计、频率--角度--深度收敛、表面能量
闭合和历史依赖测试。单次非线性步失败或单个求解器失败不能证明静态物理失败。

## 4. “差异小”的可计算定义

比较必须固定相同 corrected ZO 几何、观察者网格、频率域和积分规范。[A-classification]
只有下列条件全部成立，才走 UVOT 分支：

- bolometric flux 相对差不超过 $0.01$；
- 归一化谱形 $L_{1}$ 距离不超过 $0.1$；
- 任一预先固定的观测诊断带通量相对差不超过 $0.1$；
- ionizing photon rate 的差不超过 $0.1\ {\mathrm{dex}}$；
- $\nu F_{\nu}$ 峰能量比位于 $[1/1.25,1.25]$。

任一量越界即进入有限大气表分支。合同要求对谱形/带通阈值 $0.05,0.1,0.2$、ionizing
差 $0.05,0.1,0.3\ {\mathrm{dex}}$ 以及峰能量比 $1.1,1.25,2.0$ 做敏感性检查，避免只报告
一套恰好有利的阈值。Phase 7B4g 曾用谱形 $0.2$ 与峰能量比 $2$ 的联合“大差异”门；其模型
是固定密度、双真空面的控制柱，不能直接充当本合同的生产阈值。

## 5. 三条分支的实际依赖

### 5.1 UVOT 仪器层和观测采样

[V] Phase 5A 已有红移、距离、$F_{\nu}\leftrightarrow F_{\lambda}$ Jacobian 和前景消光。
[O] 尚缺 Swift/UVOT 有效面积、时变灵敏度、计数率、观测 cadence 与 upper-limit 接口。
进入该分支后先用冻结 provenance 的局域闭合重跑 Phase 4/5A，再实现并验证仪器层。

### 5.2 有限大气表并替换 Phase 4

[V] AngleResolvedAnnulusTable 已提供严格不外推的
$I_{\nu}(T_{\mathrm{eff}},m_{0},Q,\mu,\nu)$ 接口。[O] 尚缺覆盖全定义域的生产强度表、Phase 4
local-intensity provider 适配器和偏振局域源函数。完成这些后才可重跑 Phase 4/5A。

### 5.3 周期动态 NLTE 柱

[V] 项目已有周期动态大气、非局域动态转移和 mixed-frame ALE 构件。[O] 尚缺收敛的全轨道
history-aware $I_{\nu}(a,E,\mu)$ 以及携带相位/历史 provenance 的 Phase 4 适配器。触发条件
是收敛后的物理静态有效性失败，不是算法运行慢或一次候选被拒绝。

## 6. 当前结论

- [V] 合同和三分支单元测试已经建立；边界值采用闭区间，三个分支互斥。
- [O] 正式 feedback pair、全定义域耦合解、历史回线、生产强度表和 band/ionizing 对照尚缺。
- [A-classification] 所有数值阈值均显式标记并要求敏感性分析。
- [V] 当前判决保持 not_ready，没有运行 Phase 4 atlas，也没有提前选择最有利分支。
