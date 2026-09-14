# Phase 5B8：有效候选源的拱点相位—相对物理时间映射

上游：[[phase5b4_strict_domain_candidate_timescale_gate|Phase 5B4 候选本征值]] ·
[[phase5b5_mode_matched_time_axis|Phase 5B5 模形绑定时间钟]] ·
[[phase5b6_equation_self_consistent_candidate_source|Phase 5B6 候选源]] ·
[[phase5b7_candidate_validity_convergence|Phase 5B7 有效域收敛门]]

> `[V]` Phase 5B8 已把通过有效域门的两条方程自洽候选源与各自的本征频率逐字绑定，
> 因而候选源自身的相位 $\Phi$ 可以换算为相对物理时间。
> `[O]` 这不是绝对日历历表，也不是 published ZO benchmark；旧常偏心 Phase 4/5/6
> atlas 仍不得加上该时间轴。

## 1. 本阶段关闭了哪一条链

Phase 5B4 同时给出无量纲本征角频率 $\widetilde{\omega}$、偏心模形 $e(a)$ 和轨道
非线性 $q(a)$。Phase 5B6 用同一组 $(a,e,q)$ 构造候选源，Phase 5B7 再验证候选源的
局域有效域收敛。Phase 5B8 要求以下条件全部成立：

1. Phase 5B4--5B7 的输入文件 SHA-256 与各自冻结来源一致；
2. 本征解和候选源的 $(a,e)$ 指纹逐字相同；
3. 决定 Jacobian 与垂向呼吸解的 $(a,e,q)$ 指纹也逐字相同；
4. 候选有效域收敛门已经关闭；
5. 时间归一化由候选物理参数重新计算，而不是从周期列反推；
6. `published_benchmark=false`，且不能由调用者改写为真。

因此，这里授权的是“同一候选动力学状态的相位—时间映射”，不是给任意偏心盘分配一个
周期。`[A-interface/V]`

## 2. 物理归一化

对当前候选采用的尺度

$$
M_{\rm BH}=10^{6}\,M_{\odot},
\qquad
M_{\star}=1\,M_{\odot},
\qquad
R_{\star}=1\,R_{\odot},
\qquad
\mathcal{V}=0.01,
\qquad
\frac{a_{\rm out}}{a_{\rm in}}=2,
$$

程序按 ZO Eqs. (9)--(12)、(39)--(40) 独立重算

$$
t_{\rm ecc}
=
\frac{n_{\rm in}a_{\rm in}^{2}}
{(\gamma-1)\varepsilon_{\rm in}}
=
3.36214308\times10^{8}\,{\rm s}
=
3891.369307\,{\rm day},
$$

以及

$$
\omega_{\rm aps}
=
\frac{\widetilde{\omega}}{t_{\rm ecc}},
\qquad
P_{\rm aps}
=
\frac{2\pi t_{\rm ecc}}{|\widetilde{\omega}|}.
$$

重算的 $t_{\rm ecc}$、$\delta_{\rm GR}$ 和 $a_{\rm in}$ 与 5B4/5B6 账本的最大相对差
低于 $2\times10^{-13}$。这里的质量、半径与 $\mathcal{V}$ 是当前候选采用的
`[A-scale]` 输入，不是对具体 TDE 的拟合。`[L/A/V]`

## 3. 从相位换成相对时间

采用有符号频率时，时间钟为

$$
\Phi(t)
=
\Phi_{0}
+
\frac{\widetilde{\omega}}{t_{\rm ecc}}
(t-t_{0}).
$$

本阶段只设

$$
\Phi_{0}=0,
\qquad
t-t_{0}=0,
$$

作为坐标原点 `[A-origin]`。没有输入某个事件的 MJD，故表中的天数全部是相对时间；
它们不能被称为绝对观测日期。若未来给出物理上有依据的 $t_{0}$ 与 $\Phi_{0}$，核心接口
可以保留频率符号并平移原点，无需改变候选周期。`[A/O]`

## 4. 数值结果

