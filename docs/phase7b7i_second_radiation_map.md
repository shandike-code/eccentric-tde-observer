# Phase 7B7i：第二物质迭代态上的全频辐射方向

上游：[[phase7b7h_second_picard_direction|Phase 7B7h 第二物质方向]]

## 方法

输入辐射场是 Phase 7B7e 已全局拼接的 $9632\times32\times4096$ 强度态，
碰撞系数更新为 Phase 7B7h 的第二物质迭代态。ALE 储存项仍指向原物理旧时间层，
时间步、密度和几何全部不变。`[A-preregistered/V]`

76 个频率块每块只做一次 block-Jacobi 源映射，最多两个短寿命进程并发。
本阶段只写入新核心频带，不在“新核心 + 旧 halo”上提取正式原子率。`[V]`

## 结果

| 诊断 | 结果 | 门 |
|---|---:|---:|
| 唯一拥有的频率组 | $9632$ | $9632$ |
| 一次映射全局辐射残差 | $6.72827\times10^{-4}$ | $<0.1$ |
| 最小输出强度 | $0$ | $\geq0$ |
| 最大进程 RSS | $4052.09\,\mathrm{MiB}$ | $<6144\,\mathrm{MiB}$ |
| 总墙钟 | $395.24\,\mathrm{s}$ | $<900\,\mathrm{s}$ |

![Phase 7B7i second full-frequency radiation direction](../outputs/phase7b7i_second_radiation_map.png)

图 (a) 显示每个频率块变化占辐射信赖门的比例；symlog 原样保留高能端的精确
零变化，没有 floor 或删点。图 (b) 给出每块内存与耗时；图 (c) 明确标注正式源项和
原子率尚未在此步评估。`[V]`

## 结论边界

辐射方向本身通过了正性、覆盖和资源门，但不能从块内旧 halo 诊断物理闭合。
只授权[[phase7b7j_second_assembled_feedback|Phase 7B7j]] 在全局拼接新态上重算源项、原子率和
固定点残差。`[O]`
