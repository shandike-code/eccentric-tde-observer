# 阶段 2A：裸偏心盘的弱场频移光谱

本阶段在阶段 1I 的严格局域域模型上加入第一层频移映射，并输出远方观察者的
$F_{\nu}$ 和 $\nu F_{\nu}$。ZO 的 $\Sigma,H,T_{\rm eff}$ 没有被重调；没有加入盘风、自由再处理层、
吸收边或发射线。

## 1. 四类内容

### [L] ZO 已确定的源量

固定源为

$M_{\rm BH}=10^6 M_{\rm sun}, e=0.6, V=0.01, a_{\rm out}/a_{\rm in}=2$，源网格为
$65 x 1024$。$\Sigma,H,T_{\rm eff}$ 和垂向呼吸函数 $h(E)$ 仍来自阶段 1E 已核对的
ZO Eqs. (10,16,18,31,35,55)。有限 $n=3$ 垂向剖面来自
Lynch--Ogilvie 2021 Appendix A。

### [A] 新的弱场运动学和转移闭合

在近心点坐标系中采用 Newtonian Kepler 速度

$$
{dE\over dt}={\sqrt{GM/a^3}\over 1-e\cos E},
$$

$$
v_{x}={-a\sqrt{GM/a^3}\sin E\over1-e\cos E},\qquad
v_{y}={a\sqrt{GM/a^3}\sqrt{1-e^2}\cos E\over1-e\cos E},
$$

再整体旋转 $\varpi$。ZO 的齐次垂向呼吸速度单独计算为

$$
v_{z}=z_{\rm ph}{d\ln h\over dE}{dE\over dt}.
$$

对从源指向观察者的单位向量 $n$，采用

$$
g\equiv{\nu_{\rm obs}\over\nu_{\rm em}}
={\sqrt{1-2GM/(rc^2)}\over
\gamma\left(1-\boldsymbol\beta\cdot\boldsymbol n\right)}.
$$

它是 Schwarzschild lapse 与局域特殊相对论 Doppler 的乘积，但轨道和射线仍是
Newtonian/直线的。因此它是明确的弱场工作闭合，不是完整 GR transfer function。

### [L/A] 辐射不变量

标准真空转移使用 $I_{\nu}/\nu^3$ 不变量：

$$
I_{\nu_{\rm obs}}=g^3I_{\nu_{\rm em}}(\nu_{\rm obs}/g).
$$

对局域黑体，这等价于

$$
g^3B_{\nu_{\rm obs}/g}(T_{\rm eff})
=B_{\nu_{\rm obs}}(gT_{\rm eff}).
$$

代码直接使用右式，没有改变源端 $T_{\rm eff}$；$gT_{\rm eff}$ 只是观察者频谱中的等价变量。

### [V] 可观测输出

每个方向仍由可见源三角形求积：

$$
F_{\nu_{\rm obs}}={1\over D^2}
\sum_{k} w_{k,\perp}
B_{\nu_{\rm obs}}(g_{\rm kT}_{{\rm eff},k}),
\qquad D=100\ {\rm Mpc}.
$$

计算 $i=0,30,60,75^\circ$，非零倾角的相对进动相位
$\Phi=\phi_{\rm obs}-\varpi=0--330^\circ$，步长 $30^\circ$。

## 2. [V] 频移尺度

- 最大轨道 $\beta=0.041413$；加入垂向呼吸后为 $0.041451$；
- 最大绝对垂向速度为 $2.14e8 cm s^-1$；
- 全部可见点和方向的 $g$ 范围为 $0.9591--1.04035$；
- 投影面积加权平均 $g$ 的方向范围仅为 $0.99731--1.00203$。

单点可有约 4% 红/蓝移，但同一盘面上的趋近和远离区大幅抵消。因此靠近谱峰的
积分通量变化温和；在 Wien 尾，指数放大会显著增强频移效应。

## 3. [V] 实际 $F_{\nu}$ 图像与峰值

完整频移模型给出：

| 方向 | $\nu F_{\nu}$ 峰频 [Hz] | 峰值 [erg s^-1 cm^-2] |
|---|---:|---:|
| face-on | $1.540e15$ | $3.007e-12$ |
| $i=75, \Phi=0$ | $1.257e15$ | $9.090e-13$ |
| $i=75, \Phi=90$ | $1.704e15$ | $8.469e-13$ |
| $i=75, \Phi=180$ | $1.885e15$ | $6.997e-13$ |
| $i=75, \Phi=270$ | $1.391e15$ | $7.256e-13$ |

图的上排前两格是实际 $\nu F_{\nu}$，不是总光度或任意归一化谱。

## 4. [V] 频移的色依赖与进动预言

全部方向中，完整频移相对无频移通量的范围为：

