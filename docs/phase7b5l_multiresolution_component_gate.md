# Phase 7B5l：守恒局域多分辨率频率组件门

> [!summary] 阶段结论
> `[A/V/O]` 已建立严格 1--2--4 对数嵌套的 P0 频率层级、按真实
> ${\rm d}\nu$ 守恒的延拓/限制、能量与 H/He 光致电离率联合嵌入式指标，以及只允许
> 每个基组保留 1 个叶或完整 4 个 master 子组的预算网格。24 个实际温度--速度--角方向
> boosted-Planck 控制谱上，守恒残差为 $4.48\times10^{-15}$--
> $7.04\times10^{-15}$，8/16 阶指标差为 $1.65\times10^{-14}$。4816 叶预算产生
> 4814 叶和 2 个显式未用自由度。组件门通过，只授权下一步在互相独立的实际动态训练/
> 验证截面上审计；生产频率表示仍未选择。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5k_high_resolution_convergence|Phase 7B5k 高分辨率相邻收敛]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

---

## 1. 这一阶段解决什么，不解决什么

7B5k 已确认 9632/19264 组存在有限高分辨率 P0 参考，但原 4816 组效率门仍失败。7B5l
先建立一个可输运、可守恒、自由度可精确计数的局域多分辨率组件，不直接用高分辨率答案
雕刻生产网格。[V/O]

本阶段只回答：[A/V]

- 粗细频率层能否严格嵌套；
- P0 粗细转换能否守恒频带积分；
- 是否能用同一个无自由带宽指标给基组稳定排序；
- 在 4816 叶上限内能否形成唯一可复现的网格。

本阶段不回答实际动态 H I 率是否通过，也不恢复角度、辐射深度、轨道或物质反馈。[O]

## 2. 严格 1--2--4 层级

基网格沿用 Phase 7B5b 已固定的 $f=0.25$ 率核分区，共 $N_{\rm base}=2408$ 组。每个
基组在 $\ln\nu$ 中等距二分，得到 4816 组 pilot；再二分得到 9632 组 master。全部基组
边界和 H I、He I、He II 阈值在三层逐位相同。[A/V]

![Phase 7B5l frequency hierarchy](../outputs/phase7b5l_frequency_hierarchy.png)

图的横轴是光子能量，纵轴是叶组的 $\Delta\ln\nu$。蓝、橙、绿线分别是基层、pilot 和
master；红线是预算内可变网格。三条灰色竖虚线是 H I、He I、He II 阈值。[V]

红线不是一段人为选择的“漂亮带宽”。它只允许每个基组处于两种状态：保留一个粗叶，或
采用该基组的全部四个 master 子叶。局域跳变来自离散选择，不移动任何物理阈值。[A/V]

## 3. 守恒延拓与限制

设父组 $P$ 含子组 $c$。限制使用真实频率宽度：[V]

$$
J_{\rm P}
=
\frac{
\sum_{c\in P}J_{c}\,\Delta\nu_{c}
}{
\Delta\nu_{\rm P}
}.
$$

延拓只复制父组 P0 常数：[A/V]

$$
J_{c}=J_{\rm P},
\qquad c\in P.
$$

因此两种操作都满足：[V]

$$
\sum_{c\in P}J_{c}\,\Delta\nu_{c}
=
J_{\rm P}\,\Delta\nu_{\rm P}.
$$

没有斜率拟合、floor、裁剪或事后重归一化。复制延拓不会凭空恢复丢失的子组结构；它只是
定义粗细层之间唯一、守恒的 P0 映射。[A/V/O]

## 4. 嵌入式排序指标

控制谱来自三个实际物态的温度和速度，并在已有 8 阶角方向上构造解析 boosted-Planck
谱，共 24 个样本。它们只用于组件控制，不是动态大气输出。[A-control]

对每个基组 $P$ 和样本 $s$，先把 master 谱限制到基组，再守恒延拓回 master。指标取
能量 $L_{1}$ 缺陷与 H I、He I、He II 率缺陷中的最大值：[A]

$$
\eta_{\rm P}
=
\frac{1}{\epsilon}
\max_{s}
\left[
\frac{
\sum_{c\in P}
|J_{c,s}-J_{\rm P,s}|\,\Delta\nu_{c}
}{
\sum_{c}J_{c,s}\,\Delta\nu_{c}
},
\max_{\rm X}
\frac{|\delta\Gamma_{\rm X,\rm P,s}|}{\Gamma_{\rm X,s}}
\right],
$$

