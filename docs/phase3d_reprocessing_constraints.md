# Phase 3D：最小再处理层的守恒约束（未加入盘风）

## 目的

裸盘的 high-energy 局域谱尚未通过 NLTE 大气闭合，因此本阶段不能合理地“加一个风再拟合”。
Phase 3D 只画出任何未来再处理层必须满足的约束面。

定义 $\epsilon=\kappa_{\rm abs}/\kappa_{\rm tot}$。在散射主导层中，若要求 $\tau_{\rm eff}=1$，则

$\tau_{\rm tot,\rm min} = 1/\sqrt(3 \epsilon)$，

$\Sigma_{\rm min} = \tau_{\rm tot,\rm min}\,(1-\epsilon)/\kappa_{\rm es}$，

$M_{\rm min} = 4\,\pi\,R^2\,C\,\Sigma_{\rm min}$，

$t_{\rm diff} = \tau_{\rm tot}\,(\Delta R)/c$。

输出质量默认写为 $C=1$ 的系数，实际质量乘覆盖因子 $C$；扩散时间写为每单位
$\Delta R/R$ 的系数。因此代码没有暗中选择覆盖率或层厚。

能量和动量约束分别为

$L_{\rm seed} \ge L_{\rm rep}/(C\,f_{\rm abs})$，

$Mdot\,v \le \tau_{\rm mom}\,L_{\rm seed}/c$。

## 数值标度

在 $R=1e14 cm$：

| $\epsilon$ | $\tau_{\rm tot,\rm min}$ | $\Sigma_{\rm min}$ [g cm^-2] | $M_{\rm min}(C=1)$ [Msun] | $t_{\rm diff}/(DeltaR/R)$ [day] |
|---:|---:|---:|---:|---:|
| $1e-6$ | 577.35 | 1698.1 | 0.1073 | 22.29 |
| $1e-5$ | 182.57 | 537.0 | 0.0339 | 7.05 |
| $1e-4$ | 57.74 | 169.8 | 0.0107 | 2.23 |
| $1e-3$ | 18.26 | 53.64 | 0.00339 | 0.705 |
| $1e-2$ | 5.77 | 16.81 | 0.00106 | 0.223 |

质量随 $R^2$ 增长；到 $1e15 cm$ 增加 100 倍。若把当前最大保守 optical band 的
$1.047e42 erg/s$ 假定为需再处理的目标，即使 $C=1$、完全吸收，也需至少同等的有效
高能种子光度；当前裸盘没有通过有效性门的 X-ray 种子谱，故能量闭合无法检验。

## 决策

- `[V]` 约束公式、半径标度、能量等式和动量等式有解析测试；
- `[O]` $\epsilon$ 实际由 NLTE 离化态决定，不能自由挑选；
- `[O]` 没有高能种子谱时，再处理模型缺少能量源；
- 因此本阶段**不实例化再处理层，也不加入盘风**。只有裸盘在有效频段定量失败、并补上
  高能源与离化结构之后，才能从这张约束面选择物理允许区。

代码：`src/eccentric_tde_observer/reprocessing.py`；数据：
`outputs/phase3_reprocessing_constraints.csv`。

