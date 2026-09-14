# Phase 7A：低温、极低重力静态环带可行性审计

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase4a_annulus_bridge|Phase 4A 动态柱接口]] ·
[[eccentric_tde_observer/docs/phase2c_modified_blackbody|Phase 2C modified-blackbody]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

## 1. 本阶段要回答什么

Phase 7A 不再假定 modified-blackbody 足以代表局域大气，而是先问一个更窄、可验证的问题：

> 在 Phase 4 已筛出的严格准静态面积子集上，能否用可追溯的 TLUSTY 208 静态 H/He
> 环带得到收敛、能量闭合的实际局域连续谱？

若答案为“能”，下一步才可以比较 blackbody、modified-blackbody 与 atmosphere spectrum；
若答案为“不能”，失败点必须保留，且不得把灰初值、未收敛迭代或邻点外推当作大气谱。
本阶段不改 ZO 动力学源，不加入盘风，不拟合 TDE，也不进入 Phase 7B。`[A/V]`

TLUSTY 的文献基础与盘垂向 NLTE 结构可由
[[markdown_papers/astro-ph_9804288_Hubeny_NLTE_vertical_structure|Hubeny 与 Hubeny 1998]]
进入；本项目采用[官方 TLUSTY 208 软件包](https://www.as.arizona.edu/~hubeny/tlusty208-package/)
及其中的 H/He 原子数据。静态 annulus 的三个输入坐标仍沿用
[[markdown_papers/astro-ph_0602499|Davis 与 Hubeny 2006]]。`[L]`

## 2. 从 ZO 动态柱到 TLUSTY 输入

每个局域柱由三个直接参数指定：

$$
T_{\rm eff}(a,E),\qquad
m_{0}(a,E)=\frac{\Sigma(a,E)}{2},\qquad
Q(a,E)=Q_{\rm pressure}(a,E).
$$

这里 $m_{0}$ 是从表面到中面的单侧柱质量，单位为
$\mathrm{g\,cm^{-2}}$；$Q_{\rm pressure}$ 是 Phase 4A 从 ZO 呼吸方程得到的瞬时共动等效
垂向重力系数，单位为 $\mathrm{s^{-2}}$。把动态柱瞬时映射成静态环带仍是工作假设，只有

$$
\epsilon_{\rm dyn}
=\frac{\left|\mathrm d\ln H/\mathrm dt\right|}
{\sqrt{Q_{\rm pressure}}}<0.1
$$

的严格子集才进入本轮代表柱选择。`[A]`

TLUSTY 输出的 Eddington flux 为 $H_{\nu}$，项目转换成单面物理通量

$$
F_{\nu}=4\pi H_{\nu}.
$$

频率积分必须满足

$$
\delta_{\rm E}
=\frac{\int F_{\nu}\,\mathrm d\nu}
{\sigma_{\rm SB}T_{\rm eff}^{4}}-1.
$$

这个关系只检查能量闭合；它不能单独证明垂向结构已经收敛。`[L/V]`

## 3. 代表柱怎样选择

完整严格源采用 $65\times1024$ 个 $(a,E)$ 网格点。满足
$\epsilon_{\rm dyn}<0.1$ 的点有 21,970 个，未通过的点有 44,590 个。严格子集分别承载
全源 corrected 面积、玻尔兹曼功率和光学控制带功率的
$12.9165\%$、$6.7358\%$ 和 $7.2760\%$。`[V]`

聚类坐标是三个经过各自范围归一化的对数量：

$$
\boldsymbol x
=\operatorname{scale}
\left(
\log_{10}T_{\rm eff},
\log_{10}m_{0},
\log_{10}Q
\right).
$$

每个点的抽样权重等量混合三种在严格子集内分别归一化的权重：

$$
w=\frac{w_{\rm A,\rm corr}+w_{\rm bol}+w_{\rm opt}}{3}.
$$

$w_{\rm A,\rm corr}$ 使用 Erratum corrected 面积；$w_{\rm bol}$ 使用
$\mathrm dA_{\rm corr}\,\sigma_{\rm SB}T_{\rm eff}^{4}$；$w_{\rm opt}$ 只用黑体
$5\times10^{14}$--$10^{15}\ \mathrm{Hz}$ 带功率帮助覆盖光学贡献，不是大气解。确定性加权
medoid 算法最终选择 12 个真实网格点，不产生虚构的平均环带。加权均方覆盖距离为
$0.05759$，最大距离为 $0.17727$。`[A/V]`

完整逐点参数、簇权重和证据路径见
`outputs/phase7a_representative_annuli.csv`。

## 4. 求解器与验收门

### 4.1 可复现构建

`scripts/bootstrap_tlusty208_hhe.py` 完成以下操作：

1. 下载官方 `tl208-s54.tar.gz`；
2. 强制核对 SHA-256
   `ec9febdc1795f2c1bbe948ea1736bed663aac9238b290483b517201132f85e4a`；
3. 只缩小 H/He 连续谱所需静态数组上限，不改 TLUSTY 物理方程；
4. 用 `gfortran` 的 legacy 兼容选项编译；
5. 把来源、哈希、编译器、数组上限和 `source_physics_modified=false` 写入构建清单。

官方包内有指向可选大型分子线表的断开符号链接；构建脚本保留这些链接，但本阶段只要求并
检查实际使用的 `h1.dat`、`he1.dat`、`he2.dat`。没有补造缺失分子数据。`[V]`

新二进制第一次人工控制重跑遗漏了 TLUSTY unit 1 的 disk 标志，程序进入普通恒星大气分支，
出现 Fortran `STOP` 文本却仍返回进程码 0。该目录保留在
`outputs/phase7a_tlusty208_rebuild_validation/lte_hhe` 并明确拒绝；正式控制同时要求
`FINAL DISK RING MODEL`、结构迭代文件和谱文件，不能只看返回码。`[V]`

### 4.2 原子与频率边界

第一轮是 H/He 可行性审计：H I、H II、He I、He II、He III；默认关闭 bound--bound
线，只求连续谱。LTE 是进入非线性结构求解的第一层；只有 LTE 模型收敛后才允许以其为初值
切换到 NLTE。该顺序不是把 LTE 称为最终大气，而是避免把“NLTE 失败”与“初始结构从未
成立”混为一谈。金属、Compton 完整处理、外部辐照和真实线谱均未在本轮声称完成。`[A/O]`

### 4.3 数值接受条件

一个模型只有同时满足以下条件才记为可接受：

$$
\max\left|\frac{\delta\psi}{\psi}\right|<10^{-3},\qquad
|\delta_{\rm E}|<10^{-2},\qquad
\text{unit 13 spectrum exists}.
$$

其中 $\psi$ 是 TLUSTY 迭代状态向量。没有 `fort.13`、结构改变量过大或能量残差超限的点都
保留为失败，不用 `nan_to_num`、`clip`、floor、删除点或事后重归一化处理。`[V]`

## 5. 先验证软件链，再检验实际柱

使用官方示例参数的 H/He 控制结果为：

| 控制 | 最终迭代 | 最大相对改变量 | 能量残差 | 结论 |
|---|---:|---:|---:|---|
| LTE H/He | 9 | $1.03\times10^{-4}$ | $4.10\times10^{-4}$ | 通过 |
| NLTE H/He continuum restart | 9 | $4.53\times10^{-4}$ | $4.32\times10^{-4}$ | 通过 |

因此 TLUSTY 208 二进制、H/He 输入、$H_{\nu}\rightarrow F_{\nu}$ 转换以及 LTE 到 NLTE
重启路径可以在正常控制问题上工作。后面的实际柱失败不能简单归因于“程序根本不能运行”。
`[V]`

## 6. 实际代表柱的结果

### 6.1 灰初值只是诊断

12 个代表柱的灰初值均报告

$$
\frac{H_{\rm rad}}{H_{\rm gas}}=7.32\text{--}8.57.
$$

这说明 TLUSTY 灰初始化器把它们置于辐射压尺度明显大于气体压尺度的区域。`NITER=0` 的
输出没有经过完整结构迭代；即使存在 `fort.13`，也只能用来检查初值和能量量级，不能进入
blackbody/modified-blackbody/atmosphere 的正式谱比较。灰初值的能量残差实际范围约为
$-9.28\times10^{-3}$ 到 $2.11\times10^{-2}$。`[V]`

### 6.2 直接 LTE 全部失败

12 个实际代表柱从各自灰初值直接求 LTE，最终最大相对改变量落在
$2.16\times10^{16}$--$6.44\times10^{27}$，全部没有生成可接受的 `fort.13`。因此结果是

$$
N_{\rm accepted}=0/12.
$$

这不是“某几个坏点被删去”，而是当前严格子集没有一个代表柱通过正式大气谱验收。`[V]`

### 6.3 代表柱 03 的连续续接

为了区分“灰初值太远”和“目标参数本身很困难”，代表柱 03 固定
$T_{\rm eff}=3.6496\times10^{4}\ \mathrm K$ 与
$m_{0}=585.59\ \mathrm{g\,cm^{-2}}$，先在
$Q_{\rm safe}=3.934\times10^{-2}\ \mathrm{s^{-2}}$ 建立收敛 LTE 模型，再只改变 $Q$。
续接采用对数路径

$$
\ln Q(f)=(1-f)\ln Q_{\rm safe}+f\ln Q_{\rm target}.
$$

最后一个可接受检查点为

$$
Q=1.53169\times10^{-7}\ \mathrm{s^{-2}}
=91.296\,Q_{\rm target},
$$

其最大相对改变量为 $1.74\times10^{-4}$，能量残差为
$5.37\times10^{-4}$。下一小步 $Q=1.51875\times10^{-7}\ \mathrm{s^{-2}}$ 已达到 206 次
迭代、最大相对改变量 577，且没有可接受谱；实际目标
$Q_{\rm target}=1.67773\times10^{-9}\ \mathrm{s^{-2}}$ 的直接求解最大相对改变量为
$1.61\times10^{17}$。`[V]`

这证明“当前已测试的静态续接路径没有到达目标”，但不能证明数学上不存在任何其他静态解。
是否需要不同的耗散随深度分配、辐射加速度边界、更多原子过程，或者该柱本来就需要动态
辐射流体处理，仍是开放问题。`[O]`

## 7. 审计图逐面板解释

![Phase 7A 静态环带可行性审计](../outputs/phase7a_static_annulus_audit.png)

**(a) 严格准静态点与 12 个 medoid。** 横轴为
$\log_{10}(T_{\rm eff}/\mathrm K)$，纵轴为
$\log_{10}(Q/\mathrm{s^{-2}})$，颜色表示
$\log_{10}(m_{0}/\mathrm{g\,cm^{-2}})$；星号都是实际 ZO 网格点。图中分离的低温低 $Q$
与高温较高 $Q$ 分支说明代表柱不能只按温度抽样。`[V]`

**(b) 每个代表柱承载的权重。** 蓝、橙、绿分别是 corrected 面积、玻尔兹曼功率和光学
控制带在严格子集内的簇分数。近心点高温柱承载较大 bolometric 权重，而较冷柱承载更多面积
或光学权重；这正是三种权重必须并列抽样的原因。`[A/V]`

**(c) 灰尺度高度与直接 LTE 失败。** 蓝线显示所有代表柱的
$H_{\rm rad}/H_{\rm gas}>7$；红方块显示直接 LTE 的最终最大相对改变量，均远高于红色
$10^{-3}$ 验收线。该面板同时说明问题不是单个异常柱，也不能把灰初值误称为收敛结构。
`[V]`

**(d) 代表柱 03 的重力续接。** 横轴是 $Q/Q_{\rm target}$，纵轴是最终最大相对改变量；
绿色点同时通过结构、能量与谱文件门，红叉为拒绝或失败。可接受分支止于约
$Q/Q_{\rm target}=91.3$，而目标位于竖虚线 1。图上存在收敛的高 $Q$ 模型，故求解器控制已
通过；目标附近没有通过点，故不能生成替代 modified-blackbody 的实际大气谱。`[V/O]`

## 8. 对 modified-blackbody 质疑的当前回答

modified-blackbody 与 Doppler/弱场频移在数学上并不冲突：任意局域共动谱只要以
$I_{\nu,\rm em}$ 提供，观察者传递仍使用 $I_{\nu}/\nu^{3}$ 不变量和已有频移因子 $g$。
真正的问题是它的局域谱形、热化深度和角分布是否代表实际大气，而不是它能否与运动学
“叠加”。`[L/A]`

Phase 7A 原计划用 TLUSTY 谱直接测量这种局域闭合误差；当前由于 0/12 实际代表柱收敛，
比较尚未成立。最严谨的结论不是 modified-blackbody 已经正确，也不是 TLUSTY 已证明它错误，
而是：

> `[V/O]` 现有 modified-blackbody 仍是 optical/UV 条件预言中的工作闭合；本轮静态 H/He
> 环带没有提供可接受的替代谱。低温、极低 $Q$、辐射压占优且沿轨道呼吸的真实大气仍未闭合。

## 9. 阶段决策

- `[V]` 代表柱选择、corrected 面积权重、官方 LTE/NLTE 控制、结构改变量和能量积分均有
  CSV/JSON/图证据；
- `[V]` 12 个实际柱直接 LTE 接受数为 0，灰初值未升级为物理谱；
- `[V]` 代表柱 03 的受控续接停在目标重力的 91.296 倍；
- `[V]` Phase 7B1 更新后的全项目现场测试为 `195 passed`，Markdown 规范检查无待修改文件；
- `[O]` 是否存在其他静态解，以及金属、Compton、辐照或耗散剖面会否改变结果，尚未解决；
- `[O]` blackbody、modified-blackbody 与 atmosphere spectrum 的正式比较被阻塞；
- Phase 7B 不开始，也不进入 Cloudy 或动态 NLTE 实现。

机器可读结果：

- `outputs/phase7a_static_annulus_report.json`；
- `outputs/phase7a_representative_annuli.csv`；
- `outputs/phase7a_rep03_continuation.csv`；
- `outputs/phase7a_static_annulus_audit.png`。

代码入口为 `src/eccentric_tde_observer/phase7a.py`、
`src/eccentric_tde_observer/tlusty.py`、`scripts/bootstrap_tlusty208_hhe.py` 和
`scripts/phase7a_static_annulus_audit.py`；测试为 `tests/test_phase7a.py` 与
`tests/test_tlusty.py`，并由 `tests/test_tlusty_bootstrap.py` 与
`tests/test_markdown_math.py` 检查构建补丁和文档控制字符。
