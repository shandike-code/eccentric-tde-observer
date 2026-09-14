# Phase 7B4m：前沿感知可变子单元与空间准入门

导航：[[eccentric_tde_observer/README|项目总览]] ·
[[eccentric_tde_observer/docs/phase7b4l_conservative_subcell_reconstruction|Phase 7B4l 报告]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

## 1. 本阶段回答什么

Phase 7B4l 已证明保守子单元能够改善移动前沿表示并严格保持质量、H/He 粒子数、电荷和
总比能，但全柱固定两个子单元时，32 对 64 有效深度的逐点人口误差仍为 $0.1132$。7B4m
因此只检验一个受限问题：**能否用 pilot 解自身的嵌入式守恒缺陷找到需要额外真实自由度的
父单元，并在不改 ZO 背景和动态方程的条件下关闭 $10^{-3}$ 空间门？** `[A/V]`

本阶段没有实现非局域频率转移、激发态、总复合级联、速度--频率耦合、Phase 4 大气表或
UVOT 仪器层。64 层解是已保存的有限分辨率参考，不是连续极限。`[O]`

## 2. 网格与误差估计器

令 $x$ 为从表面到中面的拉格朗日柱质量分数。固定 16 个父单元；每个父单元在 pilot
网格中有 2 个子单元，在 master 网格中有 4 个子单元，所以三层总自由度分别为 16、32、64。
对 pilot 场 $q_{p,k}$，先在父单元 $P$ 内按子单元质量宽度限制：

$$
\bar q_{\rm P}
=
\frac{1}{\Delta x_{\rm P}}
\sum_{k\in P}q_{p,k}\,\Delta x_{k}.
$$

再用 Phase 7B4l 已验证的受限线性守恒延拓得到 $\widehat q_{p,k}$，其父平均严格满足

$$
\frac{1}{\Delta x_{\rm P}}
\sum_{k\in P}\widehat q_{p,k}\,\Delta x_{k}
=\bar q_{\rm P}.
$$

估计器同时监视四个分量：

$$
\epsilon_{\rm T,\rm P}
=
\max_{t,k\in P}
\left|\ln T_{p,k}-\ln \widehat T_{p,k}\right|,
$$

$$
\epsilon_{\kappa,\rm P}
=
\max_{t,k\in P}
\left|\ln \kappa_{{\rm R},p,k}
-\ln \widehat\kappa_{{\rm R},p,k}\right|,
$$

$$
\epsilon_{{\rm H\,II},P}
=
\max_{t,k\in P}
\left|x_{{\rm H\,II},p,k}
-\widehat x_{{\rm H\,II},p,k}\right|,
$$

$$
\epsilon_{{\rm He\,III},P}
=
\max_{t,k\in P}
\left|x_{{\rm He\,III},p,k}
-\widehat x_{{\rm He\,III},p,k}\right|.
$$

这里对正定热力学量使用对数缺陷，对人口使用绝对缺陷。父单元排序量为

$$
\eta_{\rm P}
=
\frac{
\max\left(
\epsilon_{\rm T,\rm P},
\epsilon_{\kappa,\rm P},
\epsilon_{{\rm H\,II},P},
\epsilon_{{\rm He\,III},P}
\right)
}{10^{-3}}.
$$

排序采用稳定降序，不拟合各分量权重，也不在看到正式结果后改阈值。若加密误差最大的
$K$ 个父单元，则真实动态自由度为

$$
N_{\rm eff}=2(16-K)+4K=32+2K.
$$

正式预算预先固定为 $K=12,14,15$，即 $N_{\rm eff}=56,60,62$。`[A-classification/V]`

## 3. 为什么初态仍然守恒

三个变量网格不能从不同粗网格各自随意插值得到初态。统一流程是：

1. 在 16 层父网格求同一个静态初态；
2. 把总比能、H II、He II、He III 保守延拓到 64 层 master 网格；
3. 中性级由元素粒子守恒导出；
4. 把 64 层单元按变量网格严格合并；
5. 由合并后的总比能和人口反演温度。

总比能仍为 Phase 7B4l 的气体、辐射与基态电离能之和：

$$
e_{\rm tot}
=e_{\rm gas}+e_{\rm rad}+e_{\rm ion}.
$$

每个变量单元 $C$ 的合并满足

$$
\bar e_{{\rm tot},C}
=
\frac{
\sum_{k\in C}e_{{\rm tot},k}\,\Delta m_{k}
}{
\sum_{k\in C}\Delta m_{k}
},
$$

人口和 opacity 采用相同的质量有限体积限制；父边界通量直接从严格嵌套的子边界抽取，
所以父单元通量散度由子单元散度望远镜求和得到。没有事后物理重归一化。`[V]`

## 4. 控制实验

嵌入式估计器的最大父平均残差为 $8.27\times10^{-13}$，低于守恒容差
$2\times10^{-12}$。16 个父单元中有 10 个在轨道周期某一相位包含 He III 半电离前沿；
最高指标位于父单元 1，$\eta_{1}=139.58$。所有正式变量网格严格保留 32 层 pilot 的每条
边界。`[V]`

独立排序验证不能使用“加密后的残余误差”，因为加密本身会降低高指标区的误差。这里改用
未施加 7B4m 加密的 N=32 pilot 对有限 N=64 参考的逐父单元真实误差。嵌入式指标与该实际
误差的 Spearman 相关为

$$
\rho_{\rm S}=0.99118,
\qquad
p=1.09\times10^{-13}.
$$

这验证了排序能力；三个正式候选的加密后残余误差另存，不参与这项相关性检验。`[V]`

![Phase 7B4m embedded front-aware refinement](../outputs/phase7b4m_embedded_refinement.png)

- `(a)` 给出四个分量的嵌入式缺陷。He III 和正定热力学量控制表层排序，H II 缺陷远小于
  当前目标。`[V]`
- `(b)` 按父单元画最大归一化缺陷；红色单元是一个周期内出现过 He III 半电离前沿的区域。
  最高缺陷集中在表面附近，但排序没有把“是否遇到前沿”当成额外自由权重。`[A/V]`
- `(c)` 展示 56、60、62 与 64 层网格。所有网格严格嵌套；越接近表面的前沿区，边界越密。
  这些刻线是真实动态自由度，不是绘图插值节点。`[V]`
- `(d)` 是把已知 64 层场直接合并到各候选网格后的表示误差。它只说明预算选择合理，不能
  代替非线性动态重解，因此图题明确写为 control only。`[A-control/V]`

## 5. 正式动态计算

三个算例都使用 64 个轨道相位、71 个实际频率点、相同 ZO 严格域背景、相同局域能量容差
和周期容差。它们各自从统一守恒初态独立演化到周期解，没有从较粗候选热启动。`[A/V]`

| $N_{\rm eff}$ | 运行时间 | N=64/候选时间比 | 周期残差 | 周期能量账本残差 | 守恒 |
|---:|---:|---:|---:|---:|---:|
| 56 | $1065.0\ \mathrm s$ | $1.361$ | $4.72\times10^{-9}$ | $7.25\times10^{-14}$ | 通过 |
| 60 | $1223.1\ \mathrm s$ | $1.185$ | $4.50\times10^{-9}$ | $1.11\times10^{-13}$ | 通过 |
| 62 | $1328.3\ \mathrm s$ | $1.091$ | $4.28\times10^{-9}$ | $1.36\times10^{-13}$ | 通过 |
| 64 有限参考 | $1449.2\ \mathrm s$ | $1$ | $2.74\times10^{-9}$ | $1.55\times10^{-13}$ | 通过 |

这里的运行时间只描述当前机器和实现，不代表理论复杂度。N=62 只比 N=64 快约 $9.1\%$，
所以本阶段的主要价值是证明前沿定位和准入逻辑，而不是获得数量级加速。`[V]`

## 6. 空间误差

| 指标 | N=56 | N=60 | N=62 | 目标 |
|---|---:|---:|---:|---:|
| 表面通量相对误差 | $7.49\times10^{-6}$ | $4.72\times10^{-6}$ | $2.69\times10^{-6}$ | $10^{-3}$ |
| 最大逐点 $T/\kappa_{\rm R}$ 相对误差 | $3.683\times10^{-4}$ | $3.693\times10^{-4}$ | $3.703\times10^{-4}$ | $10^{-3}$ |
| 最大逐点 H II/He III 绝对误差 | $1.066\times10^{-3}$ | $5.458\times10^{-4}$ | $4.448\times10^{-4}$ | $10^{-3}$ |
| 最大柱平均 $T/\kappa_{\rm R}$ 相对误差 | $1.748\times10^{-4}$ | $1.140\times10^{-4}$ | $6.429\times10^{-5}$ | $10^{-3}$ |
| 最大柱平均 H II/He III 绝对误差 | $3.118\times10^{-4}$ | $1.317\times10^{-4}$ | $6.428\times10^{-5}$ | $10^{-3}$ |
| He III 半电离前沿质量分数误差 | $3.59\times10^{-6}$ | $2.25\times10^{-6}$ | $1.29\times10^{-6}$ | $10^{-3}$ |
| 前沿状态错配相位数 | 0 | 0 | 0 | 0 |

N=56 只因逐点人口误差 $1.066\times10^{-3}$ 略高于目标而失败；N=60 是预先声明预算中
第一个全部指标通过的点，N=62 也通过。逐点 $T/\kappa_{\rm R}$ 误差从 N=56 到 N=62
轻微增加约 $0.5\%$，所以“所有指标严格单调下降”为假；不过它始终低于目标，人口、柱平均、
通量和前沿位置则随预算改善。该轻微漂移必须保留，不能用后验重排序隐藏。`[V]`

![Phase 7B4m front-aware variable-depth convergence](../outputs/phase7b4m_variable_convergence.png)

- `(a)` 选取 He III 梯度最强的相位 18。四档剖面在极窄表层跃迁处仍可分辨，但 N=60、62
  已把实际人口误差压到目标以下。`[V]`
- `(b)` 四条表面能流响应在图上线宽内重合。动态出射相对瞬时 ZO 单面通量在轨道内约为
  $0.991$--$1.007$，但这仍是局域 Rosseland 动态柱，不是频率依赖输出谱。`[A/V/O]`
- `(c)` N=56 的人口点态误差略高于黑色目标线；N=60 和 N=62 通过。热力学点态误差出现
  小幅平台而非严格单调，图中没有省略。`[V]`
- `(d)` 表面通量、柱平均量和 He III 前沿误差均远低于目标并随预算下降。这与 `(c)` 一起
  说明局域人口仍是最后关闭的空间指标。`[V]`

## 7. 阶段判据与下一步

| 判据 | 结果 |
|---|---|
| 嵌入式限制--再延拓父平均守恒 | 通过 `[V]` |
| 指标对未加密 N=32 实际误差的排序验证 | 通过，$\rho_{\rm S}=0.99118$ `[V]` |
| 三个正式变量网格初态与动态限制守恒 | 通过 `[V]` |
| 首个测试通过预算 | N=60 `[A-classification/V]` |
| N=62 对有限 N=64 的空间生产门 | 通过 `[A-classification/V]` |
| 1024 对 2048 相位时间门 | 通过，继承 Phase 7B4k `[A-classification/V]` |
| 64 深度、1024 相位联合参考 | 7B4m 当时获准；7B4n 后续已完成但联合时间门失败 `[V/O]` |
| 非局域频率依赖动态转移 | 尚未获准 `[O]` |
| Phase 4 大气替换与 UVOT | 尚未获准 `[O]` |

7B4m 在本阶段结束时指定的下一微阶段是联合 $64$ 深度、$1024$ 相位周期动态参考；后续
7B4n 已执行该审计。只有联合参考完成且联合时间门通过后，才能把局域
$J_{\nu}=B_{\nu}(T)$--Rosseland 扩散替换为非局域、频率依赖的动态转移。7B4m 的通过
不能被解释为已经产生 NLTE 连续谱。`[V/O]`

本阶段没有使用 `nan_to_num`、任意 `clip`、任意物理 floor、删除失败相位或事后物理
重归一化。7B4m 新增 4 项测试，与 7B4l 子单元测试合并后为
`10 passed in 11.06s`；全项目现场回归为 `316 passed in 48.26s`。`[V]`

## 8. 产物

- `src/eccentric_tde_observer/adaptive_subcell_refinement.py`：嵌入式误差估计和变量网格；
- `src/eccentric_tde_observer/subcell_reconstruction.py`：严格嵌套合并和变量网格限制；
- `tests/test_adaptive_subcell_refinement.py`：制造前沿、嵌套拒绝、真实小型动态守恒和禁用修复；
- `scripts/phase7b4m_front_aware_variable_refinement.py`：控制、正式算例和汇总入口；
- `outputs/phase7b4m_control_report.json`：估计器与网格控制判据；
- `outputs/phase7b4m_complete_report.json`：空间、时间和路线准入判据；
- `outputs/phase7b4m_embedded_indicator.csv`：逐父单元四分量缺陷与排序；
- `outputs/phase7b4m_refinement_budgets.csv`：自由度预算和仅表示控制；
- `outputs/phase7b4m_variable_edges.csv`：全部候选的严格嵌套边界；
- `outputs/phase7b4m_convergence.csv`：三个正式动态算例的误差、成本与判据；
- `outputs/phase7b4m_estimator_validation.csv`：未加密 pilot 的独立排序验证；
- `outputs/phase7b4m_candidate_parent_residuals.csv`：加密后逐父单元残余误差；
- `outputs/phase7b4m_profiles.csv`：三个候选和有限 N=64 参考的逐相位剖面；
- `outputs/phase7b4m_embedded_refinement.png`：英文控制图；
- `outputs/phase7b4m_variable_convergence.png`：英文正式空间收敛图。

复现命令：

```bash
uv run python scripts/phase7b4m_front_aware_variable_refinement.py --stage control
uv run python scripts/phase7b4m_front_aware_variable_refinement.py --stage cases
uv run python scripts/phase7b4m_front_aware_variable_refinement.py --stage summary
```

正式算例若已经成对保存，会被安全复用；不完整的单个输出会被拒绝，而不是当作已完成。

后续结果见
[[eccentric_tde_observer/docs/phase7b4n_joint_depth_time_reference|Phase 7B4n 联合深度--时间参考]]：
N=62 对 N=64 的 1024 相位空间门继续通过，但 N=64 的 512 对 1024 高深度时间比较以
$1.087\times10^{-3}$ 的最大 He III 误差轻微失败。64×1024 有限参考已经完成，联合生产
门和非局域动态转移仍未获准；下一步必须直接计算 N=64、2048 相位参考。`[V/O]`

后续状态：[[eccentric_tde_observer/docs/phase7b4o_high_depth_time_reference|Phase 7B4o]] 已完成
该 N=64、2048 相位独立审计并通过联合有限时间门；这不改变 7B4m 本阶段只关闭空间门的
历史结论。`[V]`
