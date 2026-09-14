# Phase 7B4i：周期动态 H/He 基态能量柱

证据标记：`[L]` 文献输入；`[V]` 代码验证；`[A]` 工作假设；`[O]` 未解决问题。

关联文档：

- [[eccentric_tde_observer/docs/phase7b_periodic_column|Phase 7B1 周期柱数值底座]]；
- [[eccentric_tde_observer/docs/phase7b4b_orbit_coupled_kinetics|Phase 7B4b 轨道耦合 H/He 动力学]]；
- [[eccentric_tde_observer/docs/phase7b4h_hydrostatic_table_gate|Phase 7B4h 静力大气表准入门]]；
- [[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]。

## 1. 本阶段回答什么

Phase 7B4h 已验证：在规定 ZO 的 $m_{0}$、$H$ 和 $Q$ 上，静态 H/He Rosseland 柱虽然有热根，
但不能同时保持 ZO 厚度。7B4i 因此不再逐相位独立求静态表，而是沿一条实际 ZO 轨道推进同一
批物质的能量和基态布居。`[V]`

本阶段只回答：

> 在 ZO 规定的周期呼吸背景上，压缩功、规定耗散、连续谱扩散和 H/He 基态电离能能否组成一个
> 正、守恒、失去初态记忆的周期解？

它不回答真实 UV/X-ray 谱，也不授权替换 Phase 4。`[A/O]`

## 2. 拉格朗日质量坐标

半柱质量坐标从表面 $m=0$ 指向中面 $m=m_{0}$，使用固定分数坐标

$$
x=\frac{m}{m_{0}}.
$$

每个相位的密度仍由原 ZO 的 $m_{0}$ 和 $H$ 通过 $n=3$ 垂向闭合构造，没有修改
$H(a,E)$、$\Sigma(a,E)$ 或 $Q(a,E)$。严格参考源在所选半长轴上满足 $m_{0}$ 沿轨道恒定，
因此每个离散质量单元确实代表同一批物质。其相对变化在浮点表示中为零。`[V]`

若以后处理 $m_{0}$ 随相位变化的源，必须加入水平会聚和质量映射；当前求解器会直接拒绝这种
输入，而不会把不同质量单元错误拼成时间轨道。`[O]`

相邻相位的压缩量直接由有限差分计算：

$$
\Delta\ln\rho_{n}
=
\ln\left(\frac{\rho_{n+1}}{\rho_{n}}\right).
$$

完整周期满足

$$
\sum_{n}\Delta\ln\rho_{n}=0.
$$

正式结果的最大闭合残差为 $1.53\times10^{-15}$。`[V]`

## 3. 联立能量方程

每个质量单元推进的比总能量为

$$
e=e_{\rm gas}+e_{\rm rad}+e_{\rm ion}.
$$

其中

$$
e_{\rm gas}
=
\frac{3}{2}k_{\rm B}T
\frac{n_{\rm H}+n_{\rm He}+n_{e}}{\rho},
$$

$$
e_{\rm rad}=\frac{a_{\rm rad}T^{4}}{\rho},
$$

并显式加入 H I、He I 和 He II 的逐级电离势能：

$$
e_{\rm ion}
=
\frac{n_{\rm H}}{\rho}x_{\rm HII}\chi_{\rm HI}
+
\frac{n_{\rm He}}{\rho}
\left[
x_{\rm HeII}\chi_{\rm HeI}
+x_{\rm HeIII}(\chi_{\rm HeI}+\chi_{\rm HeII})
\right].
$$

压力包含气体和辐射：

$$
P=P_{\rm gas}+P_{\rm rad}
=
k_{\rm B}T(n_{\rm H}+n_{\rm He}+n_{e})
+\frac{a_{\rm rad}T^{4}}{3}.
$$

采用表面到中面的质量坐标后，能量方程写为

$$
\frac{{\rm d}e}{{\rm d}t}
=
-P\frac{{\rm d}}{{\rm d}t}\left(\frac{1}{\rho}\right)
+q_{m}
+\frac{\partial F}{\partial m}.
$$

这里 $q_{m}$ 是 Phase 7B4h 已声明的单位质量均匀或支撑压力加权耗散，$F>0$ 表示向表面
流出。静态极限回到 $\partial F/\partial m=-q_{m}$。`[A/V]`

有限时间步的压缩功不用点值 $\dot H/H$ 近似，而是

$$
\Delta w
=
-\frac{P_{n}+P_{n+1}}{2}
\left(
\frac{1}{\rho_{n+1}}-\frac{1}{\rho_{n}}
\right).
$$

这使有限步压缩和膨胀直接对应实际体积变化。`[V]`

## 4. 基态 H/He 动力学与当前辐射闭合

H I/H II 和 He I/He II/He III 仍由电荷自洽的后向 Euler 率方程推进，粒子数不靠事后
重归一化。当前局域辐射率使用

$$
J_{\nu}=B_{\nu}(T)
$$

和同一组基态 Milne 正反过程。它代表光学厚单元内部的局域受困热场，是 7B4i 的明确工作假设，
不是非局域频率依赖转移。`[A]`

正式运行没有启用 Voronov 碰撞电离。原因不是为了得到更好看的结果，而是动态表层最低温度
$1.21\times10^{4}\ {\rm K}$ 已低于当前 He II Voronov 拟合声明的下限。代码不外推、不裁剪，
因此本阶段只使用 Milne 辐射率；低温有效的碰撞数据仍是未解决输入。`[V/O]`

## 5. Rosseland 扩散和边界

时间依赖布居先生成基态 H/He Milne 连续消光，再计算

$$
\frac{1}{\kappa_{\rm R}}
=
\frac{
\int \kappa_{\nu}^{-1}
\left(\partial B_{\nu}/\partial T\right){\rm d}\nu
}{
\int
\left(\partial B_{\nu}/\partial T\right){\rm d}\nu
}.
$$

相邻单元中心的向外扩散通量为

$$
F_{i+1/2}
=
\frac{4\sigma_{\rm SB}}{3}
\frac{T_{i+1}^{4}-T_{i}^{4}}
{
\tfrac{1}{2}\kappa_{i}\Delta m_{i}
+\tfrac{1}{2}\kappa_{i+1}\Delta m_{i+1}
}.
$$

表面使用灰 Eddington 真空关系

$$
F_{0}
=
\frac{\sigma_{\rm SB}T_{0}^{4}}
{
\tfrac{1}{2}
+\tfrac{3}{4}\left(\tfrac{1}{2}\kappa_{0}\Delta m_{0}\right)
},
$$

中面严格设置

$$
F_{\rm N}=0.
$$

离散静态控制可以逐浮点精度回收预先构造的通量剖面。`[V]`

## 6. 周期解和能量账本

一个周期结束后，把末态作为下一周期初态，直到温度相对残差和布居绝对残差同时收敛。正式
均匀单位质量耗散只需 2 周期；替代初态使用高 15% 的温度以及不同的正 H/He 分数，最终得到：

| 量 | 结果 |
|---|---:|
| 温度初态相对差 | $9.22\times10^{-9}$ |
| 布居初态绝对差 | $6.25\times10^{-9}$ |
| 最大局域能量残差 | $1.08\times10^{-11}$ |
| 周期能量账本相对残差 | $2.14\times10^{-12}$ |
| 最大相对电荷残差 | $2.20\times10^{-16}$ |
| 最大粒子守恒残差 | $3.33\times10^{-16}$ |
| 温度范围 | $1.21\times10^{4}$--$1.08\times10^{5}\ {\rm K}$ |

周期账本验证

$$
\Delta U_{\rm cyc}
=
W_{\rm comp,\rm cyc}
+E_{\rm diss,\rm cyc}
-E_{\rm esc,\rm cyc}.
$$

均匀耗散下，轨道耗散为 $1.3815\times10^{19}\ {\rm erg\,cm^{-2}}$，压缩功净值为
$-7.60\times10^{14}\ {\rm erg\,cm^{-2}}$，远小于耗散，但没有被删去。`[V]`

## 7. 主图逐面解释

![Phase 7B4i periodic dynamic column](../outputs/phase7b4i_periodic_dynamic_column.png)

- `(a)`：ZO 尺度高度从近心点最小值增加约 38 倍，深部密度作相反变化；这是规定动力学背景，
  不是热求解器反算出的新 $H$。`[V]`
- `(b)`：深部单元温度高于表层，二者随压缩在近心点附近上升。$T_{\rm eff}$ 只标记 ZO 给出的
  瞬时单面耗散通量，不等于任一深度单元的气体温度。`[A/V]`
- `(c)`：动态出射通量与 ZO 瞬时耗散很接近，但并不严格相等；均匀耗散的比值范围为
  $0.9904$--$1.0073$。差额由能量储存和压缩功承担。两种受控耗散律在当前灰闭合下差异很小。`[V]`
- `(d)`：H 在表层和深部几乎完全电离；He III 在低温轨道段的表层显著复合，而深部仍保持较高
  电离。这个急剧的 He 电离前沿也是深度收敛最困难的区域。`[V]`

## 8. 能量图和收敛图

![Phase 7B4i energy closure and convergence](../outputs/phase7b4i_energy_convergence.png)

- `(a)`：累计耗散和累计出射几乎重合；压缩功相对较小但具有完整的压缩--膨胀周期结构。
- `(b)`：出射/瞬时 ZO 通量偏离 1 的幅度约为 1%，说明该参考柱的灰扩散热记忆不大，但不能
  据此推断非灰电离边附近也只有 1%。
- `(c)`：128 对 256 相位的温度/通量最大相对误差约 $8.90\times10^{-3}$；65 对 257 个频率
  基点约 $9.32\times10^{-4}$。深度误差不单调，8 对 12 个半柱单元约为 $3.22\times10^{-2}$。
- `(d)`：相应人口误差分别约为 $1.57\times10^{-2}$、$4.27\times10^{-3}$ 和 $0.331$。
  深度人口误差在固定拉格朗日质量坐标上计算，不再错误比较位置不同的“第一个单元”。`[V]`

因此，能量守恒和周期吸引子已经通过，但当前生产分辨率没有通过。尤其是 He 电离前沿需要
自适应质量网格或显著更细的固定网格。`[V/O]`

## 9. 本阶段结论

1. `[V]` ZO 呼吸背景上的周期能量--基态人口求解在数值上可行，正性、电荷、粒子数和周期能量
   账本均通过。
2. `[V]` 静态逐相位表失败后，压缩功可以与规定耗散和扩散放进同一拉格朗日时间推进；没有必要
   修改 ZO 动力学源场。
3. `[A]` 局域 $J_{\nu}=B_{\nu}(T)$ 和 Rosseland 扩散仍把非局域辐射场压缩成灰闭合，不能称为
   完整 NLTE。
4. `[V/O]` 当前 128 相位、8 个半柱单元和 65 个频率基点的主网格没有实现生产级时间与深度
   收敛，不能接入 Phase 4、不能生成 UVOT 计数、不能宣称物理连续谱。
5. `[V/O]` 后续 [[eccentric_tde_observer/docs/phase7b4j_adaptive_dynamic_convergence|Phase
   7B4j]] 已建立共享自适应拉格朗日网格并把时间参考提高到 1024 相位；局部前沿解析改善，
   但柱平均量存在权衡。[[eccentric_tde_observer/docs/phase7b4k_error_estimated_dynamic_convergence|Phase
   7B4k]] 又证明 1024 对 2048 相位时间门通过，而双网格深度门仍失败。下一步先做保守
   单元内微物理重构，再把局域 Planck 扩散替换为非局域、频率依赖的辐射--能量耦合。

新增 6 项模块测试覆盖循环密度闭合、绝热解析关系、含电离能热力学、离散静态扩散、双初态
周期解和禁用数值修补；全项目现场回归为 `302 passed`。`[V]`

## 10. 产物

- `src/eccentric_tde_observer/periodic_dynamic_atmosphere.py`；
- `tests/test_periodic_dynamic_atmosphere.py`；
- `scripts/phase7b4i_periodic_dynamic_energy.py`；
- `outputs/phase7b4i_periodic_dynamic_report.json`；
- `outputs/phase7b4i_periodic_dynamic_phase.csv`；
- `outputs/phase7b4i_periodic_dynamic_profile.csv`；
- `outputs/phase7b4i_periodic_dynamic_convergence.csv`；
- `outputs/phase7b4i_periodic_dynamic_column.png`；
- `outputs/phase7b4i_energy_convergence.png`。
