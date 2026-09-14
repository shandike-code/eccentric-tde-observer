# Phase 7B4p：冻结动态柱的非局域转移审计

> [!abstract] 本阶段定位
> Phase 7B4p 在 [[eccentric_tde_observer/docs/phase7b4o_high_depth_time_reference|Phase 7B4o]]
> 的 N=64、2048 相位有限动态参考上冻结物质状态，逐相位求解频率--角度非局域形式解。
> 它回答两件事：局域 $J_{\nu}=B_{\nu}$ 闭合偏离多少，以及辐射场能否视为逐相位准静态。
> 它不是含辐射储能的动态 NLTE 解，也没有生成观察者连续谱。

证据分类沿用项目约定：`[L]` 文献或基本转移关系，`[V]` 代码验证，`[A]` 工作假设或
诊断定义，`[O]` 尚未关闭的问题。

## 1. 为什么先做冻结形式解

7B4o 已关闭物质态的有限深度--时间门，但当时仍用局域 Planck 场计算 H/He 基态辐射率。
真正的辐射场由其他深度的发射、吸收和相干电子散射共同决定，因此一般有
$J_{\nu}(z)\ne B_{\nu}[T(z)]$。在直接编写动态辐射储能求解器前，必须先判断：

1. 现有静态形式解在真实动态柱上是否守恒；
2. 频率、角度、深度和轨道相位是否达到数值门；
3. 光行时或扩散时是否足够短，使逐相位静态辐射场成为可接受近似。

本阶段只冻结 7B4o 给出的 $\rho(m,t)$、$T(m,t)$、H/He 基态布居和 Rosseland opacity，
不回写或重新定义 ZO 动力学源场。`[A/V]`

## 2. 完整对称柱与转移方程

7B4o 保存从一个表面到中面的拉格朗日半柱。7B4p 按中面对称关系镜像为 128 单元完整柱，
两侧外边界均取真空。对每个频率和方向余弦求解

$$
\mu\frac{\partial I_{\nu}}{\partial z}
=
\chi_{\nu}\left(S_{\nu}-I_{\nu}\right),
$$

其中源函数为

$$
S_{\nu}
=
\epsilon_{\nu}B_{\nu}
+
\left(1-\epsilon_{\nu}\right)J_{\nu},
\qquad
\epsilon_{\nu}
=
\frac{\chi_{\nu}^{\rm abs}}
{\chi_{\nu}^{\rm abs}+\chi_{\nu}^{\rm es}}.
$$

这里 $\chi_{\nu}^{\rm abs}$ 来自现有 H I、He I、He II 基态 Milne 束缚--自由过程与
自由--自由过程，$\chi_{\nu}^{\rm es}$ 是相干 Thomson 散射。平均强度和频率分辨能流为

$$
J_{\nu}
=
\frac{1}{2}\int_{-1}^{1}I_{\nu}\,{\rm d}\mu,
\qquad
F_{\nu}
=
2\pi\int_{-1}^{1}\mu I_{\nu}\,{\rm d}\mu.
$$

代码显式求解离散 $\Lambda$ 系统，没有用失败迭代外推。生产探索文件使用 71 个实际频率点
和 4 个半区间离散方向；后文证明这两个设置都不能自动称为收敛配置。`[V/O]`

## 3. 能量账本与控制题

材料的辐射加热定义为

$$
q_{\rm rad}(z)
=
4\pi\int
\left[
\chi_{\nu}^{\rm abs}J_{\nu}-\eta_{\nu}^{\rm th}
\right],{\rm d}\nu.
$$

正值表示材料吸收能量，负值表示材料净辐射冷却。对双真空完整柱，积分账本满足

$$
F_{\rm top}+F_{\rm bottom}
+
\int q_{\rm rad}\,{\rm d}z
=
0.
$$

五个独立控制的最大误差如下：`[V]`

| 控制 | 误差 |
|---|---:|
| LTE Kirchhoff 源函数回收 $B_{\nu}$ | $4.339\times10^{-13}$ |
| 对称完整柱积分能量 | $1.219\times10^{-14}$ |
| 对称完整柱 $J_{\nu}$ 镜像 | $2.602\times10^{-16}$ |
| 纯相干散射通量守恒 | $3.336\times10^{-16}$ |
| 高光深线性源函数扩散通量 | $7.768\times10^{-13}$ |

2048 个真实冻结相位全部完成；最大积分能量残差为 $5.813\times10^{-13}$，最大源方程
残差为 $3.668\times10^{-13}$，最大上下边界镜像残差为 $4.601\times10^{-14}$。这说明
形式解本身守恒，但不说明所选频率、角度和深度网格已经收敛。`[V]`

## 4. 准静态辐射门

本阶段采用扩散量级估计

$$
t_{\rm diff}
\simeq
\frac{3\tau_{\rm R}H}{c},
$$

并以 $t_{\rm diff}/P_{\rm orb}<0.1$ 作为预声明的准静态分类门。这里的 0.1 是
`[A-classification]`，因此同时报告 0.03、0.1 和 0.3 三个阈值敏感性，而不是只给一个
通过/失败标签。

