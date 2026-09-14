# Phase 5B3a：ZO 2020 已发表分支反演审计

## 1. 结论先行

Phase 5B3a 沿 ZO 2020 Fig. 7 左图的 $e_{\rm in}$ 方向重新追踪了三维 Eq. (34)/(38)
无节点非线性分支，并独立检查了线性本征谱的径向节点拓扑。[L/V]

结果没有复现已发表分支：

- [V] 在 $e_{\rm in}=0.10$--$0.30$、$a_{\rm out}/a_{\rm in}=1.3,2,4$ 的 18 个状态中，
  三维无节点频率始终为正，范围为 $1.3917313$--$1.7880953$；
- [V] published 曲线在同一区间从负值跨过零，而 published 与三维解的差异可近似写成
  $A/e_{\rm in}+B$，三组 $R^{2}=0.9672$--$0.9956$；
- [A] 这种 $1/e_{\rm in}$ 型差异与“小的绝对 Hamiltonian 偏导误差被频率项中的
  $e$ 除大”相容，但不能确定具体偏导、差分格式或未公开代码中的原因；
- [V] 线性强形式证明无节点支在窄环极限保持有限；发散的是一、二径向节点支；
- [O] published 分支仍未得到方程级复现，故 $\Phi\mapsto t$ 的正式映射继续封锁。

## 2. 文献数据怎样获得

published 点来自 arXiv 源包内 Fig. 7 左图的原始 PDF 矢量路径，而不是从低分辨率截图
目测读数。[L/V] 图轴使用

$$
1-e_{\rm in}
=
10^{
\left(x_{\rm PDF}-x_{10^{0}}\right)/
\left(x_{10^{-1}}-x_{10^{-2}}\right)
},
$$

再把路径坐标线性映射到 $\widetilde{\omega}$。审计只在
$e_{\rm in}=0.10,0.15,0.1918332609,0.20,0.25,0.30$ 六个预先选定位置对矢量路径插值。
这些值在 CSV 中明确命名为 published_frequency_digitized，不能升级为解析真值。[L/V]

## 3. 三维无节点连续追踪

对每个半径比，先用 Phase 5B1 的线性无节点频率作为初值，再沿递增
$e_{\rm in}$ 逐点延续。每一点都重新满足

$$
e(1)=e_{\rm in},
\qquad
F_{f}(1)=F_{f}(x_{\rm out})=0,
$$

并拒绝 $e\le0$、非正 Jacobian、$F_{\rm ff}\le0$ 或 Hamiltonian 表外状态。[V]

| $a_{\rm out}/a_{\rm in}$ | $e_{\rm in}$ | published | 三维 Eq. (38) | published $-$ 三维 |
|---:|---:|---:|---:|---:|
| 1.3 | $0.10$ | $-2.082780$ | $1.788095$ | $-3.870875$ |
| 1.3 | $0.191833$ | $-0.717062$ | $1.733672$ | $-2.450734$ |
| 1.3 | $0.30$ | $-0.115162$ | $1.629105$ | $-1.744268$ |
| 2.0 | $0.10$ | $-0.612580$ | $1.565987$ | $-2.178567$ |
| 2.0 | $0.30$ | $0.371165$ | $1.442010$ | $-1.070845$ |
| 4.0 | $0.10$ | $-0.308883$ | $1.513372$ | $-1.822255$ |
| 4.0 | $0.30$ | $0.394540$ | $1.391731$ | $-0.997191$ |

18 个解的最大绝对外边界残差为 $3.79\times10^{-10}$，全部径向节点数为零。[V]

## 4. $1/e$ 型差异只是一项诊断

定义

$$
\Delta\widetilde{\omega}
=
\widetilde{\omega}_{\rm pub}
-
\widetilde{\omega}_{\rm 3D}.
$$

若 Eq. (38) 分子中存在近似不随 $e$ 消失的绝对误差 $\delta N$，而本征频率项为

$$
\widetilde{\omega}x^{3/2}
\frac{e}{\sqrt{1-e^{2}}},
$$

则在 $e\ll1$ 时会有诊断性尺度

$$
\delta\widetilde{\omega}
\sim
\frac{\delta N}{e}.
$$

因此本阶段拟合

$$
\Delta\widetilde{\omega}
=
\frac{A}{e_{\rm in}}+B.
$$

| $a_{\rm out}/a_{\rm in}$ | $A$ | $B$ | $R^{2}$ | $e_{\rm in}\Delta\widetilde{\omega}$ 的变异系数 |
|---:|---:|---:|---:|---:|
| 1.3 | $-0.31473$ | $-0.76728$ | $0.99559$ | $0.1047$ |
| 2.0 | $-0.16304$ | $-0.58638$ | $0.98831$ | $0.1326$ |
| 4.0 | $-0.12004$ | $-0.66950$ | $0.96722$ | $0.1659$ |

