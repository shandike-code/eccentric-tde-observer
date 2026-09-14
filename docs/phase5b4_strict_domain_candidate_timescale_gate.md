# Phase 5B4：严格域候选进动时标与模形兼容门

## 1. 结论先行

Phase 5B4 已对现有严格域源的参数

$$
\mathcal V=0.01,
\qquad
\frac{a_{\rm out}}{a_{\rm in}}=2,
\qquad
e_{\rm in}=0.60
$$

以及边界敏感性案例 $e_{\rm in}=0.65$，求出方程自洽的三维非线性无节点拱点模。[V]

两层结论必须分开：

- [V] **候选时标可计算**：高偏心 Hamiltonian、双端 BVP、射击互证和直接量纲账本通过；
- [O] **现有 atlas 不能加 day 轴**：候选模的 $e(a)$ 强烈下降，而 Phase 4/5/6 atlas
  使用的是常偏心 $e(a)=0.6$ 源；两者不是同一动力学状态。

此外，Phase 5B3a 的 ZO Figs. 6--7 published benchmark 仍未关闭。因此本阶段只把周期
命名为 equation-self-consistent candidate period，不称为正式 ZO benchmark period。[A/O]

## 2. 为什么不能只算一个频率

现有连续谱和线核运动学源取

$$
e_{\rm atlas}(a)=e_{\rm in}.
$$

但自由边界非线性本征问题同时决定 $\widetilde{\omega}$ 和 $e_{\rm mode}(a)$。若只把
$\widetilde{\omega}$ 贴到旧 atlas，而忽略两者的模形差异，就把一个动力学状态的周期配给
另一个几何与速度场。这不属于坐标换算，而是源模型不一致。[V/O]

因此本阶段同时设置：

1. 高偏心方程内部门；
2. Eqs. (9)--(12)、(39) 直接物理单位门；
3. 候选模与常偏心 atlas 的形状兼容门；
4. inherited published benchmark 门。

只有四者都通过，$\Phi$ 才能正式换成 $t$。[A-classification]

## 3. 高偏心数值门

Hamiltonian 表覆盖

$$
0\le e\le0.75,
\qquad
-0.75\le q\le0.25,
$$

并使用三档分辨率：

| $N_{e}\times N_{q}$ | 异常角点数 | $e_{\rm in}=0.60$ 的 $\widetilde{\omega}$ | $e_{\rm in}=0.65$ 的 $\widetilde{\omega}$ |
|---:|---:|---:|---:|
| $21\times41$ | 128 | $1.640146459$ | $1.559367056$ |
| $31\times61$ | 192 | $1.640149260$ | $1.559376675$ |
| $41\times81$ | 192 | $1.640149718$ | $1.559376886$ |

粗到细的最大频率相对变化为 $6.30\times10^{-6}$，最大外边界偏心率相对变化为
$3.87\times10^{-6}$。[V]

### 3.1 被保留的偏导失败

$31\times61$ 表在 $e_{\rm in}=0.65$ 内边界的样条偏导向量与直接五点呼吸偏导相差
$1.866\times10^{-3}$，超过预声明 $10^{-3}$ 门。这个失败没有被删除或通过改变差分步长
掩盖。[V]

完整矩形域加密到 $41\times81$ 后，同一点误差降到 $2.023\times10^{-4}$；最终六个
内、中、外留出点的最大误差为 $2.774\times10^{-4}$。三档原始 $F(e,q)$ 表值均保存在
NPZ 中，缓存坐标若不完全一致会直接拒绝复用。[V]

### 3.2 两个全局求解器

在最终表上，射击法与配点 BVP 的最大频率相对差为
$1.09\times10^{-8}$，最大外边界偏心率相对差为 $1.62\times10^{-8}$；配点解的最大绝对
外边界残差为 $4.23\times10^{-17}$。[V]

射击互证只在配点根附近构造符号括区。更宽的试探上界曾把轨迹带出声明表域并被拒绝；
程序没有为使射击成功而外推 Hamiltonian。[V]

## 4. 候选时标的直接单位账本

对 $\mathcal V=0.01$，Eqs. (9)--(12)、(39) 直接给出

$$
t_{\rm ecc}=3.36214308\times10^{8}\ {\rm s}
=3891.3693\ {\rm day},
$$

$$
\delta_{\rm GR}=0.7794829,
\qquad
\frac{\widetilde{\omega}}{2\pi t_{\rm ecc}}
=
\widetilde{\omega}
\left(4.0899470\times10^{-5}\right)
\ {\rm cycle\,day^{-1}}.
$$

最终候选为：

| 案例 | $\widetilde{\omega}$ | 直接 Eqs. (9)--(12)、(39) 周期 | Eq. (48) 印刷周期 |
|---|---:|---:|---:|
| $e_{\rm in}=0.60$ | $1.640149718$ | $14907.29\ {\rm day}$ | $1490.60\ {\rm day}$ |
| $e_{\rm in}=0.65$ | $1.559376886$ | $15679.46\ {\rm day}$ | $1567.81\ {\rm day}$ |

