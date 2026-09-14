# Phase 7B6d：最坏全深度块的保护收缩通过

上游：[[phase7b6c_guarded_relaxation|Phase 7B6c 整步保护超松弛]]  
协议：[预注册 JSON](../outputs/phase7b6d_preregistered_full_depth_contraction.json)  
结果：[汇总 JSON](../outputs/phase7b6d_full_depth_contraction_summary.json)

## 1. 为什么先测一个块

完整 9632 组、4096 深度的一次全频源映射实测约需 $245\,\mathrm{s}$。7B6d 因此先固定
Phase 1367 中内存成本最大的第 27 块，即核心组 $[3456,3584)$，在完全相同的 4096 深度
和 turning-ray 算子上比较 16 次普通 Jacobi 与 16 次保护超松弛。[A-preregistered]

该块仍只有 128 个核心频率组，频率 halo 固定为局域 boosted-Planck 初态；因此它是完整
深度算子的收缩试验，不是完整全频固定点。[A/O]

## 2. 结果

![Phase 7B6d full-depth contraction](../outputs/phase7b6d_full_depth_contraction.png)

| 路径 | 第 16 次原始残差 | 末态审计残差 | 加速步数 | 总时间 | 峰值 RSS |
|---|---:|---:|---:|---:|---:|
| Jacobi | $8.1217\times10^{-5}$ | $7.1815\times10^{-5}$ | 0 | $106.23\,\mathrm{s}$ | $3.73\,\mathrm{GiB}$ |
| 保护 $\omega\leq1.8$ | $5.6541\times10^{-5}$ | $4.5907\times10^{-5}$ | 15 | $106.34\,\mathrm{s}$ | $3.67\,\mathrm{GiB}$ |

- `[V]` 两条路径的第一次未松弛源映射哈希都精确回到 7B5x 的
  `f6d7a776d176e9188b5403c75181807e93839e7bf1aba7d8dec4d1978b9781ed`；
- `[V]` 保护路径第一次采用 $\omega=1$，随后 15 次都完整接受 $\omega=1.8$；
- `[V]` 第 16 次残差比为 $0.69617$，严格低于预注册的 $0.8$ 门槛；
- `[V]` 两条路径所有中间态都保持正强度，完整末态残差和能量账本均为有限量；
- `[V]` 两条路径成本相同，说明保护判定没有增加额外辐射源映射。

图 (a) 给出真正的全深度原始残差；图 (b) 给出整步保护实际接受的权重；图 (c) 比较
第 16 次残差比与冻结门槛；图 (d) 说明两条路径的时间和内存几乎相同。

## 3. 结论边界

7B6d 证明 $\omega\leq1.8$ 的整步保护在最坏全深度块上稳定且有实际收益，并授权有界的
全频率收缩试验。[V] 但是 $5.65\times10^{-5}$ 仍远高于 $10^{-10}$，不能称为收敛；本阶段
没有授权物质反馈、完整轨道或替换 Phase 4。[O]
