# Phase 5B2：三维非线性局域 Hamiltonian 与导数门槛

## 1. 阶段定位

Phase 5B2 实现了 ZO 无扭曲偏心盘在任意局域 $e$ 与径向偏心梯度下的三维呼吸和轨道平均
Hamiltonian 核。它是下一步全局高偏心边值本征问题的局域系数生成器，不是已经求出的
$e(a)$ 或 $\widetilde{\omega}$。`[L/V/O]`

新增文件：

- `src/eccentric_tde_observer/nonlinear_hamiltonian.py`：局域呼吸、$F$ 和五点偏导；
- `scripts/phase5b2_nonlinear_hamiltonian_gate.py`：130 状态网格、解析极限和导数门；
- `outputs/phase5b2_nonlinear_hamiltonian_report.json`：判据、误差和授权；
- `outputs/phase5b2_hamiltonian_surface.csv`：$(e,q)$ 网格的完整局域状态；
- `outputs/phase5b2_derivative_convergence.csv`：三种状态、四档步长的偏导结果。

## 2. 坐标与非交叉域

ZO Eq. (38) 使用

$$
f=e+a\frac{\mathrm{d}e}{\mathrm{d}a}.
$$

这里的 $f$ 不是轨道真近点角。对无扭曲盘，Eq. (31) 化为

$$
j(E)=
\frac{1-ef-(f-e)\cos E}{\sqrt{1-e^{2}}}.
$$

再定义非线性参数

$$
q=\frac{f-e}{1-ef},
$$

则本阶段只接受 $1-ef>0$ 且 $|q|<1$ 的状态。扫描图使用

$$
f=\frac{e+q}{1+eq}
$$

从 $(e,q)$ 生成 $f$，因此不会靠裁剪把相交轨道拉回有效域。`[L/V]`

## 3. 垂向呼吸与 Hamiltonian

### 3.1 正周期呼吸支

每个 $(e,f)$ 都重新求解 ZO Eq. (35)：

$$
(1-e\cos E)\frac{\mathrm{d}^{2}h}{\mathrm{d}E^{2}}
-e\sin E\frac{\mathrm{d}h}{\mathrm{d}E}
+h
=
\frac{(1-e\cos E)^{3}}{j^{\gamma-1}h^{\gamma}},
$$

并施加

$$
\frac{\mathrm{d}h}{\mathrm{d}E}(0)
=
\frac{\mathrm{d}h}{\mathrm{d}E}(\pi)=0.
$$

代码以 $u=\ln h$ 为变量，所以 $h>0$ 是变量变换的结果，不需要 floor。射击根使用 DOP853
和 Brent 求根；同时反号状态利用严格对称
$F(-e,-f)=F(e,f)$ 对应的半轨道平移，避免在物理等价但数值不稳定的反向射击支上积累
误差。`[L/V]`

### 3.2 轨道平均能量

三维无量纲 Hamiltonian 是 ZO Eq. (34)：

$$
F(e,f)=
\frac{\gamma+1}{4\pi(\gamma-1)}
\int_{0}^{2\pi}
\frac{1-e\cos E}{(jh)^{\gamma-1}}\,\mathrm{d}E.
$$

高偏心近心点的 $h$ 可窄到 $10^{-6}$ 以下，普通均匀异常角梯形积分收敛很慢。因此正式
实现把上式被积函数作为第三个 ODE 状态与 $u,u'$ 同步自适应推进；它不是在结果后对能量
重归一化。独立的 1024 点周期求积在中等状态回收同一 $F$。`[V]`

### 3.3 Eq. (38) 所需偏导

全局本征方程需要

$$
\frac{\partial F}{\partial e},\qquad
\frac{\partial F}{\partial f},\qquad
\frac{\partial^{2}F}{\partial e\partial f},\qquad
\frac{\partial^{2}F}{\partial f^{2}}.
$$

本阶段先使用显式五点中心模板，并要求完整模板都在非交叉域内；任何一个偏移状态越域就
拒绝，禁止缩步夹回边界。Phase 5B3 建表时仍需另做插值导数与直接五点导数的留出对照。
`[A/V/O]`

## 4. 解析与回归控制

### 4.1 圆盘与常偏心支

圆盘精确回收

$$
h=1,\qquad j=1,\qquad
F=\frac{\gamma+1}{2(\gamma-1)}=3.5.
$$

$f=e$ 时 $ae_{a}=0$，新求解器逐点对照既有 ZO Eq. (35) 常偏心呼吸代码；
$e=0.2,0.6,0.8$ 的最坏高度相对差为 $1.968403\times10^{-11}$。`[V]`

### 4.2 正确线性展开

与 Ogilvie--Lynch Eq. (44) 相容的二次展开为

$$
F=
\frac{\gamma+1}{2(\gamma-1)}
+\frac{1}{4\gamma}
\left[
(5\gamma-9)e^{2}
+2(4\gamma-3)e(f-e)
+(2\gamma-1)(f-e)^{2}
\right]
+O(4).
$$

对 $\gamma=4/3$，它也可写成

$$
F=3.5-e^{2}+\frac{1}{4}ef+\frac{5}{16}f^{2}+O(4).
$$

