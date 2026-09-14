# Phase 7B7a：收敛共动辐射场的物质反馈系数

上游：[[phase7b6r_worker_recycling|Phase 7B6r 固定物质全柱门]]

## 本阶段回答什么

7B7a 不更新温度或布居，只从第 30 次收敛强度执行一次正式映射，提取物质共动系的
$J_{\nu}$、H I/He I/He II 光致电离率、自然与受激复合率以及净辐射加热。
`[A-preregistered]`

每个频率块只拥有其 128 个全局物理频率组；Doppler 守护组只服务 Lorentz 重映射，不进入
第二次原子率积分。因此 76 块恰好覆盖 9632 组，每组所有权都等于 1。`[V]`

原子率给出的物质净加热为

$$
Q_{\rm rate}
=
4\pi\int
\left(\kappa_{\nu}J_{\nu}-\eta_{\nu}\right)
\,\mathrm{d}\nu.
$$

独立的四力路径先合并唯一实验室系频带，再逆变换：

$$
G^{0}_{\rm com}
=
\gamma\left(G^{0}_{\rm lab}-\beta cG^{1}_{\rm lab}\right),
\qquad
Q_{4}=-G^{0}_{\rm com}.
$$

## 科学结果与首次资源失败

| 量 | 结果 |
|---|---:|
| 频率块/唯一物理组 | $76/9632$ |
| $Q_{\rm rate}$ 对 $Q_{4}$ 体积加权 $L_{1}$ | $9.423999\times10^{-4}$ |
| 柱积分加热相对差 | $7.804101\times10^{-4}$ |
| 最大镜面对称残差 | $1.198921\times10^{-11}$ |
| 四个原工作进程峰值 RSS | $5296,6187,6359,5822\,\mathrm{MiB}$ |

频率所有权、非负率、四力一致性和镜面对称门全部通过；但两个长寿命进程越过
$6144\,\mathrm{MiB}$，所以 7B7a 严格总门失败，不能直接授权物质更新。`[V]`

![Phase 7B7a feedback coefficients](../outputs/phase7b7a_feedback_coefficients.png)

图 (a) 显示 Milne 率积分和逆四力给出的共动加热几乎重合；图 (b) 把小差异放大后仍低于
冻结的柱积分门；图 (c) 给出三条基态光致电离率的全柱结构；图 (d) 显示所有镜面对称残差
远低于 $10^{-3}$。标题保留 6359 MiB，提醒首次科学通过并不等于资源通过。`[V]`

资源闭合见[[phase7b7ar_resource_closure|Phase 7B7a-r]]。

