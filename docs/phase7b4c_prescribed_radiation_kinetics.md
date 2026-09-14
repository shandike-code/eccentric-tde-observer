# Phase 7B4c：规定辐射场与 H/He 基态周期布居耦合

> [!abstract] 阶段结论
> `[V]` 本阶段已把逐相位规定的 $J_{\nu}$ 映射为 H I、He I、He II 光致电离率，并送入
> Phase 7B4b 的电荷自洽周期求解器。零辐射场严格回到 7B4b；热详细平衡控制的瞬时布居
> 回到 LTE，最大离子分数误差为 $2.22\times10^{-16}$。
> `[A-sensitivity]` 用 $J_{\nu}=W B_{\nu}(T_{0})$ 扫描 $W=0$ 到 $1$ 时，周期布居相对
> 零场最多改变 $0.99776$，说明辐射闭合远比当前轨道时间滞后重要。
> `[O]` $W$ 不是由转移方程求出的，本阶段没有 $J_{\nu}$--布居迭代、能量方程、激发态或
> 输出谱，因此仍不是自洽 NLTE 大气。

导航：[[eccentric_tde_observer/README|项目 README]] ·
[[eccentric_tde_observer/docs/phase7b4b_orbit_coupled_kinetics|Phase 7B4b 无辐射轨道动力学]] ·
[[eccentric_tde_observer/docs/phase7b3_atomic_continuum|Phase 7B3 原子连续谱控制]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

---

## 1. 为什么 7B4c 先用规定辐射场

Phase 7B4b 已证明：在当前规定 ZO 中面中，动态布居相对无辐射瞬时稳态的最大差只有
$3.57\times10^{-7}$，但无辐射稳态相对 LTE 的最大差达到 $0.99909$。因此下一步首先要
检查光致电离率进入同一周期求解器后，零场极限、详细平衡、守恒和收敛是否仍成立。`[V]`

直接把 Phase 7B2 的未知 $J_{\nu}$ 与布居联立，会同时混入辐射转移、原子率和非线性迭代
三类问题。7B4c 先规定 $J_{\nu}$，只验证“辐射场到布居”的接口。这一拆分是数值验收顺序，
不是对真实盘辐射场的主张。`[A-control]`

## 2. 规定辐射场与光致电离率

当前采用同温度稀释 Planck 场：

$$
J_{\nu}(t)=W B_{\nu}\!\left[T_{0}(t)\right],
$$

其中 $T_{0}(t)$ 是 Phase 7B4b 已使用的灰 Eddington 中面温度，$W$ 是规定的无量纲稀释
因子。它既不是几何计算得到的稀释，也不是 Phase 7B2 转移解。`[A-control]`

每个基态靶离子的光致电离率为

$$
\Gamma_{i}(t)
=4\pi\int_{\nu_{i}}^{\nu_{\max}}
\frac{\sigma_{i}(\nu)J_{\nu}(t)}{h\nu}\,\mathrm d\nu.
$$

截面使用 Phase 7B3 已验证的 Verner 等（1996）H I、He I 和 He II 基态拟合。正式网格从
$1$ 到 $5000\ \mathrm{eV}$，并把 $13.60$、$24.59$ 和 $54.42\ \mathrm{eV}$ 三条离化边
精确插入网格，禁止跨越不连续边做单个梯形。最高中面温度为 $1.277\times10^{5}\ \mathrm K$，
在 $5000\ \mathrm{eV}$ 处已有 $h\nu/(kT)>450$；正式频率收敛仍另外相对 8193 点网格检查。
`[L/A/V]`

## 3. 两条必须分开的复合路径

### 3.1 文献总辐射复合敏感性 `[A-sensitivity]`

用于 $W$ 扫描的上、下跃迁率为

$$
u_{i}=\Gamma_{i}+n_{\rm e}C_{i},
$$

$$
d_{i}=n_{\rm e}\alpha_{i}^{\rm RR}
+n_{\rm e}^{2}\beta_{i}^{\rm DB}.
$$

这里 $C_{i}$ 是 Voronov 碰撞电离率，$\alpha_{i}^{\rm RR}$ 是 Verner--Ferland 总辐射复合率，
$\beta_{i}^{\rm DB}=C_{i}/S_{i}$ 是 Phase 7B4a 的三体详细平衡控制。该路径保留文献率，但
$W$ 是人为扫描量，所以只比较布居形状和敏感性，不把某个 $W$ 选成物理解。`[L/A/O]`

### 3.2 热详细平衡控制 `[A-control]`

总辐射复合率与基态光电离截面不是逐微观通道配对的数据。为了独立检验方程方向和 LTE
极限，另构造

$$
\alpha_{i}^{\rm rad,DB}(T)
=\frac{\Gamma_{i}[B_{\nu}(T)]}{S_{i}(T)},
$$

并继续使用

$$
\beta_{i}^{\rm DB}(T)=\frac{C_{i}(T)}{S_{i}(T)}.
$$

于是

$$
\frac{u_{i}}{d_{i}}
=\frac{S_{i}(T)}{n_{\rm e}},
$$

逐跃迁严格回到同一组基态 Saha 比值。这条构造型逆率只用于验收，不替换文献总辐射复合
率。沿当前轨道，构造型 $\alpha_{i}^{\rm rad,DB}$ 与文献总复合率之比位于
$0.188$--$1.238$；二者不能在代码中悄悄混称为同一个率。`[A-control/V/O]`

## 4. 接入周期隐式求解器

Phase 7B4c 不改 Phase 7B4b 的电荷自洽后向 Euler 方程：

$$
\left(\mathbf I-\Delta t\,\mathbf R^{n+1}\right)
\boldsymbol x^{n+1}=\boldsymbol x^{n},
$$

$$
n_{\rm e}
=n_{\rm H}x_{\rm H\,\rm II}
+n_{\rm He}\left(x_{\rm He\,\rm II}+2x_{\rm He\,\rm III}\right).
$$

新量只有逐相位 $\Gamma_{i}(t)$。电子密度仍在每个隐式步内二分求根，H/He 粒子数由守恒
方程保持；没有布居裁剪、floor、`nan_to_num` 或事后重归一化。`[V]`

## 5. 必须通过的四个接口门

### 5.1 零场回归

$W=0$ 生成逐元素严格为零的 $\Gamma_{i}$。它与显式传入零率的 Phase 7B4b 路径逐点完全
相同，最大离子分数差为 $0$。`[V]`

### 5.2 热详细平衡

在 $J_{\nu}=B_{\nu}(T_{0})$ 和构造型辐射逆率下，逐相位瞬时稳态相对 LTE 的最大分数误差
为 $2.22\times10^{-16}$；完整动态周期解相对逐相位 LTE 的最大差为
$2.52\times10^{-12}$，后者来自有限背景时间离散。`[V]`

### 5.3 正初值独立性

在中间敏感区 $W=10^{-4}$，生产初值与
$\boldsymbol x_{\rm H}=(0.8,0.2)$、
$\boldsymbol x_{\rm He}=(0.6,0.3,0.1)$ 两组正初值的最终周期解最大差为
$6.66\times10^{-16}$。`[V]`

### 5.4 守恒

全部 $W$ 扫描、详细平衡和替代初值计算的最大相对电荷残差为
$5.76\times10^{-16}$，最大元素粒子数残差为 $4.44\times10^{-16}$。`[V]`

## 6. 规定场敏感性结果

扫描点为 $W=0$ 以及 $10^{-10}$ 到 $1$ 的逐十倍序列，不进行拟合。关键轨道平均分数为：

| $W$ | $\langle x_{\rm H\,\rm II}\rangle$ | $\langle x_{\rm He\,\rm I}\rangle$ | $\langle x_{\rm He\,\rm II}\rangle$ | $\langle x_{\rm He\,\rm III}\rangle$ |
|---:|---:|---:|---:|---:|
| $0$ | 0.999862 | 0.008365 | 0.381917 | 0.609718 |
| $10^{-6}$ | 0.999864 | 0.006541 | 0.375601 | 0.617858 |
| $10^{-4}$ | 0.999952 | $2.760\times10^{-4}$ | 0.246767 | 0.752957 |
| $10^{-2}$ | 0.999999 | $9.347\times10^{-7}$ | 0.053002 | 0.946997 |
| $1$ | 1.000000 | $1.660\times10^{-10}$ | $8.661\times10^{-4}$ | 0.999134 |

H 在整个扫描中已经接近全电离；氦对规定辐射最敏感。$W=0$ 到 $W=1$ 的动态离子分数
最大变化为 $0.99776$。即使如此，不能说真实盘对应表中任何一行，因为当前没有方程决定
$W$。`[A-sensitivity/V/O]`

所有 $W$ 下的动态--瞬时稳态差都不超过零场的 $3.57\times10^{-7}$，并随辐射增强继续
减小。这再次说明在当前中面控制上，主要不确定性是辐射场本身，而不是率方程追不上轨道。
`[V]`

## 7. 主图逐面解释

![Phase 7B4c 规定辐射场轨道动力学](../outputs/phase7b4c_prescribed_radiation_kinetics.png)

### (a) Prescribed same-temperature Planck field

三条曲线是 $W=1$ 时逐相位 H I、He I 和 He II 光致电离率。它们继承灰中面温度在近心点
附近的急剧上升；He II 的高阈值使其轨道变化最强。图内所有文字均为英文。`[A/V]`

### (b) Thermal detailed-balance control

蓝线是瞬时详细平衡稳态减去 LTE，只剩双精度噪声；橙线是完整动态解减去逐相位 LTE，
最高为 $2.52\times10^{-12}$。它验证了热逆率、相位接口和隐式推进，但不是新物理谱。
`[A-control/V]`

### (c) Prescribed-field dilution sensitivity

曲线给五个代表 $W$ 的动态 He III 分数。弱场时远心点附近 He II 仍占重要比例；增强规定
场会把氦推向 He III。选择这些 $W$ 是展示整个扫描，不是寻找“最好看”的电离曲线。
`[A-sensitivity/V]`

### (d) Radiation sensitivity versus kinetic lag

蓝线量化相对零场周期解的最大变化，橙线量化动态解相对同一 $W$ 瞬时稳态的滞后。蓝线
跨越近六个数量级并接近 1，橙线始终低于 $4\times10^{-7}$；两者直接分开“未知辐射场”
和“时间推进误差”。`[V/O]`

## 8. 三条独立收敛轴

![Phase 7B4c 数值收敛](../outputs/phase7b4c_prescribed_radiation_convergence.png)

### (a) Photoionization frequency convergence

2049 点正式能量网格相对 8193 点参考的最大率误差为 $4.50\times10^{-4}$，由高阈值
He II 控制；H I 和 He I 分别为 $4.71\times10^{-5}$ 和 $9.03\times10^{-5}$。4097 点时
最大误差进一步降到 $8.99\times10^{-5}$。`[V]`

### (b) Orbit time-step convergence

固定 128 个背景节点，在每段内细分到 1024 个时间点；相对 2048 点参考的最大离子分数
误差为 $1.08\times10^{-9}$。`[V]`

### (c) ZO source-grid convergence

独立重建 256、512、1024 和 2048 点 ZO 源。1024 点相对 2048 点的最大离子分数 RMS 误差
为 $1.04\times10^{-5}$，仍是当前主导离散误差。`[V]`

## 9. 文件、测试与复现

核心文件：

- `src/eccentric_tde_observer/prescribed_radiation.py`：边分辨能量网格和规定 Planck 场率接口；
- `tests/test_prescribed_radiation.py`：零场、线性稀释、详细平衡、固定点和拒绝测试；
- `scripts/phase7b4c_prescribed_radiation_kinetics.py`：完整证据生成脚本。

机器可读产物：

- `outputs/phase7b4c_prescribed_radiation_report.json`：假设、残差、敏感性、收敛和阶段边界；
- `outputs/phase7b4c_prescribed_radiation_orbits.csv`：全部 $W$ 的逐相位光致率与布居；
- `outputs/phase7b4c_dilution_sensitivity.csv`：连续敏感性诊断；
- `outputs/phase7b4c_convergence.csv`：频率、时间步和源相位三条收敛轴；
- `outputs/phase7b4c_prescribed_radiation_kinetics.png`：四面板主图；
- `outputs/phase7b4c_prescribed_radiation_convergence.png`：三面板收敛图。

复现命令：

```bash
cd /Users/shandike/Downloads/A_USTCer/8.3/eccentric_tde_observer
uv run python scripts/phase7b4c_prescribed_radiation_kinetics.py --output-dir outputs
uv run pytest -q
```

`tests/test_prescribed_radiation.py` 的 7 项专项测试和全项目 `249 passed` 均通过；Markdown
数学规范检查无待修改文件。`[V]`

## 10. 当前允许与禁止的结论

> `[V]` 可以说：规定的逐相位 $J_{\nu}$ 已能通过可追溯 Verner 截面生成光致电离率，并在
> 电荷自洽周期求解器中保持零场极限、热详细平衡、正初值独立性、粒子数、电荷和分层收敛。

> `[A-sensitivity/V]` 可以说：在同温度稀释 Planck 控制中，氦布居对 $W$ 极为敏感，而
> 当前中面动力学滞后很小。

> `[O]` 不能说：$W=1$ 或任何其他 $W$ 是真实盘辐射场；也不能把这些布居输出成 NLTE
> 连续谱。当前没有自洽 $J_{\nu}$、受激复合、激发态、气体能量方程或耗散深度闭合。

[[eccentric_tde_observer/docs/phase7b4d_coupled_slab|Phase 7B4d]] 已完成固定温度、固定密度
$J_{\nu}$--基态布居--opacity 迭代，并通过零 opacity、纯吸收、Planck/LTE 固定点、极端
初态和分层收敛控制；
[[eccentric_tde_observer/docs/phase7b4e_continuum_emission|Phase 7B4e]] 又完成同截面基态 Milne
连续发射、Kirchhoff/LTE、光子率和固定温度能量账本。下一步先求规定加热下的温度平衡；
仍不应直接输出最终大气谱。`[V/O]`
