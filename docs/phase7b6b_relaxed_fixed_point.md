# Phase 7B6b：无保护全局超松弛严格失败

上游：[[phase7b6a_full_frequency_source_iteration|Phase 7B6a 全频单次源迭代]]  
协议：[预注册 JSON](../outputs/phase7b6b_preregistered_relaxed_fixed_point.json)  
结果：[汇总 JSON](../outputs/phase7b6b_relaxed_fixed_point_summary.json)

## 1. 问题与边界

Phase 7B6a 表明完整柱的一次源映射可运行，但一次约需 $245\,\mathrm{s}$，不能未经检查就
直接执行几十次。7B6b 先在已有 9632 组严格单单元参考上测试纯数值超松弛：[A]

$$
I^{(n+1)}
=
I^{(n)}+\omega\left[G\!\left(I^{(n)}\right)-I^{(n)}\right].
$$

这里 $G$ 是未改变的正式源映射，$\omega$ 不是新物理参数。收敛判据始终使用未松弛残差：

$$
R_{n}
=
\frac{\max\left|G\!\left(I^{(n)}\right)-I^{(n)}\right|}
{\max\left(\max\left|G\!\left(I^{(n)}\right)\right|,
\max\left|I^{(n)}\right|\right)}.
$$

候选权重 $\omega=1.0,1.2,1.5,1.8$ 在运行前冻结。任何非有限或负强度试探态都使该权重
整体失败；没有裁剪、floor、删点或事后重归一化。[A-preregistered]

## 2. 结果

![Phase 7B6b relaxed fixed point](../outputs/phase7b6b_relaxed_fixed_point.png)

- `[V]` $\omega=1.0$ 用 35 次迭代收敛，末态哈希
  `5b982f0cfda44b68bdabd371e008c586f5951aca4794fde4a7be81fbdbac383a` 与保留参考逐位相同；
- `[V]` 收敛时原始残差为 $5.2433\times10^{-11}$，再做一次完整诊断得到
  $2.4354\times10^{-11}$；
- `[V]` $\omega=1.2,1.5,1.8$ 都在第一次外推时产生负强度，最小值分别为
  $-5.85\times10^{-3}$、$-1.55\times10^{-2}$ 和 $-2.51\times10^{-2}$；
- `[V]` 因此两个相邻加速权重改善的预注册门未通过，7B6b 总门严格失败。

图 (a) 给出真正的原始定点残差；三种加速候选只留下第一次失败点。图 (b) 的一次迭代柱
不是“快速收敛”，而是立即被拒绝。图 (c) 明确只有基线同时保持非负并收敛。图 (d) 只对
有足够历史的基线报告末段收缩因子，其中位数约为 $0.465$。

## 3. 结论与下一步

简单全局超松弛不能进入正式完整柱求解。[V] 失败来自初始迭代尚未处于允许安全外推的
正强度区域，而不是内存不足。[V] 下一步只能另立预注册门，逐次完整拒绝不满足非负性的
外推步，并退回未松弛的 $G(I)$；这种做法不修改任何单元值，也不删除失败点。[A/O]

本阶段没有授权完整柱固定点、物质反馈、完整轨道或替换 Phase 4。[O]
