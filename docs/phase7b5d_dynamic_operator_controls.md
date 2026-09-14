# Phase 7B5d：H I 阈值误差来自 Lorentz 与真实连续碰撞的交互

> [!summary] 阶段结论
> `[A/V/O]` Phase 7B5d 对同一个 $f=0.25$、2408 组失败候选和 38496 组 P0 有限参考
> 同时实施五个一因子控制。完整基线逐位复现 7B5c；全部 15 对候选/参考控制的联立残差、
> 能量账本、正性和原生 H I 率复算通过。去除 ALE 宽度变化几乎不改变两个移动状态的
> 误差；关闭散射也没有稳定改善。令 $D=1$ 或关闭真实吸收/热发射，都会把最大速度与
> 最大宽度变化状态的误差降低 $99.9\%$ 以上。因为两个控制同时满足预声明的稳定降低规则，
> 不能把误差唯一归因于 Lorentz 或真实连续碰撞中的任一单项；证据指向二者的非线性交互。
> 因此不授权针对单一算子的修正，也不选择生产频率表示。下一步必须分别控制强度、消光和
> 发射率的 Lorentz 搬移。

导航：[[eccentric_tde_observer/README|README]] ·
[[eccentric_tde_observer/docs/phase7b5c_signed_rate_error_localization|Phase 7B5c 率误差定位]] ·
[[eccentric_tde_observer/lecture/项目讲义/项目整体讲义|项目整体讲义]] ·
[[eccentric_tde_observer/lecture/项目讲义/下一步研究路线|下一步研究路线]]

---

## 1. 为什么每个控制都要重算候选和参考

若只关闭 2408 组候选中的某个子算子，却仍比较完整物理的 38496 组参考，那么差值会混入
“物理问题已经改变”的偏差。7B5d 对每个控制 $c$ 都独立计算 `[V]`

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

因此比较的是同一个受控算子在两种频率离散下的误差，而不是把受控谱与完整谱相减。

所有关闭实验都标为 `[A-control]`：它们只定位数值来源，不是物理盘解，也不能输出到
Phase 4 或观察者链。

## 2. 五个一因子控制

| 控制 | 实施方式 | 保留的部分 |
|---|---|---|
| full operator | 不改变正式一步算子 | Lorentz、真实吸收/发射、散射、ALE 全部保留 |
| $D=1$ control | 物质 Lorentz 速度置零 | 实际移动 ALE 网格与全部碰撞源保留 |
| rigid ALE width control | 旧/新单元宽度设为相同 | 实际平均平移速度、Lorentz 与碰撞源保留 |
| no scattering control | 电子散射消光/源置零 | Lorentz 与真实吸收/热发射保留 |
| no true absorption/emission control | 真实吸收与热发射置零 | Lorentz、散射和 ALE 保留 |

刚体 ALE 控制不是把网格完全静止，而是令

$$
z_{k}^{\rm old,ctrl}
=
z_{k}^{\rm new}
-
\bar v_{\rm edge}\Delta t,
$$

使两个界面以同一速度平移。这样保留平均材料速度，只去除
$\Delta z^{\rm new}-\Delta z^{\rm old}$。[A/V]

一因子控制在非线性联立方程中不可相加：两个“关闭后误差小”的控制可能表示交互项，而不是
两个各自独立的误差来源。[A/O]

## 3. 控制本身是否数值有效

完整基线相对 Phase 7B5c 的最大差为 0。全部 15 个控制状态得到：[V]

| 诊断 | 范围或最大值 | 正式门 |
|---|---:|---:|
| 候选联立残差 | $2.78\times10^{-16}$--$7.19\times10^{-11}$ | $2\times10^{-8}$ |
| 候选能量账本 | $7.95\times10^{-18}$--$2.36\times10^{-10}$ | $2\times10^{-8}$ |
| 参考联立残差 | $2.76\times10^{-16}$--$7.20\times10^{-11}$ | $2\times10^{-8}$ |
| 参考能量账本 | $1.65\times10^{-17}$--$1.30\times10^{-10}$ | $2\times10^{-8}$ |
| 候选原生率复算 | 最大 $3.47\times10^{-15}$ | $2\times10^{-8}$ |
| 参考原生率复算 | 最大 $1.27\times10^{-14}$ | $2\times10^{-8}$ |

所有候选与参考强度非负。控制结果的差异不是固定点未收敛、能量不守恒或后处理率积分不一致
造成的。[V]

## 4. 动态算子控制图

![Phase 7B5d dynamic operator controls](../outputs/phase7b5d_dynamic_operator_controls.png)

**左上。** 完整基线的最冷、最大速度和最大宽度变化误差分别为
$1.6127\times10^{-5}$、$5.6819\times10^{-4}$ 和 $2.1329\times10^{-3}$。
$D=1$ 与 no true absorption/emission 把三态误差都降到约 $10^{-7}$；刚体 ALE 与完整
结果重合，no scattering 仍保留 $10^{-5}$--$10^{-3}$ 误差。[V]

**右上。** 完整、刚体 ALE 和 no scattering 主要保持负误差，即 P1 低估 P0 率；
$D=1$ 和 no true absorption/emission 的残余变成约 $10^{-7}$ 且可改变符号。这进一步
说明主负偏差需要同时存在 Lorentz 与真实连续碰撞。[V/O]

**左下。** 相对完整误差的控制比为：

