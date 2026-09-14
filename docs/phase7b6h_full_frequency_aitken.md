# Phase 7B6h：四次全频率向量 Aitken 通过

上游：[[phase7b6g_vector_aitken|Phase 7B6g 全深度 Aitken 门]]  
协议：[预注册 JSON](../outputs/phase7b6h_preregistered_full_frequency_aitken.json)  
结果：[汇总 JSON](../outputs/phase7b6h_full_frequency_aitken_summary.json)

## 1. 检查点续算

7B6h 从 7B6f 的第 4 次完整强度检查点继续。第 5 次先用保护 $\omega=1.8$ 重建上一残差；
第 6--8 次在全部 9632 组、32 方向和 4096 深度单元上累加 Aitken 内积，并对一个全局
统一权重做整态非负审计。[A-preregistered]

## 2. 结果

![Phase 7B6h full-frequency Aitken](../outputs/phase7b6h_full_frequency_aitken.png)

| 全局映射次数 | 方法 | 接受权重 | 原始残差 | 墙钟时间 | 最大进程 RSS |
|---:|---|---:|---:|---:|---:|
| 5 | 保护回退 | 1.8 | $1.79153\times10^{-3}$ | $328.97\,\mathrm{s}$ | $4.08\,\mathrm{GiB}$ |
| 6 | 向量 Aitken | 1.15335 | $1.39371\times10^{-3}$ | $389.43\,\mathrm{s}$ | $4.06\,\mathrm{GiB}$ |
| 7 | 向量 Aitken | 1.16107 | $5.41450\times10^{-4}$ | $372.29\,\mathrm{s}$ | $5.63\,\mathrm{GiB}$ |
| 8 | 向量 Aitken | 5.87095 | $4.43027\times10^{-4}$ | $366.25\,\mathrm{s}$ | $5.53\,\mathrm{GiB}$ |

- `[V]` 四次迭代都连续、唯一覆盖 76 块和全部 9632 组；
- `[V]` 三次动态权重都由全局内积直接给出，没有权重裁剪；
- `[V]` 全局强度始终非负，进程峰值严格低于 $6\,\mathrm{GiB}$；
- `[V]` 第 8 次/第 5 次残差为 $0.24729$，通过预注册的 $0.8$ 门槛；
- `[V]` 最终强度和残差分别保存在
  `outputs/checkpoints/phase7b6h_full_frequency_iteration8.dat` 与
  `outputs/checkpoints/phase7b6h_full_frequency_residual8.dat`，二者均为 $9.40625\,\mathrm{GiB}$；
- `[V]` 强度 SHA256 为
  `2eaff5a5a56998643427e043e6675c86ab8e5d92652020b4ded9ccb004d32bb1`，残差 SHA256 为
  `946d8baf884aea909090abf8f6b5010f0eace80875f7eaa8d45a0dfe548d2aa7`。

图 (a) 给出全频残差；图 (b) 给出全局动态权重；图 (c) 包含源映射、内积、两遍整态审计
和写入的墙钟成本；图 (d) 给出每轮两个进程中的较大 RSS。

## 3. 下一授权与边界

7B6h 授权从第 8 次强度--残差双检查点继续正式 Aitken 固定点求解。[V] 当前残差
$4.43\times10^{-4}$ 仍远高于 $10^{-10}$，所以物质反馈、完整轨道和 Phase 4 替换仍未授权。
[O] 长续算必须每轮原子更新清单并可恢复，最终还要另做完整块残差与能量账本审计。[A/O]
