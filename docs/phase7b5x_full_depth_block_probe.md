# Phase 7B5x：正式整深度最坏单块资源实测

预注册：[[phase7b5x_preregistered_full_depth_block_probe|Phase 7B5x 预注册]]  
上游：[[phase7b5w_translation_invariant_remap_gate|Phase 7B5w 平移不变搬移门]]

## 1. 正式结论

`phase7b5x_gate_passed=true`，但 `full_column_fixed_point_authorized=false`。

- `[V]` 正式最坏速度相位为 1367；选中的第 27 块覆盖 128 个核心组、263 个碰撞 halo
  组和 397 个外层 halo 组，深度为 4096，包含两个 turning directions；
- `[V]` 父物质单元系数复制对直接子单元复算的三项相对误差均为 0；
- `[V]` 最坏块实测峰值 RSS 为 2863.14 MiB，低于 6144 MiB 门；已识别活跃数组初估为
  1.782 GiB，差额来自 Python/Numpy 临时量和返回诊断；
- `[V]` 微物理构造、辐射场准备和一次源映射分别耗时 0.167 s、0.930 s 和 9.659 s，
  总计 10.828 s；
- `[V]` 输出强度最小值为 $4.84228\times10^{-7}$，全部记录诊断有限，正式频率边界未变。

## 2. 这说明时间花在哪里

实际 H/He 连续系数构造只占约 $1.5\%$，辐射场准备约占 $8.6\%$，一次 Lorentz--ALE
映射约占 $89.2\%$。所以当前限制已经从“单体数组会超内存”转成“对 76 个频率块重复
执行频率--角度--深度搬移与输运的时间成本”。[V/A-inference]

把该最坏块总时间机械乘 76 得到 822.9 s，把算子时间机械乘 76 得到 734.1 s；两者只是
单次全频源迭代的保守成本代理，不是实测。更不能再乘一个假定迭代数后声称得到完整柱
运行时间。[A-computational/O]

一次映射的固定点变化为 $1.68163\times10^{-2}$，未收敛；联立残差
$6.82174\times10^{-4}$ 和能量账本残差 $3.07426\times10^{-3}$ 只按预注册记录。
原因是返回诊断使用更新强度重新构造散射源，而本阶段只执行一次 block-Jacobi 映射。它们
不是完整柱失败，也不能作为科学连续谱。[A/V/O]

## 3. 图像逐图解释

![Phase 7B5x full-depth block probe](../outputs/phase7b5x_full_depth_block_probe.png)

- **(a) Worst full-depth block memory**：蓝柱是静态数组账本，橙柱是隔离进程实测峰值，
  灰柱是 6 GiB 门。实测明显低于门，但也表明只看静态数组会低估约 1 GiB 临时量。
- **(b) Measured cost by component**：微物理与输入场构造很短，主要时间集中在一次源映射。
- **(c) Selected block geometry**：Doppler 查询使 128 个核心组实际需要 263 个碰撞组和
  397 个外层组；halo 不能用几个宽守护组替代。
- **(d) Pre-registered gates**：资源、运行时间、有限性和非负性全部通过。

## 4. 下一步边界

下一阶段应先剖析 9.659 s 算子内部的 Lorentz 搬移、散射矩和空间输运占比，并只优化
不改变加法顺序或物理离散的重复计算。优化候选必须重新对 7B5w 的逐位等价性以及 7B5x
最坏块复验。[A/O]

尚未授权完整柱固定点、全轨道、温度/布居反馈、Phase 4 替换或 UVOT；本阶段没有生成
动态连续谱。[O]

机读结果：`outputs/phase7b5x_full_depth_block_probe_summary.json`；隔离进程结果：
`outputs/phase7b5x_full_depth_block_worker.json`。
