# Phase 7B4n：联合深度--时间周期动态参考

导航：[[eccentric_tde_observer/README|项目总览]] ·
[[eccentric_tde_observer/docs/phase7b4m_front_aware_variable_refinement|Phase 7B4m 报告]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

证据标记：`[V]` 代码验证；`[A]` 工作假设；`[A-control]` 数值控制；
`[A-classification]` 预声明分类门；`[O]` 未解决问题。

## 1. 本阶段回答什么

Phase 7B4m 的空间门只在 64 个轨道相位上检验，Phase 7B4k 的 1024 对 2048 时间门又只用
4 个半柱深度单元。两个分离门不能证明高深度与高时间分辨率同时存在时仍然收敛。
Phase 7B4n 因此独立求解：

1. N=64、512 相位的高深度时间候选；
2. N=62、1024 相位的高时间空间候选；
3. N=64、1024 相位的联合有限参考。

本阶段仍使用局域 $J_{\nu}=B_{\nu}(T)$、H/He 基态 Milne 率和 Rosseland 扩散；没有实现
激发态、多能级 NLTE、非局域频率依赖动态转移、观察者谱、Phase 4 大气替换或 UVOT
仪器层。`[A/V/O]`

## 2. 三色三对角 Jacobian 控制

每个隐式时间步在对数温度 $u_{j}=\ln T_{j}$ 上求能量残差 $R_{j}$。局域热力学、基态率和
opacity 只依赖本层，扩散通量只跨相邻单元面，因此有严格依赖结构

$$
\frac{\partial R_{j}}{\partial u_{k}}=0,
\qquad
|j-k|>1.
$$

把温度列按 $k\bmod3$ 分成三种颜色，同色列没有共享残差行。一次基准函数值加三次同色
扰动即可构造完整三对角有限差分 Jacobian，再交给原有精确 trust-region 求解器。这个
优化没有删除层、改变方程或放宽物理容差。`[A-control/V]`

第一次开发尝试直接把稀疏矩阵交给 SciPy，求解器因此切换到 LSMR，并在控制算例第 8
相位达到函数评估上限。由于没有完整周期完成，该路径未产生正式结果；正式实现改为三色
有限差分并重新从零做 dense 对照。`[V]`

N=64、64 相位独立控制的最大逐场差异为 $4.578\times10^{-9}$，远低于预先固定的
$10^{-6}$ 数值等价门；前沿状态错配为 0。运行时间从 $1449.2\ \mathrm{s}$ 降到
$117.3\ \mathrm{s}$，dense/colored 比为 12.35。`[V]`

![Phase 7B4n colored-Jacobian control](../outputs/phase7b4n_colored_jacobian_control.png)

- `(a)` 比较独立 dense 与三色 N=64、64 相位表面能流，曲线重合；`[V]`
- `(b)` 选取 He III 差异最大的相位 17，前沿剖面仍重合；`[V]`
- `(c)` 展示通量、逐点、柱平均和前沿误差，全部比 $10^{-6}$ 门低两阶以上；`[V]`
- `(d)` 只报告当前机器实测成本，不把加速比当成物理结论。`[A-control/V]`

## 3. 完整周期检查点

正式脚本只在完整轨道周期结束后保存温度和 H/He 布居末态，不保存未闭合的相位片段。若
运行中断，下一次调用从最后一个完整周期末态继续，并保留已用周期数和累计运行时间。
检查点的相位数、深度边界和实际频率网格必须逐位匹配当前请求，否则显式拒绝恢复。`[V]`

三个正式算例都从同一个 16 层父初态守恒延拓到 64 层，再按严格嵌套边界限制到目标网格；
没有从另一正式动态解热启动，也没有事后物理重归一化。`[V]`

## 4. 正式周期解与能量账本

| 深度 × 相位 | 运行时间 | 周期数 | 周期残差 | 周期能量账本残差 | 初态/限制守恒 |
|---:|---:|---:|---:|---:|---:|
| 64 × 512 | $699.3\ \mathrm{s}$ | 2 | $5.337\times10^{-10}$ | $1.975\times10^{-12}$ | 通过 |
| 62 × 1024 | $1140.0\ \mathrm{s}$ | 2 | $4.907\times10^{-10}$ | $4.391\times10^{-12}$ | 通过 |
| 64 × 1024 | $1176.3\ \mathrm{s}$ | 2 | $4.492\times10^{-10}$ | $4.365\times10^{-12}$ | 通过 |

这里的“初态/限制守恒”使用预声明的 $2\times10^{-12}$ 容差，包含质量、H/He 粒子数、
离子级、电荷、总比能、光深和父面通量散度。周期能量账本是独立诊断，其残差远低于
$10^{-3}$ 离散生产门。`[A-classification/V]`

## 5. 联合空间与时间误差

时间比较先把独立 512 相位解按周期线性插值到 1024 相位参考的真实轨道时间坐标；空间
比较要求 N=62 的每条边界都是 N=64 边界的严格子集。温度、Rosseland opacity 和表面
通量采用相对误差，H II 与 He III 采用绝对误差。柱平均以单元质量加权，He III 半电离
前沿另外比较状态与质量分数位置。`[A/V]`

| 指标 | 64×512 对 64×1024 | 62×1024 对 64×1024 | 目标 |
|---|---:|---:|---:|
| 表面通量相对误差 | $5.457\times10^{-4}$ | $2.187\times10^{-6}$ | $10^{-3}$ |
| 最大逐点 $T/\kappa_{\rm R}$ 相对误差 | $1.069\times10^{-4}$ | $3.748\times10^{-4}$ | $10^{-3}$ |
| 最大逐点 H II/He III 绝对误差 | $1.087\times10^{-3}$ | $4.508\times10^{-4}$ | $10^{-3}$ |
| 最大柱平均 $T/\kappa_{\rm R}$ 相对误差 | $9.182\times10^{-5}$ | $6.457\times10^{-5}$ | $10^{-3}$ |
| 最大柱平均 H II/He III 绝对误差 | $1.127\times10^{-4}$ | $6.508\times10^{-5}$ | $10^{-3}$ |
| He III 前沿质量分数误差 | $9.801\times10^{-5}$ | $1.028\times10^{-6}$ | $10^{-3}$ |
| 前沿状态错配相位数 | 0 | 0 | 0 |

空间轴全部通过。时间轴只有最大逐点人口误差失败，比门槛高约 $8.7\%$，因此不能把
64×1024 解直接称为已经时间收敛的生产参考。`[V/O]`

失败项可定位到最表层 He III：轨道相位 $0.98885$、质量分数中心
$7.899\times10^{-4}$，512 与 1024 相位插值值分别为 $0.21157$、$0.21048$。同一审计中
H II 的最大差只有 $6.22\times10^{-8}$。失败位于回到近心点前的快速 He 电离响应区，
不是非有限值或被删除的坏 bin。`[V]`

![Phase 7B4n joint convergence](../outputs/phase7b4n_joint_convergence.png)

- `(a)` 的 512 与 1024 相位表面能流目视重合，但最大范数仍保留 $5.46\times10^{-4}$
  差异；`[V]`
- `(b)` 展示相位 735 的最强 He III 前沿，N=62 与 N=64 高度一致；`[V]`
- `(c)` 是正式准入图：时间轴的逐点人口柱稍高于 $10^{-3}$，其余时间项和全部空间项
  通过；`[A-classification/V]`
- `(d)` 分开显示周期初末状态残差与周期能量账本，不用后者掩盖前者。`[V]`

## 6. 64×1024 有限参考的物理内容

![Phase 7B4n joint dynamic reference map](../outputs/phase7b4n_joint_reference_map.png)

- `(a)` 展示完整周期的二维温度场；表层最低温、近心点附近整体升温，图中没有把深度剖面
  压缩成单一色温。`[V]`
- `(b)` 展示 He III 半电离前沿随轨道相位在质量坐标内移动；它正是时间门最敏感的结构。
  `[V]`
- `(c)` 表明动态出射能流相对瞬时 ZO 加热存在约百分之一以内的周期记忆，而不是逐相位
  强制相等。`[V]`
- `(d)` 中 H II 柱平均量接近 1，He III 柱平均量在约 $0.60$ 到 1 之间周期变化；这仍是
  H/He 基态局域闭合下的结果，不是多级 NLTE 光谱。`[A/V/O]`

## 7. 阶段判断

| 判据 | 结果 |
|---|---|
| dense--colored 数值等价 | 通过 `[A-control/V]` |
| N=62 对 N=64 的 1024 相位空间门 | 通过 `[A-classification/V]` |
| N=64 的 512 对 1024 高深度时间门 | 失败，He III 为 $1.087\times10^{-3}$ `[V/O]` |
| 64×1024 联合有限参考是否完成 | 已完成 `[V]` |
| 联合深度--时间生产门 | 未通过 `[V/O]` |
| 非局域频率依赖动态转移 | 不获准 `[O]` |
| Phase 4 大气替换与 UVOT | 不获准 `[O]` |

下一微阶段是 **Phase 7B4o：N=64、2048 相位联合时间参考**。已有 4 层直接审计说明
1024 对 2048 可以通过，但本阶段证明高深度 He III 前沿更敏感，所以必须在同一 N=64
网格上直接复算。只有 1024 对 2048 的全部高深度指标通过，才授权非局域频率依赖动态
转移。`[V/O]`

后续状态：[[eccentric_tde_observer/docs/phase7b4o_high_depth_time_reference|Phase 7B4o]] 已完成
这项独立复算；最大逐点人口差降为 $2.887\times10^{-4}$，全部时间指标通过，联合有限
深度--时间门因此关闭。这个后续结果不改变 7B4n 当时保留轻微失败的历史判定。`[V]`

## 8. 产物与复现

- `src/eccentric_tde_observer/joint_dynamic_reference.py`：独立时间/空间比较和联合门；
- `src/eccentric_tde_observer/periodic_dynamic_atmosphere.py`：三色 Jacobian 与整周期检查点；
- `scripts/phase7b4n_joint_depth_time_reference.py`：控制、正式算例和总结；
- `outputs/phase7b4n_control_report.json`：dense--colored 控制；
- `outputs/phase7b4n_complete_report.json`：最终判定；
- `outputs/phase7b4n_joint_convergence.csv`：时间与空间误差；
- `outputs/phase7b4n_time_population_error_locations.csv`：H II/He III 最大时间误差位置；
- `outputs/phase7b4n_energy_ledger.csv`：周期守恒账本；
- `outputs/phase7b4n_reference_phase.csv`：64×1024 逐相位积分量；
- `outputs/phase7b4n_reference_profiles.csv`：选定相位的深度剖面；
- `outputs/phase7b4n_colored_jacobian_control.png`：英文数值控制图；
- `outputs/phase7b4n_joint_convergence.png`：英文联合收敛图；
- `outputs/phase7b4n_joint_reference_map.png`：英文动态二维图。

```bash
uv run python scripts/phase7b4n_joint_depth_time_reference.py --stage control
uv run python scripts/phase7b4n_joint_depth_time_reference.py --stage case --case depth64_phase512
uv run python scripts/phase7b4n_joint_depth_time_reference.py --stage case --case depth62_phase1024
uv run python scripts/phase7b4n_joint_depth_time_reference.py --stage case --case depth64_phase1024
uv run python scripts/phase7b4n_joint_depth_time_reference.py --stage summary
```

成功完成的成对 NPZ/JSON 会安全复用；未完成但含合法整周期检查点的算例会恢复。全项目现场
回归为 `321 passed in 52.13s`。`[V]`

本阶段没有使用 `nan_to_num`、任意 `clip`、任意物理 floor、删除失败相位或事后物理
重归一化。`[V]`
