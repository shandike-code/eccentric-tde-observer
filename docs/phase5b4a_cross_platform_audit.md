# Phase 5B4a：macOS/Windows 跨平台复算审计

## 1. 结论先行

Phase 5B3c 与 Phase 5B4 已在 Windows 远程目录
`D:\eccentric_tde_observer_remote` 中独立复算，并与 macOS 本地产物逐表比较。[V]

- Phase 5B3c 主解量的最大相对差为 $2.07\times10^{-11}$；
- Phase 5B4 候选时标表的最大相对差为 $6.12\times10^{-13}$；
- 两个平台的全部布尔科学门槛一致；
- 两个平台都得到“方程自洽候选存在”，也都保持 published benchmark、常偏心 atlas
  模形兼容和现有 atlas 时间映射三道门关闭。[V/O]

因此，跨平台复算排除了“Phase 5B3c/B4 结论只是单机或单一操作系统数值偶然”的解释；
它没有恢复 ZO 论文 Fig. 6/7 的 published 分支，也不能把方程自洽候选改称发表
benchmark。[V/O]

## 2. 复算来源与传输核对

Windows 节点使用 Python 3.11.9。远程计算完成后，仅把 Phase 5B3c/B4 的 CSV 与 JSON
审计产物复制回本地专用目录：

- `outputs/remote_windows_phase5b3c/`；
- `outputs/remote_windows_phase5b4/`。

通过 SSH 对远程 10 份源产物逐一计算 SHA-256，远端哈希与本地复制件全部一致。[V]
完整的本地/远程复制件文件清单、远端传输完整性门及各自 SHA-256 已写入
`outputs/phase5b4a_cross_platform_audit.json`。

本阶段没有传输或修改 Phase 7 辐射检查点，没有改动 ZO 正式源模型，也没有继续枚举任意
符号或边界变体。[V]

## 3. Phase 5B3c 对照

| 对照量 | macOS/Windows 差异 | 判定 |
|---|---:|---|
| 主解量最大相对差 | $2.07\times10^{-11}$ | 一致 |
| 矢量边界切线量最大相对差 | $1.95\times10^{-10}$ | 一致 |
| 边界残差最大绝对差 | $2.95\times10^{-15}$ | 一致 |
| 印刷方程来源账本 | 逐行相同 | 一致 |

两个平台均通过 equation-variant 内部门，也均得到：附录印刷符号不能解释 published
分支、published 矢量内端切线不能共同满足声明的三维自由边界、正式 ZO 源未被修改、
$\Phi\mapsto t$ 未获授权。[V/O]

这里对接近零的边界残差报告绝对差，而不是相对差。两个约 $10^{-17}$ 的数即使只相差机器
舍入量，相对差也可能接近一；用它判断跨平台失败会误读尺度。[A-audit]

## 4. Phase 5B4 对照

| 对照量 | macOS | Windows | 跨平台差异或门槛 |
|---|---:|---:|---:|
| 候选时标表 | — | — | 最大相对差 $6.12\times10^{-13}$ |
| 高偏心表主解 | — | — | 最大相对差 $6.12\times10^{-13}$ |
| 射击解频率/外缘偏心率 | — | — | 最大相对差 $1.56\times10^{-8}$ |
| 最终偏导留出误差 | $2.77\times10^{-4}$ | $2.59\times10^{-4}$ | 均小于原门 $10^{-3}$ |
| 三档偏导分辨率门 | fail, fail, pass | fail, fail, pass | 完全一致 |
| 表解外边界残差最大绝对差 | — | — | $5.15\times10^{-17}$ |

射击法是独立常微分方程路径，对收敛容差和平台库实现比配点候选量更敏感，因此其
跨平台差异大于最终候选表；但两边各自的射击/配点误差仍远低于 Phase 5B4 原声明的
$10^{-5}$ 科学门。[V]

有限差分偏导留出误差也不要求逐位相同。关键结果是两个平台都保留中间两档失败、最终
$41\times81$ 表通过的同一分辨率模式，并且最终最大留出误差均低于 $10^{-3}$。[V]

## 5. 审计门与科学门必须分开

JSON 中名为 `reproduction_gates` 的阈值仅用于判断两个平台的结果是否在相应数值尺度上
相符，标记为 [A-audit]。这些阈值不替代 Phase 5B3c/B4 原有科学门，也不重新定义 ZO
benchmark。

跨平台一致后仍保留以下边界：[O]

1. 方程自洽高偏心候选已被独立复现；
2. ZO published Fig. 6/7 benchmark 仍未恢复；
3. 候选 $e(a)$ 与现有常偏心 atlas 的模形不兼容；
4. 现有 Phase 4/5/6 atlas 的 $\Phi$ 仍不能正式换算成时间；
5. 没有根据 published 曲线事后拟合新符号或新边界。

## 6. 机器可读产物与复现

机器可读报告：`outputs/phase5b4a_cross_platform_audit.json`。其中包含：

- 10 个 Windows 源产物的远端/复制件 SHA-256 完整性对照；
- 20 个平台输入条目的路径、平台标签和 SHA-256；
- Phase 5B3c/B4 数值差异；
- 两个平台的门槛向量；
- 跨平台审计门及科学边界。

复现命令：

    python scripts/phase5b4a_cross_platform_audit.py
    python -m pytest -q tests/test_phase5b4a_cross_platform_audit.py

阶段关系见
[[eccentric_tde_observer/docs/phase5b3c_printed_equation_path_audit|Phase 5B3c]]、
[[eccentric_tde_observer/docs/phase5b4_strict_domain_candidate_timescale_gate|Phase 5B4]]。
