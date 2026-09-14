# Phase 7B4d：固定温度板层中的辐射--布居--opacity 反馈

> [!abstract] 阶段结论
> `[V]` 本阶段首次把 1D 转移求得的 $J_{\nu}(z)$ 回送到 H I、He I、He II 基态光致
> 电离率，再由新布居更新束缚--自由吸收和电子散射。两个极端初态在 16 次 Picard 迭代后
> 到达同一固定点，最大布居差为 $7.78\times10^{-12}$。
> `[A-control]` 正式控制是固定 $T$、固定 $\rho$、单侧受照且无内部复合连续发射的板层；
> 它只验证 $J_{\nu}$--基态布居--opacity 反馈，不是 ZO 环带大气，也不是最终 NLTE 谱。
> `[O]` 激发态、复合连续发射、bound--bound 转移、气体能量方程和轨道周期耦合仍未闭合。

导航：[[eccentric_tde_observer/README|项目 README]] ·
[[eccentric_tde_observer/docs/phase7b4c_prescribed_radiation_kinetics|Phase 7B4c 规定辐射场]] ·
[[eccentric_tde_observer/docs/phase7b2_transfer_controls|Phase 7B2 转移控制]] ·
[[eccentric_tde_observer/docs/phase7b3_atomic_continuum|Phase 7B3 原子连续谱]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]]

---

## 1. 7B4d 到底新增了什么

Phase 7B4c 使用规定场

$$
J_{\nu}=W B_{\nu}(T_{\rm rad}),
$$

所以布居不能反过来改变辐射场。7B4d 把这条单向箭头闭合为最小固定点：

$$
\boldsymbol x^{(k)}
\longrightarrow
\chi_{\nu}^{(k)}
\longrightarrow
J_{\nu}^{(k)}
\longrightarrow
\Gamma_{i}^{(k)}
\longrightarrow
\boldsymbol x_{\rm eq}^{(k)}.
$$

这里 $\boldsymbol x$ 只含 H I/H II 和 He I/He II/He III 基态电离分数。温度、密度、板层
厚度和外边界辐射均保持规定值。这个阶段隔离检验非线性反馈是否守恒、是否有稳定固定点以及
对离散网格是否收敛。`[A-control/V]`

## 2. 从布居构造连续 opacity

三条基态光致吸收体积系数为

$$
\chi_{\nu,{\rm H\,I}}^{\rm bf}
=n_{\rm H}x_{\rm H\,\rm I}\sigma_{\rm H\,\rm I}(\nu),
$$

$$
\chi_{\nu,{\rm He\,I}}^{\rm bf}
=n_{\rm He}x_{\rm He\,\rm I}\sigma_{\rm He\,\rm I}(\nu),
$$

$$
\chi_{\nu,{\rm He\,II}}^{\rm bf}
=n_{\rm He}x_{\rm He\,\rm II}\sigma_{\rm He\,\rm II}(\nu).
$$

$\sigma_{i}(\nu)$ 使用 Phase 7B3 已核定的 Verner 等（1996）基态截面。电子密度由电荷中性
直接计算：

$$
n_{\rm e}
=n_{\rm H}x_{\rm H\,\rm II}
+n_{\rm He}\left(x_{\rm He\,\rm II}+2x_{\rm He\,\rm III}\right),
$$

$$
\chi_{\nu}^{\rm es}=n_{\rm e}\sigma_{\rm T}.
$$

于是

$$
\chi_{\nu}=\chi_{\nu}^{\rm bf}+\chi_{\nu}^{\rm es},
\qquad
\epsilon_{\nu}=\frac{\chi_{\nu}^{\rm bf}}{\chi_{\nu}}.
$$

真空单元的 $\chi_{\nu}=0$ 是解析分支，源函数不影响形式解；代码没有为分母添加 floor。
没有使用 `clip`、`nan_to_num` 或事后布居重归一化。`[V]`

当前 opacity 没有加入激发态光致电离、金属、非 LTE 受激复合修正或复合连续发射，因此不能
把它称为完整 NLTE 连续 opacity。`[O]`

## 3. 转移方程与主控制边界

沿用 Phase 7B2 的静态平面平行转移：

$$
\mu\frac{\mathrm d I_{\nu}}{\mathrm dz}
=-\chi_{\nu}\left(I_{\nu}-S_{\nu}\right),
$$

$$
S_{\nu}
=\epsilon_{\nu}B_{\nu}^{\rm src}
+\left(1-\epsilon_{\nu}\right)J_{\nu}.
$$

主控制取

$$
B_{\nu}^{\rm src}=0,
$$

上边界入射为

$$
I_{\nu}^{\rm top,in}
=10^{-6}B_{\nu}(1.5\times10^{5}\ \mathrm K),
$$

下边界无入射。气体温度固定为 $4.0\times10^{4}\ \mathrm K$，但这里没有用该温度伪造内部
复合连续源；它只进入碰撞电离、辐射复合和三体详细平衡率。换言之，吸收能量在当前转移
控制中作为物质汇项离开辐射场，尚未由能量方程重新发射。`[A-control/O]`

规定板层参数为

