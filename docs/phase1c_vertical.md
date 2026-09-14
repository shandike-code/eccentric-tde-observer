# 阶段 1C：Gaussian 垂向闭合与灰光球

## [L] 源模型提供

Zanazzi--Ogilvie 源接口继续只提供 $\Sigma(a,E)$ 和 $H(a,E)$；本阶段没有
改变它们的动力学来源，也没有从流体模拟重新生成盘结构。

## [A] 新闭合

采用归一化 Gaussian：

$$
\rho(a,E,z)=\frac{\Sigma(a,E)}{H(a,E)}
\frac{\exp[-(z/H)^2/2]}{\sqrt{2\pi}}.
$$

它满足 $\int \rho dz = \Sigma$，但并不是 ZO 理论唯一指定的垂向剖面。
灰不透明度 $\kappa$ 必须由调用者显式传入。上表面光球定义为

$$
\tau(z_{\rm ph})=\kappa\int_{z_{\rm ph}}^\infty\rho\,{\rm d}z
=\tau_{\star},
\qquad \tau_{\star}=2/3.
$$

### 为什么采用 $\tau_{\star}=2/3$

`[L]` 在平行平面、灰不透明度和 Eddington 闭合下，灰大气温度关系为

$$
T^4(\tau)=\frac{3}{4}T_{\rm eff}^4\left(\tau+\frac{2}{3}\right).
$$

因此 $\tau=2/3$ 处恰有 $T=T_{\rm eff}$；Eddington--Barbier 关系也表明出射辐射主要
采样光深为一量级的层。这里的 $2/3$ 是标准灰大气的 bolometric flux 光球约定，不是从
当前 ZO 动力学重新推导出的特殊数值，也不是可以调节以改善图形的自由参数。

`[A]` 本项目把这一约定用于定位上表面几何。在当前 benchmark 中，$\kappa$ 取与频率
无关的电子散射值，所以“灰光球”只表示：用同一个频率无关不透明度求得一张共同的
$z_{\rm ph}(a,E)$ 表面。它不表示辐射没有颜色，也不等于频率依赖的热化面。

`[O]` 对散射占优介质，$\tau_{\rm es}=2/3$ 更接近末次散射面的几何标记；真实热化深度
由吸收与散射共同决定，通常应检查 $\tau_{\rm eff}(\nu)\simeq1$，并可能更深且依赖频率。
因此仅有灰光球不能推出 $I_{\nu}=B_{\nu}(T_{\rm eff})$，也不能替代 NLTE 大气计算。

对 Gaussian 闭合，若 $q=\tau_{\star}/(\kappa\,\Sigma)$，则
$z_{\rm ph}/H = -\Phi^{-1}(q)$。实现使用对数尾概率，避免大光深下 $1-q$ 的
浮点消减。

## [V] 代码验证

- 数值积分恢复 $\Sigma$；
- 中面以上质量柱严格为 $\Sigma/2$；
- 回代得到的 $\kappa\,column(z_{\rm ph})$ 恢复 $\tau_{\star}$；
- $\kappa\,\Sigma/2 = \tau_{\star}$ 时 $z_{\rm ph} = 0$；
- $\kappa\,\Sigma/2 < \tau_{\star}$ 时抛出 `OpticallyThinColumnError`；
- 没有用 clipping 或 `nan_to_num` 把光学薄单元伪装成光球；
- 求得的非平面光球可以直接送入阶段 1B 的三角表面模块。

## [O] 不能声称已自洽

- Gaussian 是工作闭合；真实 ZO 垂向解可能不是等温 Gaussian；
- $H$ 的具体归一化必须与输入理论解保持一致；
- benchmark 的 $\kappa=0.34 cm^2 g^-1$ 仅代表完全电离太阳组成电子散射；
- 散射光深 $\tau=2/3$ 不是热化深度。频率依赖吸收和有效光深
  $\tau_{\rm eff}$ 尚未计算；
- 尚未求解温度随高度的变化、limb darkening 或颜色修正；
- 尚未进行自遮挡射线或射线数收敛。