沿 $(e,f)=A(1,0.7)$ 把 $A$ 从 0.08 减到 0.01，非线性值减二次式的对数斜率为
$4.006739$，回收四阶余项。该控制再次说明主源 TeX 中字面的
$(5\gamma-9\gamma)e^{2}$ 与随后 Eq. (44) 不相容。`[L/V/O]`

## 5. 数值门槛

130 个状态覆盖 $0\le e\le0.9$、$-0.75\le q\le0.75$。结果为：

- 全部状态 $h>0$，最小值 $6.820037\times10^{-7}$；
- 最坏远心点周期边界残差 $7.230642\times10^{-13}$；
- 同时反号对称最坏相对差为 0；
- 粗/细 ODE 容差的最坏 $F$ 相对差 $1.570610\times10^{-11}$；
- 三种导数状态、$4\times10^{-3}$ 到 $5\times10^{-4}$ 步长的最坏导数向量变化
  $3.770135\times10^{-6}<10^{-5}$。`[V]`

表面网格中的 $F$ 从 $3.122276$ 到 $4.095870$。该范围只是所扫描非交叉局域域的结果，
不是全局模式的频率范围。`[V]`

## 6. 图像与逐图解释

### 6.1 非线性 Hamiltonian 面

![ZO nonlinear Hamiltonian surface](../outputs/phase5b2_hamiltonian_surface.png)

**怎么看。** 横轴是偏心率 $e$，纵轴是非线性参数 $q$，颜色是每一点完整解呼吸方程后
得到的 $F(e,f)$。颜色面明显不只依赖 $e$，而且对正、负梯度响应不同。

**验证了什么。** `[V]` 局域 Hamiltonian 在全部 130 个非交叉状态上连续且有限。高偏心
负 $q$ 区先降低，接近 $e=0.9$ 时又快速抬升；正 $q$ 则总体增加能量。这种曲率正是
Eq. (38) 中二阶偏导不能用常数线性系数替代的原因。

**不能证明什么。** `[O]` 色块是验证采样，不是正式 BVP 插值表；图也没有施加全局两端
边界或固定 $e_{\rm in}$，不能从最低颜色位置读出本征模。

### 6.2 呼吸与 Jacobian

![Nonlinear vertical breathing profiles](../outputs/phase5b2_vertical_breathing_profiles.png)

**怎么看。** 左图用对数纵轴比较圆盘、常偏心 $e=0.6$ 和两个 $e=0.9$ 梯度状态的
$h(E)$；右图是相同状态的 $j(E)$。图中所有 $j$ 都保持正值。

**验证了什么。** `[V]` 高偏心近心点压缩可跨越六个数量级，并且 $q$ 会显著改变
Jacobian 在轨道上的分布。$q=-0.5$ 和 $q=+0.5$ 的呼吸曲线在图上局部接近，但对应的
$j$ 完全不同，因此 Hamiltonian 也不同。

**不能证明什么。** `[O]` 极薄 $h$ 只是绝热三维呼吸解；它没有加入冷却、辐射反作用或
磁压力，不能直接解释成实际光球厚度。

### 6.3 线性极限与导数稳定性

![Nonlinear Hamiltonian local controls](../outputs/phase5b2_local_hamiltonian_controls.png)

**怎么看。** 左图把非线性 $F$ 与正确二次式的差和四阶参考并列；右图显示三种状态在
逐次减半五点步长下的完整导数向量变化，黑虚线是 $10^{-5}$ 门。

**验证了什么。** `[V]` 左图四个点与四阶线重合；右图全部低于门槛，最坏点来自
$e=0.9,q=-0.5$ 的 $4\times10^{-3}$ 对 $2\times10^{-3}$ 比较。继续减半后误差下降，
没有通过选择一个“最好看”的单一步长掩盖敏感性。

**不能证明什么。** `[O]` 局域偏导稳定不等于全局 BVP 已收敛；正式插值表还要分别检查
表分辨率、留出点偏导和边界附近有效域。

## 7. 阶段判定与下一步

- `[V]` 非线性局域 Hamiltonian、呼吸、对称性、线性极限和五点偏导全部通过；
- `[V]` Phase 5B3 获准实现全局非线性边值问题；
- `[O]` 尚未复现 ZO Figs. 6--7 的高偏心 $e(a)$ 与 $\widetilde{\omega}$；
- `[O]` 严格域源仍不得把 $\Phi$ 或 $t/P_{\rm prec}$ 改写为 day；
- `[O]` [[eccentric_tde_observer/docs/phase5b1_linear_apsidal_mode_gate|Phase 5B1]] 发现的
  Eq. (48) 十倍物理归一化差异仍保持开放。

## 8. 复现

```bash
uv run python scripts/phase5b2_nonlinear_hamiltonian_gate.py --output-dir outputs
uv run pytest -q tests/test_nonlinear_hamiltonian.py tests/test_phase5b2_nonlinear_hamiltonian_gate.py
```

本阶段完成后的现场完整回归为 `549 passed in 58.85s`。`[V]`

全局模式的后续顺序见[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]。
