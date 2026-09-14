# Phase 5B6：方程自洽候选源

上游：[[phase5b4_strict_domain_candidate_timescale_gate|Phase 5B4 严格域候选时标]] ·
[[phase5b5_mode_matched_time_axis|Phase 5B5 模形绑定时间轴]]  
后续：候选有效域的网格收敛、候选连续谱、观察者 atlas 与线核复算。

> `[A-candidate]` 用户已批准把两条方程自洽模形作为新的**候选基准**继续推进。
> `[V]` Phase 5B6 已把冻结的 $e(a)$ 和 $q(a)$ 构造成独立
> `ZOSourceGrid`。`[O]` 它们仍不是 Zanazzi & Ogilvie 论文的已发表数值
> benchmark，也没有替换旧常偏心控制。

## 1. 为什么要建立独立候选分支

Phase 5B4 的高偏心本征解沿半长轴明显下降：外缘偏心率仅为内缘的
$36.2\%$--$37.2\%$。因此不能把该本征频率直接贴到常偏心观察者 atlas 上。
Phase 5B6 从同一条径向模形重新建立源场，而
`build_zo_constant_e_reference_model` 保持不变，继续承担历史回归和圆盘极限控制。
`[V]`

现有 Phase 5B5 报告中的 `candidate_mode_source_rebuild_authorized=false` 是用户批准前的
历史状态；本阶段用新的机器可读报告记录批准，不反向改写旧审计产物。`[A-decision]`

## 2. 两级逐字指纹

既有 Phase 5B5 指纹绑定 binary64 数组 $(a/a_{\rm in},e)$。仅绑定 $e(a)$ 仍不足以
唯一决定垂向源，因为轨道 Jacobian 和呼吸解还依赖

$$
f(a)=e+a\frac{{\rm d}e}{{\rm d}a}.
$$

Phase 5B4 CSV 同时保存 ZO 轨道非线性参数

$$
q=\frac{f-e}{1-ef}.
$$

构造器不数值微分 $e(a)$，而是逐点精确反解

$$
f=\frac{q+e}{1+qe}.
$$

因此接口同时要求：

- $(a/a_{\rm in},e)$ 的既有 SHA-256 指纹逐字匹配；
- $(a/a_{\rm in},e,q)$ 的新增 SHA-256 指纹逐字匹配。

任一 binary64 值改变一个 representable step，测试都会拒绝建源。这里没有容差匹配、
插值、裁剪或事后重归一化。`[V]`

## 3. 源场构造

候选保持无扭曲条件 ${\rm d}\varpi/{\rm d}a=0$。每个径向点独立求解 ZO Eq. (35)
的正、偶、周期呼吸支 $h(a,E)$，并使用 ZO Eq. (31)

$$
j(a,E)
=
\frac{
1-e f-(f-e)\cos E
}{\sqrt{1-e^2}}.
$$

随后沿用原 ZO 源定义

$$
\Sigma(a,E)=\frac{\Sigma_{\rm circ}(a)}{j(a,E)},
\qquad
H(a,E)=H_{\rm circ}(a)h(a,E),
$$

以及 ZO Eq. (55)

$$
T_{\rm eff}(a,E)
\propto
\left(\frac{a}{a_{\rm in}}\right)^{-1/2}
j(a,E)^{-1/12}
h(a,E)^{-1/3}.
$$

这里没有重新定义 ZO 动力学场。辐射积分仍由下游统一使用 Erratum 修正面积

$$
{\rm d}A_{\rm corr}
=
a\,j(a,E)\left(1-e(a)\cos E\right){\rm d}a\,{\rm d}E.
$$

`[L/V]`

## 4. 首次候选源结果

固定参数为 $M_{\rm BH}=10^6\,M_{\odot}$、$M_{\star}=1\,M_{\odot}$、
$R_{\star}=1\,R_{\odot}$、$\mathcal{V}=0.01$ 和
$\kappa=0.34\,{\rm cm^2\,g^{-1}}$；源网格为 $256\times128$。`[A/V]`

| 候选 | $e_{\rm in}\rightarrow e_{\rm out}$ | $\min j\rightarrow\max j$ | $\min h\rightarrow\max h$ | $T_{\rm eff}$ 范围 | corrected face-on $L_{\rm bol,\rm iso}$ |
|---|---:|---:|---:|---:|---:|
| atlas reference | $0.600\rightarrow0.217$ | $0.461\rightarrow2.158$ | $0.0186\rightarrow2.025$ | $9.33\times10^3$--$5.29\times10^4\,{\rm K}$ | $1.003\times10^{43}\,{\rm erg\,s^{-1}}$ |
| strict boundary sensitivity | $0.650\rightarrow0.242$ | $0.432\rightarrow2.305$ | $0.00618\rightarrow2.020$ | $9.24\times10^3$--$7.60\times10^4\,{\rm K}$ | $1.173\times10^{43}\,{\rm erg\,s^{-1}}$ |