$$
\rho=10^{-10}\ \mathrm{g\,cm^{-3}},
\qquad
m_{\rm slab}=10^{-4}\ \mathrm{g\,cm^{-2}}.
$$

它们被选择为透明与极厚之间的中等反馈控制，不来自某个 ZO 面元，也不拟合 TDE。另以
无量纲 `opacity_scale` 从 0 扫到 3，只检验透明到不透明的连续性，不把它作为物理自由参数。
`[A-control]`

## 4. 从 $J_{\nu}$ 更新布居

每个深度的三条光致电离率为

$$
\Gamma_{i}(z)
=4\pi\int_{\nu_{i}}^{\nu_{\max}}
\frac{\sigma_{i}(\nu)J_{\nu}(z)}{h\nu}\,\mathrm d\nu.
$$

向上和向下率继续沿用 7B4c 的文献率路径：

$$
u_{i}=\Gamma_{i}+n_{\rm e}C_{i},
$$

$$
d_{i}=n_{\rm e}\alpha_{i}^{\rm RR}
+n_{\rm e}^{2}\beta_{i}^{\rm DB}.
$$

$C_{i}$ 是 Voronov 碰撞电离率，$\alpha_{i}^{\rm RR}$ 是 Verner--Ferland 总辐射复合率，
$\beta_{i}^{\rm DB}=C_{i}/S_{i}$ 仍是三体详细平衡控制。每个深度联立 H/He 稳态和电荷
中性，得到映射后的 $\boldsymbol x_{\rm eq}^{(k)}$。`[L/A/V]`

正式迭代为

$$
\boldsymbol x^{(k+1)}
=\left(1-\omega\right)\boldsymbol x^{(k)}
+\omega\boldsymbol x_{\rm eq}^{(k)}.
$$

主解取 $\omega=1$；$\omega=0.3,0.5,0.7,1$ 只作数值敏感性。凸组合保持元素粒子数，不做
事后重归一化。固定点残差定义为

$$
R_{\rm fp}
=\max\left|\boldsymbol x_{\rm eq}-\boldsymbol x\right|.
$$

若在最大迭代数内未达到容差，求解器抛出 `CoupledSlabConvergenceError`，不会返回修补解。
`[V]`

## 5. 四个独立验收门

### 5.1 精确透明极限

当 `opacity_scale=0` 时，吸收和散射同时严格为零，形式解逐角保持边界强度。单侧受照控制的
透射能流分数为 1.000000。双侧各向同性规定场另逐点回收 7B4c 的光致电离率。`[V]`

### 5.2 Planck/LTE 详细平衡固定点

双侧边界和内部源都取 $B_{\nu}(T)$，并构造

$$
\alpha_{i}^{\rm rad,DB}
=\frac{\Gamma_{i}[B_{\nu}(T)]}{S_{i}(T)}.
$$

从同温 LTE 布居开始时一次迭代即满足固定点；$J_{\nu}/B_{\nu}-1$ 的最大误差为 0，最大
布居误差为 $7.66\times10^{-18}$，最终固定点残差为 0。该控制只验证方向和详细平衡，
不替代文献总复合率。`[A-control/V]`

### 5.3 纯吸收能量关系

关闭电子散射后，转移方程的边界能流变化与体积吸收汇逐频一致，最大相对能量残差为
$3.59\times10^{-16}$。主解保留电子散射时该残差为 $7.29\times10^{-16}$。`[V]`

### 5.4 极端初态独立性

分别从完全中性和完全电离 H/He 初态开始，两条迭代均在 16 步达到 $10^{-10}$ 更新容差，
最终五个离子分数的最大差为 $7.78\times10^{-12}$。主解固定点残差为
$5.76\times10^{-12}$，最大相对电荷残差为 $1.56\times10^{-16}$。`[V]`

## 6. 主控制结果

正式展示网格使用 513 个对数基点并精确加入三条离化边，最终共 515 个频率点、16 个深度
单元和 16 阶 Gauss--Legendre 角度求积。固定归一化深度 $x=z/L$ 的结果为：

| 位置 | $x_{\rm H\,\rm II}$ | $x_{\rm He\,\rm III}$ |
|---:|---:|---:|
| $x=0.2$ | 0.999403 | 0.674680 |
| $x=0.5$ | 0.999400 | 0.465907 |
| $x=0.8$ | 0.999398 | 0.249604 |

H 主要由 $4\times10^{4}\ \mathrm K$ 的碰撞率维持近全电离；氦的第二次电离对 $54.42\ \mathrm{eV}$
光子衰减很敏感，因此随深度显著下降。三条离化边的总消光光深分别为
$0.1593$、$0.1087$ 和 $3.5635$；入射电离能流中 $0.61765$ 穿过底边界，反射分数只有
$1.99\times10^{-5}$。这些是规定板层控制量，不是 ZO 大气预言。`[A-control/V]`

## 7. 主图逐面解释

![Phase 7B4d 固定温度辐射布居反馈](../outputs/phase7b4d_coupled_slab.png)

### (a) Radiation attenuation

