# Phase 7B6f：四次全频率保护收缩通过

上游：[[phase7b6d_full_depth_contraction|Phase 7B6d 保护收缩通过]]、
[[phase7b6e_extended_relaxation|Phase 7B6e 扩展权重失败]]  
协议：[预注册 JSON](../outputs/phase7b6f_preregistered_full_frequency_contraction.json)  
结果：[汇总 JSON](../outputs/phase7b6f_full_frequency_contraction_summary.json)

## 1. 正式全频率状态

7B6f 在 Phase 1367 的冻结物质态上保留全部 9632 个频率组、32 个方向和 4096 个辐射
深度单元。单个 float64 强度状态为 $10\,099\,884\,032$ 字节，即 $9.40625\,\mathrm{GiB}$。
两份状态通过磁盘 memmap 交替保存，两个进程各负责 38 个互不重叠块。[A-preregistered]

每轮的全局原始残差定义为

$$
R_{n}
=
\frac{\max_{f,\mu,z}\left|G(I_{n})-I_{n}\right|}
{\max\!\left(
\max_{f,\mu,z}\left|G(I_{n})\right|,
\max_{f,\mu,z}\left|I_{n}\right|
\right)}.
$$

这与 7B6a 报告的“76 个块各自相对变化的最大值”不是同一个归一化；7B6f 的第一次全场
哈希精确复现 7B6a，因此 $0.02540$ 与早先的 $0.28290$ 不代表两个源映射不一致。[V]

## 2. 结果

![Phase 7B6f full-frequency contraction](../outputs/phase7b6f_full_frequency_contraction.png)

| 全频映射次数 | 接受权重 | 全局原始残差 | 墙钟时间 | 最大进程 RSS |
|---:|---:|---:|---:|---:|
| 1 | 1.0 | $2.53988\times10^{-2}$ | $269.45\,\mathrm{s}$ | $2.88\,\mathrm{GiB}$ |
| 2 | 1.8 | $5.01175\times10^{-3}$ | $334.99\,\mathrm{s}$ | $4.00\,\mathrm{GiB}$ |
| 3 | 1.8 | $3.27712\times10^{-3}$ | $344.34\,\mathrm{s}$ | $4.24\,\mathrm{GiB}$ |
| 4 | 1.8 | $2.40024\times10^{-3}$ | $333.17\,\mathrm{s}$ | $4.28\,\mathrm{GiB}$ |

- `[V]` 第一次完整状态哈希为
  `7afefba5b82393bb05dd147ae66e3a771f18a4b8d54694430389e8b3dbe64d6e`，与 7B6a 精确一致；
- `[V]` 四轮残差严格递减，末轮/首轮为 $0.09450$，通过预注册的 $0.95$ 门槛；
- `[V]` 每轮 76 块连续、唯一覆盖全部 9632 组，所有接受态非负；
- `[V]` 每进程峰值低于 $6\,\mathrm{GiB}$，每轮墙钟低于 $900\,\mathrm{s}$；
- `[V]` 最终检查点保存在
  `outputs/checkpoints/phase7b6f_full_frequency_iteration4.dat`，SHA256 为
  `ff530568eefd0e9fd3eedb55c294ee75b9cffafe0dcb3792327148b25bfc396c`；另一临时状态已删除。

图 (a) 是全局残差；图 (b) 是全局统一接受的权重；图 (c) 给出含 halo 读取、保护检查与
整文件变换的实际每轮成本；图 (d) 给出两个工作进程中的较大 RSS。

## 3. 结论边界

7B6f 证明完整全频率算子能够从检查点继续稳定收缩，并授权固定点续算。[V] 但当前
$R_{4}=2.40\times10^{-3}$，仍远高于 $10^{-10}$；它不是收敛态，不能开始物质反馈，也不能
替换 Phase 4 连续谱。[O] 在直接续跑数十轮前，应先验证是否有比固定 $\omega=1.8$ 更有效且
保持同一固定点的残差加速方法。[A/O]
