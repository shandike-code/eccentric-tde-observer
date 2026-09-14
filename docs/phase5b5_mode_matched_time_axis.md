# Phase 5B5：模形绑定的候选拱点时间轴

上游：[[phase5b4_strict_domain_candidate_timescale_gate|Phase 5B4 严格域候选时标]] ·
[[phase5b4a_cross_platform_audit|Phase 5B4a 跨平台复算]]  
下游：若明确采用方程自洽候选，必须用同一 $e(a)$ 重建源端 atlas。

> `[V]` 已实现并通过一个带径向模形哈希的拱点时间钟。对与本征模逐字同源的候选源，
> $\Phi$ 可以换成相对天数；对现有常偏心 Phase 4/5/6 atlas，接口会因模形哈希不同而
> 拒绝。`[O]` 这还没有给旧 atlas 加 day 轴，也没有提供绝对历元。

## 1. 相位到时间的物理关系

若 $\widetilde{\omega}$ 是以偏心通信时间 $t_{\rm ecc}$ 归一化的有符号角频率，则

$$
\Phi(t)
=
\left[
\Phi_{0}
+
\frac{\widetilde{\omega}}{t_{\rm ecc}}(t-t_{0})
\right]_{2\pi},
$$

以及

$$
P_{\rm aps}
=
\frac{2\pi t_{\rm ecc}}{|\widetilde{\omega}|}.
$$

代码保留 $\widetilde{\omega}$ 的符号，因此顺行和逆行不会被绝对值误合并；只有周期长度
使用绝对值。解析测试回收整周期、负频率和相位--时间往返关系。`[L/V]`

## 2. 为什么时间钟必须绑定 $e(a)$

本征问题同时给出 $\widetilde{\omega}$ 和 $e_{\rm mode}(a)$。Phase 5B5 对
$(a/a_{\rm in},e)$ 的 binary64 数组计算 SHA-256 指纹；只有观察者源的指纹与本征模指纹
完全相同，才构造时间钟。这个门没有可调容差，也不会把“形状大致相似”当成同一个动力学
状态。`[A-interface/V]`

现有 atlas 使用常偏心剖面，而候选模在外缘只剩内缘的 $36.2\%$--$37.2\%$。两个常偏心
指纹均被接口拒绝；因此输出 CSV 中每一行都明确标记
`existing_constant_e_atlas_row=false`。`[V]`

## 3. 候选相对时间表

直接 Eqs. (9)--(12)、(39) 账本的 $t_{\rm ecc}=3891.3693\,\mathrm{day}$ 给出：

| 候选 | $\widetilde{\omega}$ | $P_{\rm aps}$ | 频率 |
|---|---:|---:|---:|
| $e_{\rm in}=0.60$ | $1.640149718$ | $14907.294\,\mathrm{day}$ | $6.70813\times10^{-5}\,\mathrm{cycle\,day^{-1}}$ |
| $e_{\rm in}=0.65$ | $1.559376886$ | $15679.464\,\mathrm{day}$ | $6.37777\times10^{-5}\,\mathrm{cycle\,day^{-1}}$ |

相位往返最大误差为 $8.88\times10^{-16}\,\mathrm{rad}$，周期逐位回收 Phase 5B4 的直接
账本。`outputs/phase5b5_mode_matched_phase_schedule.csv` 为两条候选各输出
$0^{\circ}$ 到 $345^{\circ}$、步长 $15^{\circ}$ 的相对天数。`[V]`

没有给定 $t_{0}$ 的真实日历日期，故这些是相对时间，不是某个具体 TDE 的 MJD；项目也
没有为匹配事件时长选择历元。`[A/O]`

## 4. 图像与解释

![Phase 5B5 mode-matched apsidal time axis](../outputs/phase5b5_mode_matched_time_axis.png)

**左图。** 两条彩色曲线是方程自洽候选 $e(a)/e_{\rm in}$，黑虚线是常偏心 atlas。
明显的径向分离说明拒绝来自源模形不一致，不是时间单位换算误差。`[V]`

**右图。** 实线是直接 Eq. (39) 候选的相位--相对天数；点线保留 Eq. (48) 印刷归一化
审计。点线短约十倍，但没有被采用，也不能因为更接近 TDE 观测时长而选择。`[L/V/O]`

## 5. 当前决策

- 模形匹配候选的 $\Phi\leftrightarrow t-t_{0}$ 接口：通过；
- 现有常偏心 atlas 的时间映射：拒绝；
- Eq. (48) 印刷归一化：仅保留审计，不采用；
- 绝对历元：未提供；
- 方程自洽候选源重建：尚未获明确采用；
- Phase 4 替换、UVOT 和真实线形成：均未因此授权。`[V/O]`

若后续明确采用方程自洽但非 published benchmark 的候选，必须把同一
$e_{\rm mode}(a)$ 接入 ZO 源端，重新验证有效域、连续谱、观察者 atlas 和 Phase 6 线核；
不能复用当前常偏心图后只改横轴。原作者 Fig. 6/7 数据请求仍是关闭 published benchmark
的独立路径。`[O]`

## 6. 复现

    python scripts/phase5b5_mode_matched_time_axis.py
    python -m pytest -q tests/test_apsidal_time_mapping.py \
      tests/test_phase5b5_mode_matched_time_axis.py

核心接口位于 `src/eccentric_tde_observer/apsidal_time_mapping.py`；机器可读结论位于
`outputs/phase5b5_mode_matched_time_axis_summary.json`。

