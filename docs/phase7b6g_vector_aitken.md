# Phase 7B6g：全深度向量 Aitken 门通过

上游：[[phase7b6f_full_frequency_contraction|Phase 7B6f 四次全频收缩]]  
协议：[预注册 JSON](../outputs/phase7b6g_preregistered_vector_aitken.json)  
结果：[汇总 JSON](../outputs/phase7b6g_vector_aitken_summary.json)

## 1. 算法

固定 $\omega=1.8$ 在完整频率块上稳定，但末段收缩仍慢。7B6g 使用残差向量

$$
r_{n}=G(I_{n})-I_{n}
$$

和预注册的向量 Aitken 权重：[A]

$$
\omega_{n}
=
-\omega_{n-1}
\frac{\left\langle r_{n-1},r_{n}-r_{n-1}\right\rangle}
{\left\|r_{n}-r_{n-1}\right\|_{2}^2}.
$$

内积是最坏全深度块所有频率、方向和深度单元上的普通 Euclidean 内积。动态权重没有被
截断；只有权重为正有限数且整个试探态有限、非负时才接受。否则完整退回
$1.8,1.5,1.2,1.0$ 的已验证序列。[A-preregistered]

## 2. 结果

![Phase 7B6g vector Aitken](../outputs/phase7b6g_vector_aitken.png)

- `[V]` 第一次映射哈希精确回到 7B5x/7B6d；
- `[V]` 第一次采用普通 $\omega=1$，其后 15 次全部接受公式直接给出的 Aitken 权重；
- `[V]` 接受权重在 $1.03$ 到 $6.95$ 之间变化，没有权重裁剪；
- `[V]` 第 16 次原始残差为 $1.1378\times10^{-5}$，仅为固定 $\omega=1.8$ 同成本结果的
  $0.20124$，通过预注册的 $0.5$ 门槛；
- `[V]` 末态完整审计残差为 $9.0267\times10^{-6}$，所有强度保持正值；
- `[V]` 总时间为 $115.52\,\mathrm{s}$，峰值 RSS 为 $5.03\,\mathrm{GiB}$，低于资源门。

残差并非逐轮单调：例如第 11--13 次动态权重较大时残差暂时回升。门槛比较的是冻结的相同
16 次成本和最终原始残差，不能把中间回升删除。[V] 图 (a) 保留了这些回升；图 (b) 给出
未经截断的动态权重；图 (c) 区分 Aitken 与回退步；图 (d) 比较固定成本末态残差。

## 3. 边界

7B6g 只验证一个最坏全深度频率块，并授权从 7B6f 检查点开始的有界全频率 Aitken 试验。
[V] 它尚未证明完整柱达到 $10^{-10}$，也没有授权物质反馈、完整轨道或 Phase 4 替换。[O]