其中 $X\in\{{\rm H\,I,He\,I,He\,II}\}$，$\epsilon=10^{-3}$ 沿用既有生产目标。
三种率不加可调权重，而是统一归一化后取最大值；相同指标用稳定索引次序打破并列。[A/V]

![Phase 7B5l embedded indicator](../outputs/phase7b5l_embedded_indicator.png)

灰线是全部基组指标，红点是预算选择的四子组父组，黑虚线是单父组单位目标贡献。所有控制
谱的最大指标为 $0.188$，但这**不代表实际动态总率已经通过**：控制谱是光滑解析输入，
没有 7B5g--7B5k 中的碰撞固定点动态结构。图只证明指标能在完整频带和三个原子阈值间做
确定性排序。[A/V/O]

## 5. 自由度账本

若细化 $N_{\rm ref}$ 个父组，每个父组从 1 个叶变成 4 个叶，则：[V]

$$
N_{\rm leaf}
=
N_{\rm base}+3N_{\rm ref}.
$$

在 $N_{\rm leaf}\le4816$ 下：[V]

$$
N_{\rm ref}
=
\left\lfloor
\frac{4816-2408}{3}
\right\rfloor
=802,
\qquad
N_{\rm leaf}=4814.
$$

剩余 2 个自由度无法组成一个完整四子组块，所以明确记为未用；没有用不对称的半块去追逐
结果。最低已细化指标 $7.0718\times10^{-4}$ 大于最高未细化指标
$7.0174\times10^{-4}$，排序账本闭合。[A/V]

## 6. 守恒和求积控制图

![Phase 7B5l transfer controls](../outputs/phase7b5l_transfer_controls.png)

四个粗细积分残差为 $4.48\times10^{-15}$--$7.04\times10^{-15}$，常数场往返残差为
$0$，8/16 阶嵌入式率指标差为 $1.65\times10^{-14}$。黑虚线是
$2\times10^{-13}$ 转移门；指标求积另使用既有 $2\times10^{-10}$ 门，二者都通过。
[V]

图从零开始显示，因此严格零常数残差没有被替换成任意 floor。[V]

## 7. 判定与下一步

| 判据 | 结果 |
|---|---|
| 2408--4816--9632 严格嵌套 | 通过 |
| H/He 阈值逐层精确保留 | 通过 |
| P0 限制/延拓频带积分 | 通过 |
| 常数场往返 | 精确通过 |
| 8/16 阶指标求积 | 通过 |
| 4816 叶预算账本 | 4814 叶，2 个未用 |
| 多分辨率组件门 | **通过** |
| 实际动态截面审计 | **授权，尚未执行** |
| 生产频率表示 | **未选择** |
| 全轨道、物质反馈、Phase 4 替换、UVOT | **仍关闭** |

下一阶段必须把实际保存的动态单步划分为互不重叠的训练与验证集合：[A/O]

1. 只用训练集合的 master--基组缺陷排序生成一张静态 4814 叶网格；
2. 不再改网格，在独立验证集合上复算 P0 单步 H I 率；
3. 同时报告训练与验证的最坏误差、能量账本、运行时间和返回数组占用；
4. 若验证失败，保留失败，不扩大带宽、不重排到验证点、不修改 4816 预算；
5. 只有验证集合全部通过，才讨论生产选择和进一步角度/辐射子网格门。

## 8. 代码与产物

新增：[V]

- `src/eccentric_tde_observer/multiresolution_frequency.py`；
- `scripts/phase7b5l_multiresolution_component_gate.py`；
- `tests/test_multiresolution_frequency.py`；
- `tests/test_phase7b5l_multiresolution_component_gate.py`；
- `docs/phase7b5l_multiresolution_component_gate.md`。

运行：

```bash
PYTHONPATH=scripts uv run python scripts/phase7b5l_multiresolution_component_gate.py --force
uv run pytest -q
```

主要产物为 `outputs/phase7b5l_summary.json`、两个 CSV 和三张已目视检查的英文图。[V]

本阶段完成后的现场完整回归为 `514 passed in 55.80s`。[V]

- `[L]`：本阶段没有新增文献物理；
- `[V]`：严格层级、阈值、守恒传递、求积、排序和自由度账本；
- `[A]`：固定率核基网格、boosted-Planck 控制谱、联合最大指标与 1/4 子组选择；
- `[O]`：独立实际动态验证、生产网格和全柱成本。