两条源的 $j$、$\Sigma$、$H$ 和 $T_{\rm eff}$ 全部有限且严格为正，独立嵌套轨道检查
通过。表中的光度是 corrected face-on 各向同性等效 bolometric 光度，不是盘的双面本征
光度。`[V]`

## 5. 有效域接口的首次执行

候选源已直接通过通用 `audit_local_vertical_domain`，没有复制或修改 Phase 1H 判据。
在当前 $256\times128$ 网格上：

- $e_{\rm in}=0.60$：Gaussian 和 $n=3$ polytrope 两种闭合中，满足
  $z_{\rm ph}/r\geq0.3$ 的 corrected 面积分数均为 $0$；
- $e_{\rm in}=0.65$：Gaussian 为 $8.10\times10^{-3}$，$n=3$ polytrope 为 $0$；
- 两条候选在两种闭合中满足 $z_{\rm ph}/r\geq1$ 的 corrected 面积分数均为 $0$；
- 最小总垂向光深分别为 $42.21$ 和 $40.87$，显式光球网格均保持向上、单值。

因此两条候选在这次原生网格检查中都满足 Phase 1H 的工作阈值：“两种闭合中
$z_{\rm ph}/r\geq0.3$ 的 corrected 面积分数不超过 $1\%$”。但是该阈值属于
`[A-domain]`，不是文献定理；本阶段还没有完成径向、偏近心点和表面三角网格的独立
收敛扫描，所以机器报告保留
`formal_candidate_validity_convergence_closed=false`。`[V/O]`

## 6. 图像与逐图解释

![Phase 5B6 candidate source diagnostics](../outputs/phase5b6_candidate_source_diagnostics.png)

**(a) Frozen candidate profiles.** 两条 $e(a)$ 都从内缘向外单调下降；这正是它们不能
与常偏心 atlas 共用动力学时钟的源端原因。`[V]`

**(b) Jacobian envelope.** 实线和虚线分别给出每个半长轴上的 $j$ 最小值与最大值。
整个包络严格为正，说明没有用裁剪掩盖轨道交叉。内缘振幅最大，与较强的近心点压缩
一致。`[V]`

**(c) Local vertical aspect ratio.** 实线为近心点，虚线为远心点。近心点压缩使
$H/r$ 显著降低；远心点曲线较厚，但当前候选仍保持局域薄柱。`[V]`

**(d) ZO Eq. (55) temperature.** 近心点压缩使内缘温度升高，$e_{\rm in}=0.65$ 候选
最明显；远心点温度低且两条候选接近。该温度仍是 ZO 扩散/LTE 源闭合，不应解释成
已完成的 NLTE 大气谱。`[L/V/O]`

## 7. 当前边界与下一门

- `[L]` 源场方程来自 ZO Eqs. (10)、(16)、(18)、(31)、(35)、(55)；
- `[V]` 两级指纹、$q\rightarrow f$、正 Jacobian、常偏心极限和通用有效域接口均有测试；
- `[A-candidate]` 两条剖面被批准作为后续候选基准，但不冒充 published benchmark；
- `[O]` 正式有效域网格收敛、候选连续谱收敛、观察者 atlas 和 Phase 6 线核尚待重跑；
- `[O]` 局域黑体或后续大气闭合、NLTE 能级布居和真实线转移不由本阶段解决。

下一步应先关闭候选有效域收敛门，再生成候选连续谱与观察者结果；不能只把旧图的标签
换成 $e(a)$。旧常偏心分支继续保留作圆盘极限、历史回归和对照。`[V/O]`

## 8. 复现

    .venv/bin/python scripts/phase5b6_equation_self_consistent_candidate_source.py
    .venv/bin/python -m pytest -q tests/test_zo_candidate_source.py \
      tests/test_zo_reference.py tests/test_validity.py

核心接口位于 `src/eccentric_tde_observer/zo_candidate_source.py`；机器可读结论位于
`outputs/phase5b6_candidate_source_report.json`，径向诊断位于
`outputs/phase5b6_candidate_source_radial_diagnostics.csv`。