| 候选 | $\widetilde{\omega}$ | $P_{\rm aps}$ | 每年相位推进 | 每 $15^{\circ}$ 所需时间 |
|---|---:|---:|---:|---:|
| $e_{\rm in}=0.60$ | $1.640149718$ | $14907.294246\,{\rm day}=40.81395\,{\rm yr}$ | $8.82051^{\circ}$ | $621.13726\,{\rm day}$ |
| $e_{\rm in}=0.65$ | $1.559376886$ | $15679.464460\,{\rm day}=42.92803\,{\rm yr}$ | $8.38613^{\circ}$ | $653.31102\,{\rm day}$ |

相位—时间往返的最大绝对误差为 $8.88\times10^{-16}\,{\rm rad}$，两条周期都逐位回收
Phase 5B4 的直接 Eq. (39) 账本。`[V]`

这也给出一个直接的观测含义：在该 `[A-candidate]` 归一化下，一年只扫过约
$8.4^{\circ}$--$8.8^{\circ}$，因此原先 $15^{\circ}$ 的 atlas 方位网格在时间上相隔约
$1.70$--$1.79\,{\rm yr}$。这不是说真实 TDE 必然以该速率进动，而是候选尺度的可检验
推论。`[A/V/O]`

## 5. 图像与解释

![Phase 5B8 candidate-source apsidal time mapping](../outputs/phase5b8_candidate_source_time_mapping.png)

**左图。** 横轴是候选源的拱点相位，纵轴是从 $\Phi=0$ 开始的相对年数。两条近直线
来自固定的全局本征频率；达到 $345^{\circ}$ 分别需要约 $39.1$ 年和 $41.1$ 年。`[V]`

**右图。** 横轴仅展示十年窗口，纵轴是不取模的累计相位。十年内两条候选分别推进约
$88.2^{\circ}$ 与 $83.9^{\circ}$。两条线的差异来自各自独立求得的本征值，并非人为调整
相位速度。`[V]`

**不能从图中推出什么。** 图中没有绝对历元，也没有使用观测光变或谱线拟合确定
$\Phi_{0}$；它不能说明某一真实事件在某日处于哪个方位。图也没有关闭 ZO Fig. 6/7 与
印刷 Eq. (48) 的约十倍归一化差异。`[O]`

## 6. 正式判定与未闭合项

- `[V]` 两条通过有效域门的候选源可以使用各自的相对物理时间钟；
- `[V]` 未来候选观察者结果只有携带完全相同的 $(a,e,q)$ 指纹时才能引用该时间轴；
- `[V/O]` 旧常偏心 Phase 4/5/6 atlas 与候选模形不同，仍禁止换成 day；
- `[A-candidate]` 采用直接 Eqs. (9)--(12)、(39)--(40) 账本作为候选归一化；
- `[O]` published ZO Fig. 6/7 benchmark 与印刷 Eq. (48) 归一化仍未关闭；
- `[O]` 没有绝对 $t_{0}$、$\Phi_{0}$ 或具体事件 MJD；
- `[O]` 本阶段不改变连续谱、辐射闭合或真实线形成的状态。

因此，“把 $\Phi$ 变成真实时间”在当前证据下应准确表述为：**方程自洽候选源的
相对物理时间尺度已闭合；published benchmark 与绝对观测历元尚未闭合。**

## 7. 复现

    .venv/bin/python scripts/phase5b8_candidate_source_time_mapping.py
    .venv/bin/python -m pytest -q \
      tests/test_candidate_apsidal_ephemeris.py \
      tests/test_apsidal_time_mapping.py \
      tests/test_phase5b5_mode_matched_time_axis.py \
      tests/test_zo_candidate_source.py \
      tests/test_phase5b7_candidate_validity_convergence.py \
      tests/test_phase5b8_candidate_source_time_mapping.py

核心接口位于 `src/eccentric_tde_observer/candidate_apsidal_ephemeris.py`；机器可读账本位于
`outputs/phase5b8_candidate_source_time_mapping_report.json`，$15^{\circ}$ 网格时间表位于
`outputs/phase5b8_candidate_source_phase_schedule.csv`。
