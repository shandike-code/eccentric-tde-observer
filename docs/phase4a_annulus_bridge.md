# Phase 4A：动态偏心柱到静态 annulus atmosphere 的桥梁

## 1. 为什么不能直接接 Davis--Hubeny 表

Davis & Hubeny (2006) 的局域环带由三个物理坐标确定：

- 有效温度 $T_{\rm eff}$；
- 从表面到中面的柱质量 $m_{0}=\Sigma/2$；
- 垂向重力系数 $Q=g/z$。

其大气假定稳态、平行平面、结构只随高度变化。Ogilvie & Lynch (2019) 则明确指出：偏心
盘的垂向重力和水平压缩随轨道相位变化，盘必然发生受迫呼吸，不处于垂向静力平衡。
因此，仅把 $\Sigma,T_{\rm eff}$ 填入一个静态表并不构成自洽闭合。

## 2. ZO 动态柱给出的两个 Q

定义轨道平均运动 $n=\sqrt(GM/a^3)$、$u=1-e\,\cos(E)$。瞬时潮汐重力是

$Q_{\rm tidal} = GM/r^3 = n^2/u^3$。

沿着呼吸运动的流体柱，压力梯度还需提供垂向加速度。若把动态柱瞬时映射成一个静态
大气，则压力所平衡的等效系数为

$Q_{\rm pressure}=Q_{\rm tidal}+\ddot{H}/H$。

利用 ZO Eq. (35)，无需对 $H(E)$ 数值二阶微分即可得到

$Q_{\rm pressure}=n^2j^{-(\gamma-1)}h^{-(\gamma+1)}$。

`[L]` 方程结构来自 ZO/Ogilvie--Lynch 呼吸解；`[A]` 把 $Q_{\rm pressure}$ 当作静态环带输入
是一个瞬时、共动的准静态桥梁，不是文献已经证明的 NLTE 闭合。

## 3. 准静态判据

定义

$\epsilon_{\rm dyn}=|\mathrm d\ln H/\mathrm dt|/\sqrt{Q_{\rm pressure}}$。

分母是静态柱的垂向响应频率，分子是背景呼吸变化率。只有 $\epsilon_{\rm dyn} \ll 1$ 时，把轨道
看成一串静态环带才有时间尺度依据。这个量不是修正因子，代码不会把较大的值压回小值。

严格参考源得到：

- $Q_{\rm tidal} = 9.91e-14--5.08e-11 s^-2$；
- $Q_{\rm pressure} = 6.21e-14--2.39e-9 s^-2$；
- $Q_{\rm pressure}/Q_{\rm tidal} = 0.300--47.1$；
- $\epsilon_{\rm dyn} = 0--2.00$；
- 面积中仅 $12.9\%$ 满足 $\epsilon_{\rm dyn}<0.1$，$35.3\%$ 满足 $<0.3$，
  $72.8\%$ 满足 $<1$。

所以一个静态 NLTE 表即使覆盖参数范围，也只能在有限相位区域成为受控近似。其余部分需要
时间依赖垂向辐射转移，或一个经过独立验证的有限响应模型。

## 4. 现有表格覆盖率

Davis--Hubeny 2006 表格范围为：

- $log10 T_{\rm eff}/K = 5.0--7.4$；
- $log10 Q/s^-2 = -4--9$；
- $log10 m_{0}/(g cm^-2) = 2.5--6$ 的离散范围。

当前源为：

- $T_{\rm eff}=8.15e3--3.87e4 K$；
- $m_{0}=104--834 g cm^-2$；
- $Q_{\rm pressure}=6.21e-14--2.39e-9 s^-2$。

三维联合覆盖面积严格为零。因此禁止外推 Davis--Hubeny 表来生成本项目的 X-ray 谱。

## 5. 接口与未解决问题

`AngleResolvedAnnulusTable` 定义了未来表格的严格接口
$I_{\nu}(T_{\rm eff},m_{0},Q,\mu,\nu)$：

- 所有轴严格递增；
- 强度正且有限；
- 对数坐标内插；
- 任何轴外查询立即报错；
- 每张表必须写 provenance。

当前没有给该接口填入伪造的 NLTE 数据。`phase4_annulus_coordinates.npz` 保存了未来求解器
所需的全部源坐标。

中面总散射深度给出的 thermal Compton $y$ 只是上限诊断，范围 $0.0069--2.10$；它使用
到中面的全部光深，不能替代实际谱形成层的 Kompaneets/NLTE 解。

代码：`src/eccentric_tde_observer/annulus_bridge.py`；测试：
`tests/test_annulus_bridge.py`。
