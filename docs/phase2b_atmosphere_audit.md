# 阶段 2B：裸盘连续谱 opacity 与热化深度审计

本阶段不增加盘风，也不把 ZO 源替换为流体模拟输出。目标是回答一个更基础的问题：
阶段 2A 使用的局域黑体，在什么频率上确实能由裸盘自身的吸收和散射热化？

## 1. [L] 保留的源量

源仍为严格局域域参考点

$M_{\rm BH}=10^6 M_{\rm sun}, e=0.6, V=0.01, a_{\rm out}/a_{\rm in}=2$。sh

$\Sigma,H,T_{\rm eff}$ 和垂向呼吸来自 ZO；密度使用 Lynch--Ogilvie $n=3$ 有限多方闭合

$$
\rho(a,E,z)={\Sigma\over H}f_{3}(z/H).
$$

这些量在本阶段没有重新拟合或归一化。

## 2. [A] 最小连续谱 opacity

电子散射沿用源模型的

$$
\kappa_{\rm es}=0.34\ {\rm cm^2\,g^{-1}}.
$$

自由--自由吸收采用含受激辐射修正的标准热连续谱式

$$
\alpha_{\nu}^{\rm ff}=3.7\times10^8 T^{-1/2}n_{e}
\sum_{i} Z_{i}^2n_{i}\nu^{-3}
\left(1-e^{-h\nu/kT}\right)g_{\rm ff}.
$$

采用完全电离 $X=0.70,Y=0.28$ 的 H/He 组成和 $g_{\rm ff}=1$。这是可复现的最小闭合，
不是对低温盘大气电离状态的自洽解。

灰深度温度使用

$$
T^4(\tau_{\rm es})={3\over4}T_{\rm eff}^4
\left(\tau_{\rm es}+{2\over3}\right).
$$

它只为 opacity 积分提供受约束的深度温度；没有假装已经求解非灰辐射平衡。

## 3. [A/V] 有效光深与热化层

定义

$$
\tau_{{\rm eff},\nu}(z)=
\int_{z}^{z_{s}}\rho
\sqrt{3\kappa_{\nu}^{\rm ff}
(\kappa_{\nu}^{\rm ff}+\kappa_{\rm es})}\,dz.
$$

$\tau_{\rm eff}=1$ 定义热化层。若到中面仍达不到 1，代码直接报告该频率有效薄；不会把热化
层钉在中面。

在每个表面元的局域 $B_{\nu}$ 峰频处，全部柱都能热化：

- 中面 $\tau_{\rm eff}=4.73--87.33$；
- 热化高度 $\zeta_{\rm th}=z_{\rm th}/H=1.173--2.101$；
- 热化层电子散射光深 $\tau_{\rm es}=6.84--9.35$；
- 灰温度给出的 $f_{\rm col}=T_{\rm th}/T_{\rm eff}=1.540--1.656$。

## 4. [V] 频率适用域

| 频率 | $\tau_{\rm eff}$ 最小--最大 | corrected ZO 2022 面积中 $\tau_{\rm eff}\ge1$ |
|---:|---:|---:|
| $5e14 Hz$ | $6.07--416.94$ | $1.000$ |
| $1e15 Hz$ | $2.35--171.27$ | $1.000$ |
| $2e15 Hz$ | $0.850--74.89$ | $0.967$ |
| $5e15 Hz$ | $0.215--23.45$ | $0.467$ |
| $1e16 Hz$ | $0.076--8.84$ | $0.181$ |
| $0.3 keV$ | $0.00390--0.458$ | $0$ |
| $10 keV$ | $2.0e-5--0.00238$ | $0$ |

因此保守的“全部源面都能热化”频域取到 $1e15 Hz$。更高 UV 是部分有效薄，0.3 keV
及以上则整个盘都不能由当前自由--自由闭合热化。

## 5. [V] 数值和闭合敏感性

- $\tau_{\rm eff}$ 垂向网格 $129 \to 257$ 最大变化 $4.42e-6$；
- $f_{\rm col}$ 垂向网格 $257 \to 513$ 最大变化 $4.37e-5$；
- 把热化约定从 $\tau_{\rm eff}=1$ 改为 $2/3$，$f_{\rm col}$ 最大变化 $7.32\%$。

最后一项是闭合系统误差，不是数值误差；阶段 2C 会单独传播它。

## 6. 文献角色与不能越过的边界

- Rybicki--Lightman：自由--自由吸收、受激辐射修正、散射和有效光深的基础公式；
- Roth et al. 2016：说明 TDE 物质中电子散射会增加吸收路径，并提醒 He II
  photoionization、bound-free 和 NLTE 对 UV/X-ray 至关重要；本项目没有移植其包层；
- Davis--Hubeny 2006：说明真实 annulus 谱需要 $\Sigma,T_{\rm eff},Q$、非 LTE、金属
  bound-free 和 Compton；单一 $f_{\rm col}=1.7$ 不是普适替代，尤其在低温吸收边区；
- Lynch--Ogilvie：提供本项目采用的有限多方密度形状，但没有给出非灰表面谱。

本阶段没有 bound-free、bound-bound、Saha/NLTE 电离、Compton、limb darkening 或
偏振。由于本源 $T_{\rm eff}$ 只有约 $8e3--3.9e4 K$，Davis--Hubeny 的高温 annulus 表不能
直接插值使用。

## 7. 产物

- `outputs/phase2b_atmosphere_audit.png`
- `outputs/phase2b_frequency_opacity_audit.csv`
- `outputs/phase2b_probe_opacity_audit.csv`
- `outputs/phase2b_thermalization_cells.csv`
- `outputs/phase2b_atmosphere_audit_report.json`

运行：

```bash
uv run python scripts/phase2b_atmosphere_audit.py
```
