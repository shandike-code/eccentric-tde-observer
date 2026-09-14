# 阶段 1A：face-on 辐射基线

本文件记录当前已经实现的最小切片及证据等级。它不宣称完成倾角、自遮挡或高偏心观测预测。

## [L] 文献给定或沿用的量

输入场是

$$
\{a,E,e(a),\varpi,\Sigma(a,E),j(a,E),H(a,E),T_{\rm eff}(a,E)\}.
$$

其中 $j$ 是 Ogilvie--Lynch canonical $(\Lambda,\lambda)$ Jacobian 的
无量纲部分。ZO 2020 原论文错误写成

$$
{\rm d}A_{\rm old}=a\,j\,{\rm d}a\,{\rm d}E.
$$

ZO 2022 Erratum 给出的正式辐射面积元为

$$
{\rm d}A_{\rm corr}=a\,j(1-e\cos E)\,{\rm d}a\,{\rm d}E.
$$

这与 Cartesian 平面嵌入给出的面积完全相同。代码正式路径只使用
`corrected_zo_area_weights`；旧式只保留在
`pre_erratum_zo2020_area_weights` 历史回归路径中。两者在 $e\to0$ 时严格相同。

face-on 远方观测者的各向同性等效光度为

$$
L_{\nu,\mathrm{iso}}=4\pi\int B_{\nu}[T_{\rm eff}(a,E)]\,{\rm d}A_{\rm corr}.
$$

双面本征光度为

$$
L_{\nu,\mathrm{intrinsic,2face}}=2\pi\int B_{\nu}[T_{\rm eff}(a,E)]\,{\rm d}A_{\rm corr}.
$$

所以 $L_{\nu,\rm iso}=2L_{\nu,\rm intrinsic,\rm 2face}$。这里的
$L_{\nu,\rm iso}$ 不是双面本征光度，也不能与 $F_{\nu}$ 混用；三者在 API 与报告中分别命名。

## [A] 当前工作假设

- LTE、局域各向同性黑体，$I_{\nu} = B_{\nu}(T_{\rm eff})$；
- corrected ZO 2022 基准无自遮挡、视线严格 face-on；
- 输入数组是活动盘域的单值采样，因此要求 $j, \Sigma, H, T_{\rm eff}$ 严格为正；
- $E$ 使用半开周期网格 $[0, 2\,\pi)$，禁止重复端点；
- 若源模型同时提供径向梯度，则额外检查嵌套轨道条件；不从离散数组自行猜测梯度。

## [V] 当前代码验证

- $e = 0, j = 1$ 时，数值面积回到 $\pi\,(R_{\rm out}^2-R_{\rm in}^2)$；
- 等温圆环的逐频积分回到解析 Planck 光谱；
- 对频率积分后回到 Stefan--Boltzmann bolometric 极限；
- 局域 corrected/old 权重比严格回到 $1-e\cos E$；
- 幂律温度圆盘相对闭式 bolometric 解呈二阶径向网格收敛；
- 常偏心椭圆环的三角网格面积呈二阶周期网格收敛；
- 平面盘无自遮挡投影严格回到 $\cos(i)$，且与观察者方位无关；
- 非有限值、越界偏心率、$j \le 0$ 和重复周期端点均直接报错；
- 源代码不使用 `nan_to_num` 或 `np.clip` 掩盖非法状态。

## [O] 尚未解决

- 还没有接入真实 Zanazzi--Ogilvie 高偏心输出；
- 已有可复用三角表面、法向和任意上半球视角投影，但没有光球闭合或自遮挡；
- 还没有吸收、散射、颜色修正或频移；
- 因尚未引入射线，射线数收敛测试不适用，也没有被声称为已完成；
- 当前图只是解析圆盘数值基准，不能用于回答裸偏心盘能否解释 optical/UV 与 X-ray 相对强度。
