# Phase 7B5e：Lorentz 分量关闭只确认强度支路值得继续审计

> [!summary] 阶段结论
> `[A/V/O]` Phase 7B5e 在同一个 $f=0.25$、2408 组 log-P1 候选与 38496 组
> P0 有限参考上，分别关闭强度、消光和发射率的 Lorentz 变换。完整基线逐位复现
> 7B5d。完整算子和 no intensity Lorentz 的三态联立方程全部通过；no extinction
> Lorentz 与 no emissivity Lorentz 至少有一个状态越过联立残差门，且收紧固定点容差
> 不改变该失败。因此后两者是不可用于因果分类的非可接受控制。唯一可接受的关闭实验
> no intensity Lorentz 把两个移动状态的 H I 率误差分别降到完整值的 $1.424\%$ 和
> $1.331\%$。这只授权一次独立的实验室系到共动系强度平移审计；不证明强度 Lorentz
> 公式错误，不授权算符修正，也不选择生产频率表示。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5d_dynamic_operator_controls|Phase 7B5d 动态控制]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

---

## 1. 三个分量控制的精确定义

完整混合系碰撞步依次使用三个 Lorentz 不变量：[V]

$$
\frac{I_{\nu}}{\nu^{3}},
\qquad
\chi_{\nu}\nu,
\qquad
\frac{\eta_{\nu}}{\nu^{2}}.
$$

7B5e 为 P1 候选和 P0 参考同时实施下列 `[A-control]`：

| 控制 | 只替换的分量 | 仍保留 |
|---|---|---|
| full Lorentz operator | 无 | 三个真实 Lorentz 变换、真实碰撞和 ALE |
| no intensity Lorentz | $I_{\nu}$ 搬移、角度像差和匹配外边界黑体取单位变换 | 消光、发射率 Lorentz 与实际 ALE |
| no extinction Lorentz | 只令 $\chi_{\nu}$ 的共动到实验室 Doppler 因子为 1 | 强度、发射率 Lorentz 与实际 ALE |
| no emissivity Lorentz | 只令 $\eta_{\nu}$ 的共动到实验室 Doppler 因子为 1 | 强度、消光 Lorentz 与实际 ALE |

这些部分关闭方程不是协变物理模型。它们只能检验数值误差对某个分量的敏感性，不能输出为
生产谱或被解释成真实物质运动。[A/O]

## 2. 为什么控制必须先通过自己的方程门

对每个控制 $c$，比较量仍是同一受控方程的两种离散：[V]

$$
\epsilon_{c}
=
\frac{
\Gamma_{\mathrm{H\,I},c}^{\rm P1}
-
\Gamma_{\mathrm{H\,I},c}^{\rm P0}
}
{\Gamma_{\mathrm{H\,I},c}^{\rm P0}}.
$$

但误差变小只有在下列门同时通过时才有解释力：

1. P1 与 P0 原生 H I 率复算误差小于 $2\times10^{-8}$；
2. 候选与参考联立残差小于 $2\times10^{-8}$；
3. 候选与参考能量账本小于 $2\times10^{-8}$；
4. 强度非负。

若控制方程本身没有闭合，不能把它的候选--参考差用于“哪一项是原因”的分类。[A/V]

## 3. 哪些控制通过

完整基线相对 7B5d 的最大差为 0。三态结果为：[V]

| 控制 | 最冷表层 | 最大速度 | 最大宽度变化 | 三态可接受 |
|---|---:|---:|---:|---|
| full Lorentz | 通过 | 通过 | 通过 | 是 |
| no intensity Lorentz | 通过 | 通过 | 通过 | 是 |
| no extinction Lorentz | 失败，残差 $1.13\times10^{-7}$ | 通过 | 失败，残差 $1.64\times10^{-3}$ | 否 |
| no emissivity Lorentz | 失败，残差 $7.91\times10^{-8}$ | 失败，残差 $2.39\times10^{-3}$ | 失败，残差 $3.68\times10^{-2}$ | 否 |

对最大宽度失败点把固定点容差从 $10^{-10}$ 收紧到 $10^{-12}$ 和 $10^{-14}$ 后，
no extinction 的联立残差仍为 $1.64\times10^{-3}$，no emissivity 仍为
$3.68\times10^{-2}$。失败不是迭代过早停止，而是部分关闭后 P1 可实现性限制与受控离散
方程不相容所留下的残差。[V/O]

P0 参考在所有关闭实验中仍通过，且所有失败点都保留；没有裁剪、删除、floor 或事后
重归一化。[V]

## 4. Lorentz 分量响应图

![Phase 7B5e Lorentz component controls](../outputs/phase7b5e_lorentz_component_controls.png)