实际结果为：`[V]`

- $P_{\rm orb}=4.160\times10^{6}\ {\rm s}$；
- $t_{\rm diff}=8.134\times10^{4}$--$3.069\times10^{6}\ {\rm s}$；
- $\max(t_{\rm diff}/P_{\rm orb})=0.7379$；
- 高于 0.03、0.1、0.3 的相位比例分别为 0.4976、0.3550、0.2202；
- 最大光行时只占轨道周期的 $1.236\times10^{-3}$，失败来自随机游走扩散而不是单次光行时。

因此逐相位稳态辐射场不能成为最终动态闭合。物理上需要保留辐射能量储存和轨道记忆，
但数值上还必须先关闭第 6 节的频率和深度门。`[V/O]`

## 5. 局域 Planck 闭合偏差

在当前 0.1--5000 eV 探索频带内定义

$$
u_{\rm rad}
=
\frac{4\pi}{c}\int J_{\nu}\,{\rm d}\nu,
\qquad
u_{\rm B}
=
\frac{4\pi}{c}\int B_{\nu}\,{\rm d}\nu.
$$

71 频点冻结解给出的全局尺度归一化最大差为 $2.493\%$；逐点
$u_{\rm rad}/u_{\rm B}=0.7767$--$1.4022$，但质量加权比只在 0.9848--0.9925。H I、He I、
He II 光致电离率的全局尺度误差分别为 $0.705\%$、$2.610\%$、$0.374\%$。`[V]`

这些数字证明 $J_{\nu}=B_{\nu}$ 不是逐点恒等式，但还不是最终物理修正量，因为同一 71 点
频率积分未通过速率收敛。尤其某些很小的局部 He I 光致率会给出很大的逐点比值；报告同时
保留全局尺度误差和质量加权比，避免只挑选最显眼的比值。`[V/O]`

冻结形式解的顶部通量相对瞬时 ZO 单面加热为 0.8238--1.3883，而 7B4o 动态扩散通量为
0.9886--1.0086。冻结状态中最大 $|q_{\rm rad}|/q_{\rm mech}=48.61$。这不是新的平衡解，
而是“若把当前物质态交给静态非局域辐射场，它会怎样立即吸热或冷却”的残差诊断。`[V]`

## 6. 四条数值收敛轴

所有误差均为参考量全局最大绝对值归一化的最大绝对差，目标为 $10^{-3}$；没有删除失败相位、
加入 floor、裁剪或事后物理重归一化。`[A-classification/V]`

### 6.1 轨道相位

1024 相位周期插值到独立 2048 相位参考后，最大误差为：

- 顶部 bolometric 通量：$7.260\times10^{-5}$；
- 频带辐射能量：$3.706\times10^{-5}$；
- 比辐射加热：$7.426\times10^{-4}$；
- 三个光致电离率：$3.052\times10^{-5}$--$5.305\times10^{-5}$；
- 三个总复合率：$2.043\times10^{-5}$--$3.398\times10^{-5}$。

时间轴通过。`[V]`

### 6.2 角度

12 个代表相位上的 4 对 12 方向最大误差为 $3.162\%$，8 对 12 为
$1.588\times10^{-3}$，最敏感量都是辐射加热。对最差相位继续加密得到：

- 12 对 16：$1.448\times10^{-4}$；
- 16 对 24：$6.626\times10^{-5}$。

因此角度求积存在可见的收敛序列，但正式 4 方向文件未通过；后续至少应采用并重新验证
12 或更高角阶。`[V/O]`

### 6.3 频率

12 个代表相位上的 71 对 135 实际频率点比较未通过。相位 0.5 的扩展序列使用
71、135、263、519 个实际点和 12 方向，逐次最大误差为：

| 比较 | 最大误差 | 最敏感量 |
|---|---:|---|
| 71 对 135 | $1.675$ | He II 总复合率 |
| 135 对 263 | $0.2836$ | He I 总复合率 |
| 263 对 519 | $0.3688$ | He II 总复合率 |

同一 263 对 519 比较中，bolometric 通量已经达到 $5.521\times10^{-5}$，但辐射加热为
$1.648\times10^{-3}$，H/He 光致电离和复合率仍为百分级到几十个百分点。不能用“总通量
已经收敛”替代原子速率收敛。`[V]`

失败表明跨越 H I、He I、He II 离化边的宽对数梯形网格不适合作为速率生产求积。下一微阶段
必须设计阈值分段、带独立权重的频率求积，并分别验证能量矩和光子数矩；单纯把全轨道点数
机械加倍既昂贵，也没有关闭现有序列。`[V/O]`

### 6.4 深度

在 12 个代表相位上独立使用 7B4n 的 N=62 和 N=64 动态物质态，并比较质量积分量。最大差
为 $3.013\times10^{-3}$，来自 He II 光致电离率；He I 也为 $1.059\times10^{-3}$。
现有最高独立动态参考只有 N=64，因此本阶段不能把 N=64 称为非局域速率的深度极限。`[V/O]`

