# Phase 7B7g：全局拼接辐射态的 H/He 原子率

上游：[[phase7b7fr_resource_closure|Phase 7B7f-r 源项资源闭合]]

## 为什么需要重算原子率

Phase 7B7e 的各块诊断使用“新核心 + 旧 halo”，只能代表 block-Jacobi
映射的中间态。Phase 7B7g 让 76 个频率块都读取同一个全局拼接辐射态，
再独立提取 H I、He I 和 He II 的光致电离与 Milne 逆过程率。`[V]`

对每个基态离子，光致电离率的结构为

$$
\Gamma_{i}
=
4\pi
\int_{\nu_{{\rm th},i}}^{\infty}
\frac{\sigma_{i}(\nu)J_{\nu}}{h\nu}
\,\mathrm{d}\nu.
$$

这里的 $J_{\nu}$ 来自完整 Lorentz 角度--频率变换，不是局域 Planck 函数或
modified-blackbody。`[V]`

## 结果

| 诊断 | 结果 | 门 |
|---|---:|---:|
| 物理频率组唯一覆盖 | $9632/9632$ | 必须逐组唯一 |
| 原子率加热对 7B7f 体积 $L_{1}$ | $5.33\times10^{-14}$ | $<10^{-10}$ |
| 父网格最大镜像残差 | $1.18\times10^{-11}$ | $<10^{-8}$ |
| 单进程最大 RSS | $4064.16\,\mathrm{MiB}$ | $<6144\,\mathrm{MiB}$ |
| 总墙钟 | $161.58\,\mathrm{s}$ | $<600\,\mathrm{s}$ |

![Phase 7B7g assembled H/He atomic rates](../outputs/phase7b7g_assembled_atomic_rates.png)

图 (a) 和 (b) 分别显示 H I、He I、He II 的光致电离率和总辐射复合系数；
图 (c) 显示独立原子率加热与 7B7f 正式源项重合；图 (d) 给出加热复现、
镜像对称和资源门。`[V]`

## 边界

本阶段只读取已有辐射态，没有做物质或辐射更新。它只授权
[[phase7b7h_second_picard_direction|Phase 7B7h]] 构造同一物理时间层的第二条物质
Picard 方向，不代表已有动态 NLTE 输出谱。`[O]`