| 频率 [Hz] | $F_{\nu,\rm shift}/F_{\nu,0}$ |
|---:|---:|
| $5e14$ | $0.9874--1.0112$ |
| $1e15$ | $0.9633--1.0351$ |
| $2e15$ | $0.8915--1.1124$ |
| $5e15$ | $0.7565--1.2925$ |
| $1e16$ | $0.5840--1.6362$ |

在 $i=75^\circ$ 的完整相位曲线上，最大/最小通量比分别为
$2.119,1.687,1.292,1.708,2.801$（对应上表五个频率）。前两个 optical 探针仍主要
由非轴对称投影控制；高频侧则出现强 Doppler 色变化。这是可以由多波段相位光变
证伪的裸盘预言。

垂向呼吸相对“仅轨道频移”的探针通量增量只有 $0.9979--1.0020$。因此当前点的
频移效应几乎全部来自平面轨道速度；这个结论是代码结果，不是预设。

## 5. [V/O] X-ray 仍然失败

完整弱场频移后的方向范围为

$$
1.36\times10^{42}\le L_{\rm UVopt}\le6.28\times10^{42}
\ {\rm erg\,s^{-1}},
$$

$$
9.85\times10^{-39}\le{L_{\rm X}\over L_{\rm UVopt}}
\le1.20\times10^{-35}.
$$

频移在极端 Wien 尾能造成很大的相对变化，却不能把几乎不存在的 X-ray 光子变成
可观测 X-ray 成分。因此阶段 1I 的负结论没有被弱场 Doppler/引力红移推翻：这个
严格局域、低 $V$ 的裸盘仍不能解释显著 X-ray。

## 6. [A-fit/V] 黑体诊断

沿用阶段 1I 的 $0.002--0.1 keV$、$log L_{\nu}$ 等权拟合约定：

$$
3.061\times10^4\le T_{\rm bb}\le3.283\times10^4\ {\rm K},
$$

$$
4.507\times10^{13}\le R_{\rm bb}\le9.764\times10^{13}\ {\rm cm}.
$$

RMS 仍为 $0.303--0.399 dex$，所以单黑体只是与观测对齐的诊断量，不能当作真实
等温球面。

## 7. [V] 必须通过的验证

- 97 项阶段 1/2A 测试全部通过；
- Kepler 速度逐点满足 vis-viva；圆盘速度恒定且无径向分量；
- face-on、只有平面速度时，$g=lapse/\gamma$；趋近侧严格比远离侧蓝；
- $g^3 B_{\nu}(\nu/g,T)=B_{\nu}(\nu,gT)$ 达到浮点舍入误差；
- 频率积分满足黑体 $g^4$ 标度；
- $g=1$ 与原积分逐位相同；
- $e=0$ 时相位 $0 \to 90^\circ$ 的残余误差为 $8.2e-6--3.73e-4$；
- 自适应射线深度 $2 \to 4$ 的五频变化为 0，因为没有遮挡边界；
- 源网格 $(65,1024) \to (129,2048)$ 最大变化为 $5.89e-4$；
- 质量非正、视界内点、超光速、非有限或非正 $g$ 都直接报错；没有
  `nan_to_num`、裁剪或静默修复。

这里的“能量验证”是频谱积分和 $g^4$ 转移标度。观察者无穷远处的能流不应被强制
等于局域发射能流；引力红移和 Doppler 本来就改变其值。完整时空中的全局守恒还需
后续相对论 transfer function 与一致的表面四速度/面积测度。

## 8. [O] 尚未自洽的问题

- 没有光线弯曲、光行时、黑洞自旋或 Cunningham 型像平面 Jacobian；
- Newtonian 椭圆轨道与 Schwarzschild lapse 是混合阶近似；
- 没有处理运动表面的相对论表观面积修正；
- $I_{\nu}=B_{\nu}$ 仍是 LTE 黑体闭合，没有频率相关吸收、电子散射或 color correction；
- 灰 $\tau=2/3$ 光球和局域垂向柱仍不能用于阶段 1H 判定失效的典型高 $e,V$ 区；
- 常偏心源未给出进动周期，所以当前只预言相位依赖，不预言绝对时间尺度。

这些缺口不能通过任意盘风参数掩盖。下一步应先做受控的频率相关裸盘大气/转移层，
并保留本阶段的黑体谱作为严格回归极限；完整 GR ray tracing 排在其后。

## 9. 产物

- `outputs/phase2a_weakfield_spectra.png`
- `outputs/phase2a_weakfield_spectra.csv`：全部方向的完整频移 $F_{\nu},L_{\nu}$，及选定方向对照谱
- `outputs/phase2a_orientation_diagnostics.csv`
- `outputs/phase2a_numerical_convergence.csv`
- `outputs/phase2a_weakfield_spectra_report.json`

运行：

```bash
uv run python scripts/phase2a_weakfield_frequency_shift.py
```