**左上。** 完整三态绝对误差为 $1.6127\times10^{-5}$、$5.6819\times10^{-4}$ 和
$2.1329\times10^{-3}$。no intensity Lorentz 分别降到 $5.1501\times10^{-8}$、
$8.0896\times10^{-6}$ 和 $2.8387\times10^{-5}$。[V]

**右上。** 完整移动状态是负偏差；关闭强度变换后残余可改变符号。这表明 H I 率差对
实验室系到共动系强度搬移敏感，但符号变化本身不等于公式错误。[V/O]

**左下。** no intensity Lorentz 相对完整误差的比例依次为 $0.00319$、$0.01424$ 和
$0.01331$，两个移动状态都超过预声明的 $50\%$ 降低门。消光与发射率柱虽然也显示数值
响应，但斜线表示它们没有通过自己的联立方程门，不能参与因果分类。[A/V]

**右下。** 黑色虚线是 $2\times10^{-8}$ 残差门。完整与 no intensity 全部低于该门；
no extinction 和 no emissivity 的失败随宽度应力显著放大。图中保留这些柱，避免只展示
“好看”的控制结果。[V]

## 5. H I 阈值区域响应

![Phase 7B5e threshold-region response](../outputs/phase7b5e_threshold_region_response.png)

**左图。** 最冷表层在完整与 no intensity 中都由 H I shoulder 主导，分别占绝对被积
函数差的 $85\%$ 和 $88\%$。总误差虽然降低约 300 倍，残余误差的位置仍在阈值肩部。
[V]

**中图。** 最大速度完整算子的 H I Doppler 带占 $62\%$；no intensity 后该带占
$22\%$，shoulder 增至 $77\%$，同时总误差降到完整值的 $1.42\%$。[V]

**右图。** 最大宽度状态完整算子的 H I Doppler 带占 $91\%$；no intensity 后降至
$44\%$，shoulder 为 $56\%$，总误差降到完整值的 $1.33\%$。消光和发射率行仅记录失败
控制的频段形态，不能作为物理归因。[V/O]

## 6. 正式判定

| 判据 | 结果 |
|---|---|
| 完整基线复现 7B5d | 通过 |
| full / no intensity 三态方程门 | 通过 |
| no extinction 三态方程门 | 失败 |
| no emissivity 三态方程门 | 失败 |
| 有效的强度关闭控制稳定降低移动误差 | 是，降低约 $98.6\%$--$98.7\%$ |
| 唯一 Lorentz 分量因果定位 | **否**，另两个控制不可接受 |
| 单次强度平移审计 | **授权** |
| 针对算符的修正 | **未授权** |
| 生产频率表示 | **未选择** |

下一步只把同一个实验室输入谱做一次 $I_{\nu}/\nu^{3}$ 守恒搬移，比较 log-P1 与高分辨率
P0 的共动 H I 率和能量矩。若一次平移已经越过 $10^{-3}$，瓶颈在强度表示/搬移；若一次
平移通过，则瓶颈来自它在隐式碰撞步中的累积反馈。[A/O]

角度、辐射子网格、整轨道、物质反馈、Phase 4 替换和 UVOT 继续关闭。[A/V/O]

## 7. 代码、产物与证据边界

新增或扩展：[V]

- `src/eccentric_tde_observer/mixed_frame_ale.py`：默认开启、仅诊断可关闭的 P0 三分量接口；
- `src/eccentric_tde_observer/mixed_frame_ale_log_p1.py`：相同语义的 log-P1 接口；
- `scripts/phase7b4v_mixed_frame_ale_gate.py` 与
  `scripts/phase7b5a_log_frequency_p1_gate.py`：匹配外边界和一步控制；
- `scripts/phase7b5e_lorentz_component_controls.py`：三态分量控制、率定位和英文图；
- `tests/test_phase7b5e_lorentz_component_controls.py`：失败点保留、授权边界和禁用修复检查。

运行：

```bash
PYTHONPATH=scripts uv run python scripts/phase7b5e_lorentz_component_controls.py --force
uv run pytest -q
```

主要产物为 `outputs/phase7b5e_summary.json`、两个 CSV 和上面两张经过目视检查的英文图。
[V]

本阶段完成后的现场完整回归为 `468 passed in 59.68s`。[V]

- `[A]`：部分 Lorentz 关闭实验、$50\%$ 稳定降低分类门；
- `[V]`：匹配候选/参考、原生率、残差、账本、正性、容差敏感性和阈值带响应；
- `[O]`：一次强度搬移误差与隐式反馈误差的分离；
- `[L]`：本阶段没有新增文献物理。

Phase 7B5e 是受控数值诊断，不是新的连续谱闭合、观察者谱或 NLTE 线谱。[A/V/O]