$13.60$ 和 $24.59\ \mathrm{eV}$ 的平均强度缓慢下降；$54.42\ \mathrm{eV}$ 穿过 He II 连续边后
下降约两个数量级。这正是 He III 深度梯度的辐射原因。`[V]`

### (b) Self-consistent ground-state populations

H II 近似保持 1；He III 从照明面向深层下降，He II 对应上升，二者在板层中部附近交叉。
He I 很小。这里“self-consistent”严格只指本阶段闭合的 $J_{\nu}$--基态布居--opacity 固定点。
`[V/O]`

### (c) Population-dependent optical depth

累计光深使用最终布居重新计算，不是固定 LTE opacity。He II 边最厚，因而决定本控制的
主要频率选择性；曲线保持原始正 opacity，没有裁剪。`[V]`

### (d) Initial-state convergence

完全中性与完全电离初态从相反方向进入同一固定点。两条曲线都实际穿过 $10^{-10}$ 容差；
没有删除早期大残差点。`[V]`

## 8. 收敛与反馈图逐面解释

![Phase 7B4d 收敛与反馈控制](../outputs/phase7b4d_coupled_slab_convergence.png)

### (a) Population convergence

布居误差在固定 $x=0.2,0.5,0.8$ 比较，避免把“第一单元中心随网格移动”误认成数值误差。
513 个频率基点相对 2049 点参考的最大绝对布居差为 $7.42\times10^{-5}$；16 个深度单元
相对 64 单元为 $6.27\times10^{-4}$；16 阶角度求积相对 32 阶为
$1.28\times10^{-3}$。角度离散是当前布居诊断的主误差，已如实保留。`[V]`

### (b) Transfer convergence

同三条扫描中，透射能流的相对差分别为 $1.22\times10^{-4}$、$2.89\times10^{-6}$ 和
$1.26\times10^{-4}$。能流比局域布居更快收敛，但二者没有被混成同一指标。`[V]`

### (c) Numerical relaxation sensitivity

$\omega=0.3$ 到 1 得到的最大布居差仅 $1.22\times10^{-11}$，但迭代数从 100 降到 17。
因此正式控制采用未欠松弛的 $\omega=1$；不是挑选一个改变答案的数值参数。`[V]`

### (d) Transparent-to-opaque control

`opacity_scale=0` 精确回到透明板层。随控制尺度增加，透射能流和深层 He III 连续下降，
没有不连续电离跳变。该横轴只检验反馈连续性，不允许当成拟合参数。`[A-control/V]`

## 9. 文件与复现

核心文件：

- `src/eccentric_tde_observer/radiation_population_coupling.py`：布居 opacity、$J_{\nu}$ 积分和固定点求解；
- `tests/test_radiation_population_coupling.py`：透明极限、规定场、LTE 固定点、能量、初态和拒绝测试；
- `scripts/phase7b4d_coupled_slab.py`：主控制、敏感性、收敛和制图。

机器可读产物：

- `outputs/phase7b4d_coupled_slab_report.json`：阶段参数、残差、固定点和边界；
- `outputs/phase7b4d_coupled_slab_depth.csv`：逐深度布居、电子密度和光致率；
- `outputs/phase7b4d_opacity_feedback_sensitivity.csv`：透明到不透明反馈扫描；
- `outputs/phase7b4d_coupled_slab_convergence.csv`：频率、深度、角度和欠松弛扫描；
- `outputs/phase7b4d_coupled_slab.png`：四面板主图；
- `outputs/phase7b4d_coupled_slab_convergence.png`：四面板收敛与反馈图。

复现命令：

```bash
cd /Users/shandike/Downloads/A_USTCer/8.3/eccentric_tde_observer
uv run python scripts/phase7b4d_coupled_slab.py --output-dir outputs
uv run pytest -q
```

`tests/test_radiation_population_coupling.py` 的 7 项专项测试与全项目 `256 passed` 均通过；
Markdown 数学规范检查无待修改文件。`[V]`

## 10. 当前允许与禁止的结论

> `[V]` 可以说：在固定 $T$、$\rho$ 和边界辐射的控制板层中，现有 1D 转移、H/He 基态
> 光致率、电荷自洽稳态和布居依赖连续 opacity 已形成稳定、守恒且可收敛的固定点。

> `[A-control/V]` 可以说：在选定中等光深控制中，He II 连续吸收会使 $54.42\ \mathrm{eV}$
> 辐射和 He III 分数随深度明显下降。

> `[O]` 不能说：该板层是某个 ZO 面元的真实大气，或已经生成优于 modified-blackbody 的
> NLTE 输出谱。当前吸收后的能量没有通过气体能量方程和一致复合连续发射返回辐射场，且
> 没有激发态、线转移、速度频率耦合或轨道周期。

这一缺口已由
[[eccentric_tde_observer/docs/phase7b4e_continuum_emission|Phase 7B4e]] 的纯辐射基态 Milne
控制关闭：同一组截面同时生成率、净消光和连续发射，并通过 Kirchhoff/LTE、光子率和
边界--体积能量门。7B4e 仍固定温度，所以下一步必须先求规定加热下的温度平衡，不能直接
推广成 ZO 最终大气谱。`[A/V/O]`
