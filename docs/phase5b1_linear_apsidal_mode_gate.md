# Phase 5B1：线性拱点本征模与物理时标门槛

## 1. 本阶段解决了什么

Phase 5B1 独立实现并验证了三维、无扭曲、小偏心极限下的自由边界拱点进动本征问题。
它回答的是“离散算子、自由边界、压力通信和局域 GR 项能否一致给出线性全局模”，不是
“已经求出严格域 $e=0.6$ 偏心盘的非线性进动周期”。`[L/V/O]`

新增入口为：

- `src/eccentric_tde_observer/apsidal_precession.py`：P1 Galerkin 广义本征求解器；
- `scripts/phase5b1_linear_apsidal_mode_gate.py`：独立强形式、收敛、物理尺度和出图门槛；
- `outputs/phase5b1_linear_apsidal_report.json`：全部数值、判据和阶段授权；
- `outputs/phase5b1_linear_apsidal_convergence.csv`：逐半径范围、逐网格的完整结果；
- `outputs/phase5b1_local_gr_profile.csv`：局域 GR 差分进动率。

本阶段没有修改 [[eccentric_tde_observer/docs/phase1e_zo_reference|ZO 源场]]，也没有把线性
本征函数写回连续谱或谱线模型。`[V]`

## 2. 物理方程与边界

### 2.1 三维线性偏心方程

采用 Ogilvie & Lynch 2019 Eq. (44)。对无扭曲模
$\mathcal{E}(a,t)=e(a)\exp(\mathrm{i}\omega t)$，其压力算子写为

$$
2\Sigma^{\circ}na^{3}\omega e
=
\frac{\mathrm{d}}{\mathrm{d}a}
\left[
\left(2-\frac{1}{\gamma}\right)
P^{\circ}a^{3}\frac{\mathrm{d}e}{\mathrm{d}a}
\right]
+
\left(4-\frac{3}{\gamma}\right)
\frac{\mathrm{d}P^{\circ}}{\mathrm{d}a}a^{2}e
+
3\left(1+\frac{1}{\gamma}\right)P^{\circ}ae.
$$

代码固定 $\gamma=4/3$，并使用 ZO Eqs. (9)--(12) 的
$\Sigma^{\circ}\propto a^{-3}$、$P^{\circ}\propto a^{-4}$ 和平均运动 $n$。局域
Schwarzschild 拱点进动作为质量矩阵上的位置相关项加入：

$$
\omega_{\rm GR}(a,e)
=
\frac{3R_{\rm g}n(a)}{a(1-e^{2})}.
$$

这里的“GR only”只是一条局域差分进动曲线；没有压力通信时，不存在自动保持相干的
全局盘本征模。`[L/V]`

### 2.2 自由边界

线性化 ZO Eq. (43) 的 $\partial F/\partial f=0$ 得到两端 Robin 条件

$$
(2\gamma-1)a\frac{\mathrm{d}e}{\mathrm{d}a}
+(4\gamma-3)e=0.
$$

对 $\gamma=4/3$，即

$$
a\frac{\mathrm{d}e}{\mathrm{d}a}=-1.4e.
$$

它是 Hamiltonian 变分问题的自然边界，不是人为令 $e=0$ 的刚性边界。有限元弱形式直接
保留这两个边界项。`[L/V]`

### 2.3 文献公式审计

Ogilvie & Lynch 2019 的期刊 PDF 和 arXiv 主源 TeX 在 Eq. (43) 中都字面写出
$(5\gamma-9\gamma)e^{2}$，但紧接着的 Eq. (44) 对应的是
$(5\gamma-9)e^{2}$。本阶段不从这个互相矛盾的二次 Hamiltonian 式重建算子，而以论文明确
给出、且说明与 Teyssandier & Ogilvie 2016 一致的 Eq. (44) 为线性基准，并用独立强形式
再次检查。这里把前者保留为文献开放问题，不擅自改写原论文。`[L/V/O]`

文献入口：[[markdown_papers/1812.05942v1|Ogilvie & Lynch 2019]]、
[[markdown_papers/2009.06636v2|Zanazzi & Ogilvie 2020]]。

## 3. 两套独立离散

### 3.1 弱形式

正式代码使用几何径向网格、P1 基函数和四点 Gauss 单元积分，求解

$$
\mathbf{K}\boldsymbol{e}=\omega\mathbf{M}\boldsymbol{e}.
$$

$\mathbf{K}$ 与 $\mathbf{M}$ 都逐单元直接积分；GR 和统一外加进动项没有折成节点后验
修正。计算同时检查矩阵对称、$\mathbf{M}$ 正定、本征残差和径向节点数。`[V]`

### 3.2 强形式射击法

门槛脚本另用 DOP853 直接积分 Eq. (44) 的强形式，从内边界 Robin 条件出发，并以外边界
Robin 残差在预声明区间 $0<\widetilde{\omega}<4$ 内求根。该路径不调用有限元矩阵或其
本征值。4097 个审计采样点确认所比较的根无径向节点。`[V]`

### 3.3 边界残差为何保存两种

P1 解在每个单元中是线性的，所以直接拿首个单元斜率近似边界处光滑解导数，只能一阶
收敛。512 点最坏原始残差仍为 $3.274091\times10^{-3}$，没有删除。三个边界节点的二次
导数外推残差为 $1.206454\times10^{-5}$，并从 64 到 512 点近似每次加密缩小四倍；正式
边界门使用后者，但 CSV 同时保留两者。`[V]`

