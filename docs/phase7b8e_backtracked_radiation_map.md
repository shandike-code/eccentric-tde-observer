# Phase 7B8e：回溯提案的全频辐射验证映射

上游：[[phase7b8d_feedback_line_search|Phase 7B8d 反馈感知回溯]]

## 数值结果

回溽物质态继续使用正式的 9632 频群、32 方向和 4096 辐射深度，没有降低分辨率。76 个
频率块仍按一块一短进程、最多两个并发运行。`[V]`

| 量 | 结果 |
|---|---:|
| 一次映射原始辐射残差 | $2.70667\times10^{-3}$ |
| 最小映射强度 | $0$ |
| 最大进程 RSS | $4023.55\,\mathrm{MiB}$ |
| 总墙钟 | $393.01\,\mathrm{s}$ |
| 检查点 SHA-256 | `68082b4c1dbe33dc9fcaa0f71e69064904f7f85aee8839c9e5de1f016ab14508` |

![Phase 7B8e backtracked radiation map](../outputs/phase7b8e_backtracked_radiation_map.png)

图 (a) 显示全部频率块都低于方向信赖门，高能尾精确零原样保留。图 (b) 显示全部短进程
低于 $6\,\mathrm{GiB}$ 门，颜色给出每块耗时。图 (c) 记录全局残差、最低强度、内存和
墙钟，并明确正式物质反馈仍待下一步装配。`[V]`

## 决策

所有权、非负性、辐射方向和资源门通过，只授权 Phase 7B8f 的正式源项与三重真残差门；
本阶段本身不是固定点。`[A-preregistered/V/O]`

