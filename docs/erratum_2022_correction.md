# ZO 2022 Erratum 专项修正

上级导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/docs/phase1e_zo_reference|Phase 1E]]

## 1. [L] 修正边界

[Zanazzi & Ogilvie 2022 Erratum](https://academic.oup.com/mnras/article/516/3/3234/6659186)
指出，ZO 2020 使用的旧面积

$$
{\rm d}A_{\rm old}=a\,j\,{\rm d}a\,{\rm d}E
$$

应修正为

$$
{\rm d}A_{\rm corr}
=a\,j(1-e\cos E)\,{\rm d}a\,{\rm d}E.
$$

Erratum 只改变辐射积分权重；本项目没有重定义
$e(a),\varpi,\Sigma,j,H,T_{\rm eff}$，也没有修改 ZO 动力学或垂向呼吸解。
正式 API 只使用 corrected 面积；旧式只保留为 pre-Erratum 历史回归。

## 2. [V] 专项门槛

| 门槛 | 独立复算结果 |
|---|---:|
| $e\to0$ | corrected 与 old 逐节点相同 |
| 局域比值 | $\mathrm dA_{\rm corr}/\mathrm dA_{\rm old}=1-e\cos E$ |
| corrected 频率积分/Stefan--Boltzmann | 相对误差小于 $10^{-5}$ |
| $e=0.8$ UV/optical corrected/old | $0.23823$ |
| $e=0.8$ X-ray corrected/old | $0.200000$ |
| $e=0.8$ corrected $L_{\rm X}/L_{\rm UVopt}$ | $4.62\times10^{-3}$ |
| $(e,\mathcal V)=(0.6,0.01)$ corrected $L_{\rm bol,\rm iso}$ | $6.9327\times10^{42}\ {\rm erg\,s^{-1}}$ |
| corrected 严格域 | $(0.6,0.01)$ 与 $(0.65,0.01)$ 均通过 |

这些数由源场和独立构造的两套面积权重积分得到，没有硬编码成模型输出，没有
事后重归一化，也没有删除失败点。

## 3. 光度命名

远方观测者通量为 $F_{\nu}$；各向同性等效光度为
$L_{\nu,\rm iso}=4\pi D^2F_{\nu}$。对局域各向同性强度，单面本征功率与双面本征光度分别为

$$
L_{\nu,\rm one}= \pi\int B_{\nu}\,{\rm d}A_{\rm corr},
\qquad
L_{\nu,\rm intrinsic,\rm 2face}=2L_{\nu,\rm one}.
$$

因此 face-on $L_{\nu,\rm iso}=2L_{\nu,\rm intrinsic,\rm 2face}$，但两者不是同一物理量。
Phase 3 的 energy reference 已分别输出 corrected 各向同性等效量、corrected 双面本征量
和 pre-Erratum 历史量。

## 4. 重生成结果与读图

![corrected 源谱与 pre-Erratum 对照](../outputs/phase1e_zo_source_and_ray_audit.png)

**怎么看。** 第二行左图是 corrected 常偏心源 SED；第二行右图直接显示
corrected/pre-Erratum 随频率变化，高频趋向 $1-e=0.2$。下排仍保留观察者积分的
收敛审计，corrected 面积不会修复未收敛的高频射线。

**验证了什么。** [V] corrected 源谱、波段光度和 optical 射线/源比均已重算；
pre-Erratum 只作为历史对照。

![corrected 有效域](../outputs/phase1h_validity_domain.png)

**怎么看。** 热图全部使用 corrected 面积加权。$e=0.65,\mathcal V=0.01$ 的 Gaussian
闭合在 $z_{\rm ph}/r\ge0.3$ 上占 $0.886\%$，低于 $1\%$ 工作门槛；多方闭合为零。

**验证了什么。** [V] 严格通过点为 49 个；因此 $e=0.6$ 不再称为最高偏心严格点。

## 5. [V/O] 观察者链

Phase 3、4、5 使用 Cartesian 三角形或像平面面积，它们与 corrected ZO 平面面积等价。
这些阶段已实际重跑；$F_{\nu}$ 与 $F_{\lambda}$ 链继续通过能流和
$\lambda F_{\lambda}=\nu F_{\nu}$ 验证。它们没有切回 pre-Erratum 权重。

完整测试分为：

- corrected 正式科学测试：圆盘极限、局域因子、SED 能流、参考波段、严格域和观察者链；
- pre-Erratum 历史回归：旧面积、旧源谱与 canonical 源质量构造检查。

项目仍禁止 nan_to_num、无物理理由的 clip、任意 floor、删除失败点和事后重归一化。
