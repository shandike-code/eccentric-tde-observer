# 阶段 1B：偏心几何与无自遮挡投影

## 1. Jacobian 约定审计

Ogilvie--Lynch 的 $j$ 来自 canonical 坐标 $(\Lambda, \lambda)$，其中
$\lambda = M + \varpi$。对固定 $a$，Kepler 方程给出

$$
\frac{\partial\lambda}{\partial E}
=\frac{\partial M}{\partial E}=1-e\cos E.
$$

ZO 2022 Erratum 明确了正式辐射面积；代码同时保留历史回归：

$$
{\rm d}A_{\rm old}=a j\,{\rm d}a\,{\rm d}E,
\qquad
{\rm d}A_{\rm corr}={\rm d}A_{\rm xy}
=a j(1-e\cos E)\,{\rm d}a\,{\rm d}E.
$$

第一式只用于 pre-Erratum 历史复现；第二式是唯一正式物理面积，也由 Cartesian
坐标映射的 Jacobian 独立得到。
对常偏心、无扭曲的相似椭圆，两者的全轨道积分相同，但局部权重不同。
因此局部温度依赖于 $E$ 时，两者会给出不同的 SED；这是必须量化的系统项。

## 2. [L] 轨道位置

在近心点坐标系内，盘中面节点为

$$
x'=a(\cos E-e),\qquad
y'=a\sqrt{1-e^2}\sin E,
$$

随后以刚体进动角 $\varpi(t)$ 绕 $z$ 轴旋转。当前输入契约只有一个全局
$\varpi$，所以代码不会把 $\mathrm d\varpi/da$ 任意积分成扭曲盘。

## 3. [A] 数值表面与观察者

- 周期 $(a,E)$ 四边形沿固定对角线拆成两个三角形；
- 面法向和面积由 Cartesian 顶点叉积直接计算；
- 观察者方向为 $n_{\rm obs}=(\sin(i)\cos(\phi), \sin(i)\sin(\phi), \cos(i))$；
- 当前只累计 $n_{\rm face} \cdot n_{\rm obs} > 0$ 的正面三角形；没有遮挡射线；
- 三角形强度取三个顶点的 Planck 强度平均，这是数值求积规则，不是大气闭合。

无自遮挡通量为

$$
F_{\nu}=D^{-2}\sum_{f\in\mathrm{front}}
\bar B_{\nu,f}(\hat n_{f}\cdot\hat n_{\rm obs})A_{f}.
$$

## 4. [V] 已通过的极限

- $e\to0$：corrected 与 pre-Erratum 测度严格相同；
- 局域比值严格满足 ${\rm d}A_{\rm corr}/{\rm d}A_{\rm old}=1-e\cos E$；
- 常偏心相似椭圆：总面积回到 $\pi\,\sqrt(1-e^2)\,(a_{\rm out}^2-a_{\rm in}^2)$；
- 三角网格面积随 $N_{\rm E}$ 二阶收敛；
- 刚体改变 $\varpi$ 不改变面积；
- 平面盘投影回到 $A_{\rm proj}/A_{\rm face}=\cos(i)$；
- 平面盘结果与观察者方位 $\phi_{\rm obs}$ 无关；
- 等温平面盘的整个 $F_{\nu}$ 按 $\cos(i)$ 缩放。

## 5. [O] 未解决

- $z_{\rm ph}(a,E)$ 尚未由 $\Sigma,H,\kappa_{\nu}$ 闭合；
- 没有自遮挡，所以非轴对称观测变化尚未出现；
- 没有 Doppler、引力红移、吸收或散射；
- pre-Erratum 与 corrected 测度对非均匀 $T_{\rm eff}(E)$ 的差异只作为历史对照报告；
- 尚无射线，因此不声称通过射线数收敛。
