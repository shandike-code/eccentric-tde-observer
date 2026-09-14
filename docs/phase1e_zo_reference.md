# 阶段 1E：ZO 常偏心参考源与观测积分审计

本阶段第一次把可追溯的 Zanazzi--Ogilvie（下称 ZO）热源接入既有观察者映射，
但结论分成两层：ZO 2022 Erratum corrected 源 SED 已收敛；optical 射线结果已收敛；
高频射线结果尚未收敛，因此没有交付 X-ray 观测谱。

## 1. 本阶段选择的最小可追溯源

本地没有发现作者发布的数值快照或完整偏心本征模求解器。因此这里复现原文
Figure 9 使用的常偏心族，而不把它冒充为 Section 2.4 的完整本征解。

### [L] 直接来自 ZO 2020 的量

取 $\gamma=4/3$、$e(a)=e=constant$、$a e_{a}=0$、$a \varpi_{a}=0$，并使用：

$$
a_{\rm in}=\frac{R_{t}^2}{2R_{\star}(1+\mathcal V)},
\qquad R_{t}=R_{\star}\left(\frac{M_{\bullet}}{M_{\star}}\right)^{1/3},
\tag{10}
$$

$$
\Sigma^\circ(a)=\frac{M_{\star}}{4\pi a_{\rm in}^2\tilde a^3},
\qquad
\frac{H^\circ}{a}=\left[\frac{(\gamma-1)\mathcal V}{1+\mathcal V}\right]^{1/2},
\tag{16,18}
$$

以及常偏心极限下

$$
j=\sqrt{1-e^2},\qquad \Sigma=\frac{\Sigma^\circ}{j},
\qquad H=H^\circ h(E).
\tag{31}
$$

垂向呼吸函数 $h(E)$ 满足

$$
(1-e\cos E)h''-e\sin E\,h'+h
=\frac{(1-e\cos E)^3}{j^{\gamma-1}h^\gamma},
\tag{35}
$$

并施加偶对称周期边界 $h'(0)=h'(\pi)=0$。有效温度使用原文 Eq. (55)：

$$
T_{\rm eff}=2.65\times10^4\,{\bar M_{\star}^{1/3}\over
\bar M_{\bullet}^{1/12}\bar R_{\star}^{1/2}}
{\mathcal V^{1/8}(1+\mathcal V)^{3/8}\over
\tilde a^{1/2}j^{1/12}h^{1/3}}\ {\rm K}.
\tag{55}
$$

ZO 2020 原论文 Eq. (56) 的旧面积元为

$$
{\rm d}A_{\rm old}=a j\,{\rm d}a\,{\rm d}E.
$$

ZO 2022 Erratum Eq. (5) 将正式辐射面积修正为

$$
{\rm d}A_{\rm corr}=a j(1-e\cos E)\,{\rm d}a\,{\rm d}E,
\qquad
L_{\nu,\rm iso}^{\rm corr}=4\pi\int B_{\nu}(T_{\rm eff})\,{\rm d}A_{\rm corr}.
$$

### [A] 本阶段新增但显式标出的闭合

- Eq. (55) 的数值系数默认对应 $\kappa=0.34 cm^2 g^-1$；代码只加入
  $T_{\rm eff} \propto \kappa^(-1/4)$ 的显式缩放。它不是频率依赖 opacity。
- Eq. (35) 在 $q=ln h$ 中用 shooting 求解。这样 $h>0$ 来自变量变换，而不是
  对负值裁剪。
- 为解析近心点极窄热区，积分网格在半轨道使用 $E=\pi\,u^5$，另一半按对称性反射。
  这只改变求积坐标，不改变轨道。
- 光球仍沿用阶段 1C 的 Gaussian 垂向柱和灰 $\tau=2/3$ 闭合；局域出射强度仍取
  $I_{\nu}=B_{\nu}(T_{\rm eff})$。
- 观察者映射仍是 Newtonian 正交平行射线，没有任何频移。

## 2. corrected 正式面积与历史回归必须分开

阶段 1B 已证明，按实际平面嵌入

$$
x=a(\cos E-e),\qquad y=a\sqrt{1-e^2}\sin E
$$

得到的 Cartesian 面积元与 Erratum corrected 面积相同：

$$
{\rm d}A_{\rm cart}={\rm d}A_{\rm corr}
=a j(1-e\cos E)\,{\rm d}a\,{\rm d}E.
$$

因此 `face_on_blackbody_sed` 只走 corrected 正式路径；
`pre_erratum_face_on_blackbody_sed` 只用于历史回归。对 $e=0.8$，在
$[5e14, 1e16, 5e16, 1e17] Hz$，corrected/old 为

$$
[0.80426,\ 0.20017,\ 0.2000004,\ 0.2000001].
$$

高频极限接近 $1-e=0.2$，因为辐射集中到近心点，而 corrected 面积包含
$1-e\cos E$。这是 Erratum 面积修正，不是自遮挡效应，也没有事后重归一化。[L/V]

## 3. [V] 源模型验证与收敛

参考参数为