[A] 这说明差异形状与 $1/e$ 放大高度相容，但常数项不可忽略，且三种半径比的 $A$ 不同。
它不能证明原作者的 $F_{e}$、$F_{f}$ 或任何特定导数有误；源包没有数值代码，无法完成
逐行归因。[O]

## 5. 初始频率与物理表域审计

在论文 Fig. 6 的 $e_{\rm in}=0.2\sqrt{0.92}$ 上，以相同正无节点初始形状分别输入
$\widetilde{\omega}_{\rm guess}=-3,-0.7,0,2,5$。[V]

- $a_{\rm out}/a_{\rm in}=1.3$ 的五次计算全部收敛到
  $1.7336723$，最大频率跨度小于 $1.1\times10^{-7}$；
- $a_{\rm out}/a_{\rm in}=4$ 的 $2,5$ 两个猜测收敛到 $1.4714707$，跨度为
  $3.00\times10^{-7}$；
- $a_{\rm out}/a_{\rm in}=4$ 的 $-3,-0.7,0$ 三次 Newton 路径走出预声明的
  $(e,q)$ 表域，均被保留为 rejected，而不是外推、裁剪或删除。

[V/O] 成功猜测没有找到 published 负频率支；失败猜测也不能用来证明该支不存在，因为
它们只说明当前正无节点初形的 Newton 路径离开了物理表域。

## 6. 图像与逐图解释

### 6.1 published 曲线、三维延续与缩放差异

![Published branch inverse audit](../outputs/phase5b3a_published_branch_inverse_audit.png)

**怎么看。** 左图虚线圆点是 Fig. 7 的矢量数字化值，实线方点是同一
$(e_{\rm in},a_{\rm out}/a_{\rm in})$ 上的三维 Eq. (38) 解。右图画
$e_{\rm in}(\widetilde{\omega}_{\rm pub}-\widetilde{\omega}_{\rm 3D})$；若差异纯为
$A/e_{\rm in}$，每条曲线应为水平线。

**验证了什么。** [V] 两套曲线在整个区间分离，三维支没有跨零；右图只缓慢变化，支持
“含显著 $1/e$ 分量”的诊断。

**不能证明什么。** [A/O] 右图不完全水平，不能把差异归结为单个常量偏导误差，更不能
据此修改 Hamiltonian 使其迎合 published 曲线。

### 6.2 窄环线性分支拓扑

![Linear branch topology](../outputs/phase5b3a_linear_branch_topology.png)

**怎么看。** 横轴为环的相对宽度 $a_{\rm out}/a_{\rm in}-1$，纵轴取频率绝对值。
蓝色无节点支由独立强形式积分给出；橙色和紫色分别是一、二节点 Galerkin 支。

**验证了什么。** [V] 当环宽从 $3$ 缩到 $10^{-3}$，无节点频率保持在约
$1.53$--$2.13$；高阶支则向巨大负频率发散。强形式无节点值与 Galerkin 值的最大相对差
为 $4.15\times10^{-6}$。

**不能证明什么。** [O] 该图证明“发散不是无节点线性支的必然性质”，但不能从 published
频率曲线反推出原作者程序到底跟踪了哪条离散分支。

## 7. 阶段判定

- [L/V] Fig. 7 矢量数据与 Fig. 6 标注彼此一致；
- [V] 正确三维无节点分支在测试区间连续、有限、正频率；
- [V] published 曲线不能由初始频率猜测或线性无节点分支正常延续解释；
- [A] published 差异含明显 $1/e_{\rm in}$ 型分量；
- [O] 尚无证据唯一定位到某个 Hamiltonian 偏导、二维/三维切换或分支跟踪错误；
- [O] 文献基准门继续失败，不授权正式天尺度进动图谱。

下一步只能选择：取得原作者数值实现进行逐项对照，或把当前独立三维方程解明确标为
“方程自洽但未通过 published benchmark”的候选时标。后一选择会改变项目的正式基准，
需要单独立门，不能在本阶段静默采用。[O]

## 8. 复现

    uv run python scripts/phase5b3a_published_branch_inverse_audit.py
    uv run pytest -q tests/test_phase5b3a_published_branch_inverse_audit.py

本阶段完成后的现场聚焦回归为 42 passed，完整回归为 573 passed。[V]

阶段关系见
[[eccentric_tde_observer/docs/phase5b3_nonlinear_apsidal_benchmark_gate|Phase 5B3]]、
[[eccentric_tde_observer/docs/phase5b1_linear_apsidal_mode_gate|Phase 5B1]]和
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]。
