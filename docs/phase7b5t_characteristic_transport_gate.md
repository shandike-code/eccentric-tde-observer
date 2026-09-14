# Phase 7B5t：特征分区角求积与精确单元特征输运门

> [!summary] 阶段结论
> `[A-preregistered/V/O]` 特征分区角求积把 32/48 方向误差降到
> $1.73\times10^{-5}$，精确单元特征积分把 16/32 与 32/64 深度误差降到
> $1.65\times10^{-4}$ 和 $4.39\times10^{-5}$。32 方向×16 子单元联合候选相对
> 48×32 参考的最大误差为 $1.74\times10^{-4}$，所有解析、守恒、非负性、科学量和
> 资源门均通过，因此正式接受该单单元生产离散。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5t_preregistered_characteristic_transport_protocol|7B5t 预注册]] ·
[[eccentric_tde_observer/docs/phase7b5s_refined_joint_convergence|Phase 7B5s]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

## 1. 问题来源得到分离

线性源吸收板层上，旧迎风在 16/32/64 单元的最大误差依次为
$1.924\times10^{-2}$、$9.622\times10^{-3}$、$4.811\times10^{-3}$，观测阶为
$1.0000$。新特征积分的对应误差为 $5.484\times10^{-3}$、
$1.424\times10^{-3}$、$3.597\times10^{-4}$，观测阶为 $1.9450$ 和 $1.9856$。
这直接验证 7B5s 的慢深度收敛来自一阶空间通量，而不是固定点失败或频率预算不足。`[V]`

常源后向 Euler 板层的最大绝对误差为 0；线性移动网格的全局联立残差为
$3.47\times10^{-16}$，能量账本残差为 0。所有解析控制强度均严格为正，没有使用裁剪、
floor 或事后重归一化。`[V]`

## 2. 角度分界

在冻结压力单元上，全区间 Gauss--Legendre 的 32/48 方向最大差为
$1.221\times10^{-3}$。把求积在 ALE 特征分界两侧分别构造后，旧迎风和新特征积分的
32/48 最大差分别降到 $1.708\times10^{-5}$ 和 $1.728\times10^{-5}$。`[V]`

分界由

$$
\mu_{\rm split}
=
\frac{w_{\rm left}+w_{\rm right}}{2c}
=-2.5219605\times10^{-3}
$$

唯一确定，与冻结物质速度一致，不是拟合参数。所有求积节点都与 ALE 特征反转位置保持
正距离。`[A/V]`

## 3. 实际压力单元结果

| 比较 | 最大误差 | 最敏感量 | 判定 |
|---|---:|---|---|
| 分区角求积、旧迎风 32/48 | $1.708\times10^{-5}$ | 共动谱 L1 | 通过 |
| 分区角求积、特征积分 32/48 | $1.728\times10^{-5}$ | 共动谱 L1 | 通过 |
| 旧迎风 32/64 子单元 | $7.659\times10^{-3}$ | H I 率 | 失败对照 |
| 特征积分 16/32 子单元 | $1.650\times10^{-4}$ | H I 率 | 通过 |
| 特征积分 32/64 子单元 | $4.388\times10^{-5}$ | H I 率 | 通过 |
| 联合 32×16 对 48×32 | $1.738\times10^{-4}$ | H I 率 | 通过 |

旧迎风即使换成正确的角分界，深度误差仍为 $0.766\%$；所以角求积改进不能伪装成空间
收敛。新特征积分在相同物理输入上把该误差降低约两个数量级，并在连续两组深度比较中
通过。`[V]`

## 4. 图怎么看

![Phase 7B5t characteristic transport gate](../outputs/phase7b5t_characteristic_transport_gate.png)

**左上图。** 蓝线每加倍深度只约减半，确认旧迎风是一阶；橙线约按四倍下降，确认特征
积分在该线性源控制上接近二阶。

**右上图。** 蓝柱是 7B5s 的全区间角求积，多个量略高于 $10^{-3}$；橙柱和绿柱把同一
32/48 方向比较降到约 $10^{-5}$。改进来自把入射边界的不光滑点放在两个求积区间之间。

**左下图。** 蓝柱保留旧迎风 32/64 的真实失败；橙柱与绿柱分别是新特征积分 16/32 和
32/64，八个连续量全部低于黑色 $10^{-3}$ 门。

**右下图。** 正式候选 `SC-a32_d16` 含 $4{,}931{,}584$ 个活跃未知量，耗时
$24.63\,\mathrm{s}$、峰值 $807.39\,\mathrm{MiB}$。最细 32×64 参考峰值为
$2409.30\,\mathrm{MiB}$，仍低于预注册的 $6144\,\mathrm{MiB}$。`[V]`

## 5. 正式接受与仍关闭的范围

正式输出为 `phase7b5t_gate_passed=true`。接受的单单元配置是：

- 9632 个物理频率组；
- 特征分区 Gauss--Legendre 角求积；
- 32 个角方向；
- 精确单元常源特征积分；
- 每个物质父单元 16 个辐射子单元。

该判定关闭的是暴露压力单元的数值输运门，不等于完整动态大气已经完成。全柱仍需检验
多个物质单元上的特征方向、内存、周期运行和温度--布居反馈；Phase 4 替换与 UVOT 仍然
关闭。`[A/V/O]`

## 6. 文件与复现

核心文件：

- `src/eccentric_tde_observer/mixed_frame_ale.py`；
- `src/eccentric_tde_observer/radiative_transfer_1d.py`；
- `scripts/phase7b5t_preregister_characteristic_transport_protocol.py`；
- `scripts/phase7b5t_characteristic_transport_gate.py`；
- `outputs/phase7b5t_characteristic_transport_summary.json`；
- `outputs/phase7b5t_characteristic_transport_runs.csv`；
- `outputs/phase7b5t_characteristic_transport_errors.csv`；
- `outputs/phase7b5t_analytic_spatial_convergence.csv`；
- `outputs/phase7b5t_characteristic_transport_gate.png`。

复现命令：

```bash
PYTHONPATH=scripts uv run python scripts/phase7b5t_preregister_characteristic_transport_protocol.py
PYTHONPATH=scripts uv run python scripts/phase7b5t_characteristic_transport_gate.py --force
```

本阶段专项回归为 `36 passed in 1.32s`；现场完整回归为
`658 passed in 60.41s`。`[V]`