$M_{\rm bh}=1e6 Msun, M_{\rm star}=1 Msun, R_{\rm star}=1 Rsun, V=1,$
$a_{\rm out}/a_{\rm in}=2, e=0.8, \kappa=0.34 cm^2 g^-1$。

- $a_{\rm in}=1.73925e14 cm$；
- Eq. (35) 给出 $h(0)=6.342715e-4$、$h(\pi)=2.024973$；
- $h'(\pi)$ shooting 残差为 $2.42e-14$；
- $T_{\rm eff}=1.9759e4--4.1738e5 K$；
- pre-Erratum canonical 测度下的质量积分仅作为源构造回归，与 Eq. (14) 的相对差为 $1.78e-5$；
- $N_{\rm E}:1024 \to 2048$ 时四个探针频率的最大变化为 $2.85e-4$；
- $N_{a}:129 \to 257$ 时最大变化为 $9.07e-5$。

均匀 $E$ 网格在高偏心情形下曾产生貌似平滑但实际未解析的高频谱；加入近心点
聚点以后才揭露这一问题。当前源积分的收敛阈值为 $1e-3$，四个频率均通过。

按 corrected 面积对频率积分，本参考源给出

$$
L_{0.002-0.1\,\rm keV}=6.0105\times10^{43}\ {\rm erg\,s^{-1}},
$$

$$
L_{0.3-10\,\rm keV}=2.7649\times10^{41}\ {\rm erg\,s^{-1}},
\qquad
{L_{\rm X}\over L_{\rm UV/opt}}=4.600\times10^{-3}.
$$

corrected/old 分别为 $0.23823$ 与 $0.200000$。这三个数是 [L/V]
**源端 corrected 重建量**，不是任意方向观测者的预言。

## 4. [V/A] 当前可发布的观察者结果

在 $i=30^\circ$、$\nu=5e14 Hz$，使用 $(N_{a},N_{\rm E})=(65,1024)$ 的源表面和
2048 长轴像素扫描 24 个相对进动相位

$$
\Phi(t)=\phi_{\rm obs}-\varpi(t),
$$

得到

$$
0.45376\leq
{L_{\nu,\rm ray}(\Phi)\over L_{\nu,\rm corr}}
\leq1.27826.
$$

三个审计方位在 4096 长轴像素下，$5e14 Hz$ 的最后一步像素收敛误差都小于
$3.1e-5$。这说明当前闭合下，盘的投影和自遮挡可以产生进动相位相关的 optical
变化；它仍依赖 Gaussian 灰光球，因此标签是 [A/V]，而不是无条件物理预言。

## 5. [O/V] 为什么本阶段不交付 X-ray 观测谱

在 $[1e16,5e16,1e17] Hz$，固定均匀像平面从 2048 增至 4096 像素时，部分方位
仍发生从百分之几到两个数量级以上的变化；最坏最后一步变化为 $178.99$。
正确解析 Eq. (35) 后，X-ray 发射缩到极窄近心点热区；均匀像素会漏掉可见热区的
细小部分。早期粗源网格给出的“高频收敛”其实是数值涂抹造成的假象。

因此当前明确记录：

- optical 相位响应通过现有像素收敛测试；
- 高频观察者积分失败，数值被保留为失败诊断，但不作为频谱结果发布；
- 不通过继续盲目增加均匀射线数来掩盖结构性采样问题；
- 下一步应使用自适应像平面积分、近心点重要性采样，或直接在可见表面上做
  带遮挡判定的自适应积分，并重新逐频验证。

## 6. [O] 暴露出的物理失效，而非数值错误

对上述 $e=0.8$ 参考源，Gaussian 灰光球给出

- $H/r=0.00129--1.1815$；
- $z_{\rm ph}/r=0.00377--4.1460$；
- 按 corrected/Cartesian 面积，$z_{\rm ph}/r\ge1$ 的区域占约 $99.35\%$。

这意味着“每个 $(a,E)$ 上的局域平面平行 Gaussian 柱”在几乎整个参考盘上都不再
是几何自洽的薄柱描述。射线图像仍可作为**条件性闭合的数值结果**，但不能宣称是
真实厚盘光球。这个失败不能通过加入任意盘风、裁剪 $z_{\rm ph}$ 或调低高度来消除。

## 7. 结论边界与下一步

- [L] ZO 2020 Eqs. (10,16,18,31,35,55) 确定源场；ZO 2022 Erratum Eq. (5) 确定辐射面积。
- [A] opacity 缩放、Gaussian 灰光球、LTE 黑体、正交 Newtonian 射线是新增闭合。
- [V] Eq. (35)、历史质量回归、corrected SED、源网格和 optical 射线相位响应已验证。
- [O] 完整 $e(a)$ 本征解、几何自洽厚盘光球、高频自适应射线、频率依赖转移、
  Doppler/引力频移和真实 $\varpi(t)$ 时间标尺均未完成。

最合理的下一步是阶段 1F：只替换观察者积分器的采样策略，保留同一源和全部物理
闭合，先让高频结果通过逐频收敛；在此之前不增加盘风、不做 GR ray tracing，
也不报告 $T_{\rm bb}$ 或 $R_{\rm bb}$。