## 7. 图像逐图解释

![Phase 7B4p frozen non-local orbit](../outputs/phase7b4p_frozen_nonlocal_orbit.png)

- 面板 (a)：蓝线是冻结非局域形式解，橙虚线是 7B4o 的动态扩散通量。二者差异说明冻结
  物质态不是新的动态平衡。
- 面板 (b)：大约 35.5% 的轨道相位超过 0.1 准静态门，峰值接近 0.74；必须保留辐射储能。
- 面板 (c)：质量加权频带能量只比局域 Planck 值低约 0.7%--1.5%，但这会掩盖逐点最高
  40% 的偏差，所以不能只看柱平均。
- 面板 (d)：局部辐射加热/冷却可达规定机械加热的几十倍，再次表明形式解只是残差审计。

![Phase 7B4p exploratory spectra](../outputs/phase7b4p_nonlocal_spectra.png)

- 面板 (a)：展示每相位 $\nu F_{\nu}/F_{\rm bol}$ 的归一化诊断谱形；它没有被赋予任意
  绝对重标定。
- 面板 (b)：展示冻结形式解的绝对表面 $\nu F_{\nu}$。高能尾跨越极大动态范围，但 71 点
  频率门失败，所以这些曲线不可用作观察者预测。
- 面板 (c)：相位 0.99 的总消光包含较平坦的电子散射底，而真吸收在离化边出现跃迁；这正是
  普通宽对数梯形求积难以稳定原子速率的原因。
- 面板 (d)：质量加权光致率接近局域值不等于逐点闭合，也不消除频率不收敛。

![Phase 7B4p convergence](../outputs/phase7b4p_convergence.png)

- 面板 (a)：1024 对 2048 的九个时间指标全部低于 $10^{-3}$。
- 面板 (b)：角度误差随 4、8、12、16、24 方向总体下降，12 以上达到当前目标。
- 面板 (c)：总通量和能量矩比原子速率更快收敛；速率的非单调有限差明确禁止把 519 点当
  自动参考极限。
- 面板 (d)：N=62 对 N=64 的 He I/He II 光致率越过目标线，深度门未关闭。

## 8. 最终判据与下一微阶段

| 判据 | 结果 |
|---|---|
| 解析、热力学与形式解守恒 | 通过 |
| 1024 对 2048 轨道相位 | 通过 |
| 正式 4 方向角度配置 | 失败 |
| 16 对 24 扩展角度 | 通过 |
| 正式 71 点频率配置 | 失败 |
| 263 对 519 扩展频率 | 失败 |
| N=62 对 N=64 非局域积分量 | 失败 |
| $t_{\rm diff}/P_{\rm orb}<0.1$ | 失败 |

因此：`[V/O]`

1. 冻结非局域诊断已经完成；
2. 逐相位稳态非局域闭合未获准；
3. 动态辐射储能在物理上是必需的，但当前数值底座尚未获准直接进入该求解；
4. 下一微阶段先重构阈值感知频率求积，并建立 N>64 独立动态深度参考；
5. Phase 4 大气替换和真实 UVOT 卷积继续关闭。

## 9. 文件与复现

核心实现：

- `src/eccentric_tde_observer/nonlocal_dynamic_transfer.py`：完整对称柱、冻结形式解和扩散时标；
- `scripts/phase7b4p_frozen_nonlocal_transfer.py`：全轨道、控制、收敛、图和总报告；
- `tests/test_nonlocal_dynamic_transfer.py`：转移模块控制；
- `tests/test_phase7b4p_frozen_nonlocal_transfer.py`：相位插值、误差、质量积分与禁用修复测试。

主要输出：

- `outputs/phase7b4p_depth64_phase1024_frozen_nonlocal.npz`；
- `outputs/phase7b4p_depth64_phase2048_frozen_nonlocal.npz`；
- `outputs/phase7b4p_controls.csv`；
- `outputs/phase7b4p_convergence.csv`；
- `outputs/phase7b4p_extended_convergence.csv`；
- `outputs/phase7b4p_local_closure.csv`；
- `outputs/phase7b4p_reference_phase.csv`；
- `outputs/phase7b4p_complete_report.json`；
- 本文引用并分析的三张 PNG。

复现命令：

```bash
uv run python scripts/phase7b4p_frozen_nonlocal_transfer.py --stage case --case depth64_phase1024 --workers 8
uv run python scripts/phase7b4p_frozen_nonlocal_transfer.py --stage case --case depth64_phase2048 --workers 8
uv run python scripts/phase7b4p_frozen_nonlocal_transfer.py --stage controls
uv run python scripts/phase7b4p_frozen_nonlocal_transfer.py --stage convergence
uv run python scripts/phase7b4p_frozen_nonlocal_transfer.py --stage extended
uv run python scripts/phase7b4p_frozen_nonlocal_transfer.py --stage summary
```

相关入口：[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]] ·
[[eccentric_tde_observer/lecture/项目讲义/00_document_map|文档地图]]。