| 控制 | 最冷表层 | 最大速度 | 最大宽度变化 |
|---|---:|---:|---:|
| $D=1$ | $6.223\times10^{-3}$ | $3.016\times10^{-4}$ | $4.293\times10^{-5}$ |
| rigid ALE width | $1.000003$ | $1.00834$ | $0.99780$ |
| no scattering | $1.01920$ | $1.31866$ | $0.74920$ |
| no true absorption/emission | $1.299\times10^{-2}$ | $2.490\times10^{-4}$ | $5.509\times10^{-5}$ |

绿色虚线对应误差至少降低 $50\%$ 的 `[A-classification]` 门。$D=1$ 和 no true
absorption/emission 在两个移动状态都通过，故没有唯一控制；ALE 宽度变化不通过，散射
也没有同时通过。[A/V]

**右下。** 所有候选控制的联立残差远低于黑色门。no scattering 的残差接近浮点精度，
是因为去掉了一个非局域源迭代分支；这不把它变成物理更正确的模型。[V/O]

## 5. H I 阈值带如何响应

![Phase 7B5d threshold-region response](../outputs/phase7b5d_threshold_region_response.png)

每格给出该能段占绝对 H I 被积函数差的比例。[V]

**左图。** 最冷表层在所有控制中仍由 H I shoulder 主导，比例为 $85\%$--$88\%$。
这里本来存在 $98.5\%$ 的符号抵消；关闭主交互项后剩余约 $10^{-7}$ 误差的位置仍不等于
生产误差来源。[V/O]

**中图。** 最大速度完整算子的 Doppler 阈值带占 $62\%$。刚体 ALE 和 no scattering
分别保持约 $62\%$ 和 $66\%$；关闭 Lorentz 或真实吸收/发射后，该带降到 $7\%$ 左右，
H I shoulder 升到 $93\%$，同时总误差已经下降三到四个数量级。[V]

**右图。** 最大宽度变化完整算子的阈值带占 $91\%$。刚体 ALE 保持 $91\%$，no
scattering 保持 $87\%$；$D=1$ 和 no true absorption/emission 分别降到 $4\%$ 和
$2\%$。决定性阈值尖峰只有在 Lorentz 与真实连续碰撞同时存在时才出现。[V/O]

## 6. 能说什么，不能说什么

可以说：[V]

1. ALE 宽度变化不是两个移动状态 H I 率误差的必要条件；
2. 散射也不是稳定主因；
3. Lorentz 速度与真实吸收/热发射都是主误差出现的必要条件；
4. 证据指向二者的交互，而非单独一个全局静态网格问题。

不能说：[O]

1. “Lorentz 变换公式错误”——解析移动平衡和四力控制已经通过；
2. “真实吸收公式错误”——静态微物理与末态压缩控制已经通过；
3. 两个关闭控制的改善可以线性相加；
4. 已经知道是强度、消光还是发射率的哪一次 Lorentz 搬移主导。

下一小阶段应在保持完整真实吸收/发射的同时，分别控制 `[O]`

$$
I_{\nu}/\nu^{3},
\qquad
\eta_{\nu}/\nu^{2},
\qquad
\chi_{\nu}\nu
$$

对应的频率平移与振幅变换。每个控制必须同时重算 P1 候选与 P0 参考，并保留移动平衡、
残差和能量账本。若只有一个搬移分支稳定降低两个移动状态误差，才允许对该分支设计保守
离散修正。[A/O]

## 7. 正式判定

| 判据 | 结果 |
|---|---|
| 完整基线复现 7B5c | 通过 |
| 全部受控候选/参考算子门 | 通过 |
| 刚体 ALE 宽度控制稳定降低误差 | 否 |
| no scattering 稳定降低误差 | 否 |
| $D=1$ 稳定降低误差 | 是 |
| no true absorption/emission 稳定降低误差 | 是 |
| 唯一动态子算子定位 | 失败，有两个必要控制 |
| 针对单一算子的修正授权 | **否** |
| 生产频率表示 | **未选择** |

角度、辐射子网格、整轨道、物质反馈、Phase 4 替换和 UVOT 继续关闭。[A/V/O]

## 8. 代码、产物与证据边界

新增或扩展：[V]

- `scripts/phase7b5d_dynamic_operator_controls.py`：五个匹配候选/参考的一因子控制和英文图；
- `scripts/phase7b4v_mixed_frame_ale_gate.py`：P0 参考的零 Lorentz、刚体 ALE 与碰撞分支
  控制接口；
- `scripts/phase7b5a_log_frequency_p1_gate.py`：同语义的 log-P1 控制接口；
- `tests/test_phase7b5d_dynamic_operator_controls.py`：交互判定、控制算子与授权边界。

运行：

```bash
PYTHONPATH=scripts uv run python scripts/phase7b5d_dynamic_operator_controls.py --force
uv run pytest -q
```

主要产物为 `outputs/phase7b5d_summary.json`、两个 CSV 和上面两张经过目视检查的英文图。
[V]

本阶段完成后的现场完整回归为 `463 passed in 58.27s`。[V]

- `[A]`：一因子关闭实验、移动状态 $50\%$ 误差降低门；
- `[V]`：匹配候选/参考、原生率、残差、账本、控制误差和阈值带响应；
- `[O]`：Lorentz--真实连续碰撞交互中强度/消光/发射率的独立贡献；
- `[L]`：本阶段没有新增文献物理，只拆分既有不变量与 H/He 连续过程。

Phase 7B5d 是非物理关闭实验组成的数值归因阶段，不是新的观察者连续谱或 NLTE 线谱。
[A/V/O]