## 4. 数值结果

基准参数为 $M_{\bullet}=10^{6}M_{\odot}$、$M_{\star}=M_{\odot}$、
$R_{\star}=R_{\odot}$、$\mathcal{V}=1$。512 点无节点模为：

| $a_{\rm out}/a_{\rm in}$ | pressure only $\widetilde{\omega}$ | pressure + GR $\widetilde{\omega}$ | pressure + GR 周期 | 强--弱相对差 |
|---:|---:|---:|---:|---:|
| 1.3 | 1.785378 | 1.808865 | 96.06 day | $7.24\times10^{-8}$ |
| 2.0 | 1.562765 | 1.582271 | 109.81 day | $4.93\times10^{-7}$ |
| 3.0 | 1.515180 | 1.534258 | 113.25 day | $1.20\times10^{-6}$ |
| 4.0 | 1.510330 | 1.529432 | 113.61 day | $1.88\times10^{-6}$ |

表中 day 值只属于 $e\to0$、$\mathcal{V}=1$ 的线性控制，不能贴到
$(e,\mathcal{V})=(0.6,0.01)$ 严格域源上。`[V/O]`

全部门槛结果：

- 512 点强--弱形式最坏相对差：$1.907752\times10^{-6}<3\times10^{-6}$；
- 256 对 512 点最坏频率变化：$5.753100\times10^{-6}<10^{-5}$；
- 二阶外推 Robin 残差：$1.206454\times10^{-5}<2\times10^{-5}$；
- 刚度/质量矩阵对称且质量矩阵正定；
- 统一外加进动 $2.5\times10^{-8}\ {\mathrm{s}}^{-1}$ 的最坏平移误差为
  $1.824165\times10^{-18}\ {\mathrm{s}}^{-1}$，本征函数最大变化
  $1.104228\times10^{-12}$。`[V]`

## 5. 图像与逐图解释

### 5.1 线性本征函数

![Linear node-free apsidal eigenfunctions](../outputs/phase5b1_linear_eigenfunctions.png)

四个面板分别增加盘的径向范围。所有基模从内边界单调下降且无节点；盘越宽，外边界相对
偏心率越低。$\delta_{\rm GR}=0.030565$ 时 pressure only 与 pressure + GR 的形状几乎
重合，但图例中的频率发生稳定正移。这表示当前基准 GR 主要改动整体频率，还没有重塑
线性本征函数；它不表示局域 GR 处处相同。`[V]`

### 5.2 径向收敛与独立强--弱对照

![Linear apsidal radial convergence](../outputs/phase5b1_linear_convergence.png)

左图的频率变化在纵轴尺度上很小；右图改画相对独立强形式的误差，显示全部序列随节点数
增加而下降。最宽的 $a_{\rm out}/a_{\rm in}=4$ 是最慢收敛案例，但 512 点仍通过预声明
$3\times10^{-6}$ 强--弱门。`[V]`

### 5.3 物理归一化与局域 GR

![ZO precession scale audit](../outputs/phase5b1_precession_scale_audit.png)

左图不是两种可任选的物理模型。蓝柱由 ZO Eqs. (9)--(12)、(39) 逐步计算；橙柱是论文
Eq. (48) 的印刷系数。对 $\widetilde{\omega}=0.1$，两者分别为
$5.755353\times10^{-4}$ 与 $5.755849\times10^{-3}\ {\mathrm{cycle}\,day^{-1}}$，相差
$10.000862$ 倍。相同账本能以 $1.62\times10^{-4}$ 相对差回收 Eq. (40) 的
$\delta_{\rm GR}$ 系数，所以程序不会静默采用 Eq. (48) 的十倍归一化。`[L/V/O]`

右图显示局域 GR 无量纲率从 $a_{\rm in}$ 的 $0.030565$ 降到
$4a_{\rm in}$ 的 $9.55155\times10^{-4}$。这条明显的径向梯度说明，压力通信是形成相干
全局模的必要组成。`[V]`

## 6. 阶段判定

- `[V]` 线性小偏心自由边界求解器通过全部独立数值门；
- `[V]` Phase 5B2 可开始实现非线性 ZO Hamiltonian 核；
- `[O]` 尚未复现 ZO Figs. 6--7 的高偏心本征模；
- `[O]` 尚未授权把严格域源的相位 $\Phi$ 换成 day；
- `[O]` Eq. (48) 十倍差异需要在高偏心复现中继续交叉核查，不能用印刷系数覆盖直接
  量纲账本。

因此当前最严格的结论是：

> 三维线性拱点本征问题已经通过弱形式、独立强形式、自由边界、GR 和径向收敛检验；
> 但真实项目使用的高偏心源仍需非线性 Hamiltonian 求解，现有相位图谱暂时不能标绝对天数。

## 7. 复现命令

```bash
uv run python scripts/phase5b1_linear_apsidal_mode_gate.py --output-dir outputs
uv run pytest -q tests/test_apsidal_precession.py tests/test_phase5b1_linear_apsidal_mode_gate.py
```

本阶段完成后的现场完整回归为 `535 passed in 56.51s`。`[V]`

下一阶段见[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]；连续谱和条件性
线核的既有定位分别见[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]与
[[eccentric_tde_observer/docs/phase6_line_response|Phase 6 报告]]。
