# Phase 7B7a-r：反馈系数的一块一进程资源闭合

上游：[[phase7b7a_feedback_coefficients|Phase 7B7a 科学量通过、资源失败]]

## 受控修改

只重算首次超过 6 GiB 的原 owner 2/3 共 38 个频率块。每个新进程只处理一个块后退出，
任何时刻最多并发两个进程；输运方程、频率所有权、角度、深度、原子率和求积阶数均不变。
每个 owner 再按原升序聚合，并要求所有数组逐位等于首次部分和。`[A-preregistered]`

## 结果

| 量 | 结果 |
|---|---:|
| 隔离重算块 | $38$ |
| 两个 owner 的最大数组差 | $0,0$ |
| 最大单进程 RSS | $4705.52\,\mathrm{MiB}$ |
| 总墙钟 | $254.76\,\mathrm{s}$ |

![Phase 7B7a-r resource closure](../outputs/phase7b7ar_resource_closure.png)

图 (a) 明示两个重新聚合的部分和逐位相同；图 (b) 显示全部单块进程低于 6144 MiB；图 (c)
显示较宽中频块耗时更长，但总墙钟仍低于 900 s。由此 7B7a 的科学系数和可重复资源门同时
关闭，只授权一次冻结辐射物质响应。`[V/O]`