Eq. (48) 印刷频率仍比直接账本高 $10.0008615$ 倍。两列不是两种可自由选择的模型；本阶段
只采用直接账本作为 candidate，保留 Eq. (48) 作为未解决的文献归一化审计。[L/V/O]

若暂看 candidate 数值，周期约为 40.8--42.9 年；这意味着数月到数年的 TDE 观测窗只覆盖
很小的拱点相位。但因模形与 published 门均未闭合，这还不是可发布时域预言。[A/O]

## 5. 模形兼容门为什么失败

最终解为：

| 案例 | $e_{\rm in}$ | $e_{\rm out}$ | $e_{\rm out}/e_{\rm in}$ | 相对常偏心形状最大差 |
|---|---:|---:|---:|---:|
| atlas reference | $0.60$ | $0.217132$ | $0.361886$ | $0.638114$ |
| boundary sensitivity | $0.65$ | $0.241924$ | $0.372191$ | $0.627809$ |

对预声明的 $2\%,5\%,10\%$ 三档 [A-classification] 形状阈值，两种源均失败。结论不依赖
选择其中某一个阈值，因为最小实际差异仍超过 $62\%$。[A/V]

## 6. 图像与逐图解释

### 6.1 候选模与常偏心 atlas

![Mode-shape compatibility](../outputs/phase5b4_mode_shape_compatibility.png)

**怎么看。** 左图把候选本征函数除以内边界偏心率；黑虚线是现有常偏心 atlas。右图画
同一解的轨道非线性 $q$。

**验证了什么。** [V] 两个候选模都从内缘快速下降，外缘只剩约 $36\%$--$37\%$；它们的
径向压缩也随半长轴显著变化。模形差异不是图线厚度或小幅插值误差。

**不能证明什么。** [O] 该图不说明常偏心控制在连续谱研究中“无效”；它只说明不能把
另一条自由边界本征模的周期直接分配给这个控制源。

### 6.2 候选频率与归一化账本

![Candidate timescale ledger](../outputs/phase5b4_candidate_timescale_ledger.png)

**怎么看。** 左图是两个方程自洽无量纲候选频率；右图同时画直接 Eq. (39) 账本和
Eq. (48) 印刷归一化得到的周期。

**验证了什么。** [V] 边界敏感性从 $e_{\rm in}=0.60$ 到 $0.65$ 只令候选周期增加约
$5.18\%$，而两种物理归一化之间保持十倍差异。

**不能证明什么。** [L/O] 橙柱不能作为“更接近 TDE 寿命”的选择而被采用；published
归一化和 Fig. 6/7 分支都没有被本项目复现。

## 7. 公开代码检索与外部依赖

论文网页的 Data Availability 明确写明底层数据可向通讯作者合理索取，但没有给出公开
代码仓库；arXiv 源包也只含论文源文件、图和审稿往来。[L/V]

[ZO 2020 论文及 Data Availability](https://academic.oup.com/mnras/article/499/4/5562/5922725)

向作者发送请求属于外部协调，本阶段当时没有代用户发送邮件；后续已按用户授权于
2026-08-30 发送唯一一封请求，当前等待回复。[V/O]

## 8. 阶段判定与下一步

- [V] 高偏心三维方程内部门通过；
- [V] 直接物理账本给出约 $1.49$--$1.57\times10^{4}\ {\rm day}$ 的候选周期；
- [O] published Fig. 6/7 与 Eq. (48) 基准仍未闭合；
- [V] 候选 $e(a)$ 与现有常偏心 atlas 的形状兼容门失败；
- [O] 现有 Phase 4/5/6 的 $\Phi$ 仍不能正式换成 day。

下一步若继续动力学支路，必须先做选择：

1. 取得原作者代码并关闭 published benchmark；或
2. 明确接受“方程自洽但非 published benchmark”的新动力学基准，再用候选 $e(a)$ 重建
   ZO 源、重新运行有效域、连续谱、观察者图谱和线核。

第二条不是给旧 atlas 加时间标签，而是一个新的、从源端开始的阶段，不能静默执行。[O]

## 9. 复现

    uv run python scripts/phase5b4_strict_domain_candidate_timescale_gate.py
    uv run pytest -q tests/test_phase5b4_strict_domain_candidate_timescale_gate.py

本阶段完成后的现场聚焦回归为 49 passed，完整回归为 580 passed。[V]

后续 Windows 独立复算与 macOS 逐表对照见
[[eccentric_tde_observer/docs/phase5b4a_cross_platform_audit|Phase 5B4a]]；该对照增强方程
自洽候选的数值复现证据，但不改变本页的 published benchmark 与 atlas 时间映射判定。[V/O]

阶段关系见
[[eccentric_tde_observer/docs/phase5b3a_published_branch_inverse_audit|Phase 5B3a]]、
[[eccentric_tde_observer/docs/phase1i_strict_domain_spectra|Phase 1I]]和
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]。
