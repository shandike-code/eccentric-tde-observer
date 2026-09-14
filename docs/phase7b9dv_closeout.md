# Phase 7B9dv：固定物质辐射尾段的干净边界收尾

上游：[[eccentric_tde_observer/docs/phase7b9do_iteration20_reproduction_audit|Phase 7B9do 异常复现审计]]、
[[eccentric_tde_observer/docs/phase7b9dt_two_state_slow_mode_locator|Phase 7B9dt 慢模定位]]。

下游判据：[[eccentric_tde_observer/docs/phase7_post_convergence_branch_contract|Phase 7 收敛后分支决策合同]]。

## 1. 收尾决定与文件状态

[A-user-stop] 用户在 7B9du 第 8 次追加 Picard map 完整结束后，决定不再为
$10^{-4}$ 原算子残差门继续追踪慢尾，而是按当前证据收尾。

[V] 收尾脚本只读取 7B9dp summary、7B9dt summary、7B9du protocol/manifest/summary 和
post-convergence branch contract。它没有读取或修改两个大检查点，没有改写协议与 manifest，
也没有启动新辐射计算。

7B9du manifest 的状态字段仍为 running，但 active_iteration 为 null。这里的 running 是原执行器
保留的“可以继续恢复”状态，不表示后台仍有任务运行。停止点具有以下完整证据：

- 7B9du 共保留 $9$ 条记录：种子 $0$ 与追加 map $1$--$8$；
- 最后一条 iteration $8$ 包含完整 $76$ 个自然频率块；
- frequency ownership、物理解和 progression gates 全部通过；
- convergence gate 明确失败；
- 没有 active partial iteration。

## 2. 合并历史的方法

7B9du 的第 $0$ 条是 7B9dp 第 $40$ 条的冻结副本。合并时只保留一次，得到连续的
$49$ 个唯一状态，combined index 为 $0$--$48$。未删除任何失败点，因为这两个历史中的所有
保留态都通过 progression；仅对完全相同的阶段连接种子去重。

定义原算子残差为 $R_{n}$，相邻收缩比为

$$
q_{n}=\frac{R_{n}}{R_{n-1}}.
$$

合并序列从

$$
R_{0}=8.2262136410\times10^{-4}
$$

下降到

$$
R_{48}=2.1041349752\times10^{-4}.
$$

总降幅为 $74.4216\%$，所有保留步单调不增；但最终残差仍为目标
$10^{-4}$ 的 $2.10413$ 倍，因此不能写成“严格收敛”。最终
$q_{48}=0.9919815$，说明慢尾每张完整 map 只再降低约 $0.8\%$。

## 3. 收尾图

![Phase 7B9dv clean-boundary closeout](../outputs/phase7b9dv_closeout.png)

上图全部标注为英文。

- 上面板合并 7B9dp 与 7B9du 的原算子残差。灰色竖虚线是两个阶段的连接位置；蓝线持续下降，
  但在红色 $10^{-4}$ 目标线上方停止。
- 中面板显示 $q_{n}$。前段约为 $0.92$--$0.94$，随后进入接近 $0.99$ 的慢模区。它证明计算仍
  沿合格方向进展，同时也客观说明继续纯 Picard 的边际收益很低。
- 下面板显示 boundary spectrum $L_{1}$ 与 boundary bolometric fraction。最终分别为
  $4.40098\times10^{-6}$ 和 $2.83780\times10^{-6}$，远低于 $10^{-3}$ 边界门；当前未通过项
  是内部原算子残差，而不是表面边界稳定性。

[V] 独立 7B9dt 诊断精确复现了 7B9dp 端点残差，并把分子控制位置定位在 frequency group
$3011$、约 $9.09679\ {\mathrm{eV}}$。该定位只说明慢模在哪里，不证明收敛，也不授权根据该组
做删除、裁剪或局部重归一化。

## 4. 已取得的成果

- [V] 在 $9632$ 个物理频率组、$32$ 个角方向和 $4096$ 个辐射深度单元上，固定物质辐射序列
  保持物理、完整 ownership，并持续通过 progression。
- [V] 合并的 $49$ 状态历史单调降低原算子残差，没有依赖 nan_to_num、任意 clip、floor、
  删除失败点或事后重归一化。
- [V] 两项边界量已稳定通过门槛，7B9dt 又独立复现了慢尾端点。
- [V] 停止发生在完整 map 之后；两个获准复用的大检查点仍可恢复，没有写入第三个全状态。

## 5. 必须保留的弊端与科学边界

当前结果仍然只是：

- 一个代表 annulus；
- 一个轨道相位；
- 固定物质状态上的辐射尾段；
- ground-state H/He continuum 闭合。

当前没有：

- 严格的 $10^{-4}$ 原算子收敛；
- 基于该端点的正式 H/He feedback pair；
- 被接受的耦合物质步或完整动态 NLTE 解；
- 覆盖全径向、全轨道相位的 angle-resolved atmosphere table；
- Phase 4 atmosphere replacement；
- Swift/UVOT 仪器层和观测采样；
- 真实 bound-bound 线形成、线光深或 NLTE 激发态布居。

因此 [V/O] post-convergence branch contract 必须保持 not_ready，不能从当前单柱慢尾提前选择
UVOT、有限大气表或周期动态 NLTE 路线。更不能把 Phase 6 的条件性运动学线核重新命名为真实
$H\alpha$ 预言。

## 6. 可复现入口

运行：

    PYTHONPATH=$PWD:$PWD/scripts .venv/bin/python scripts/phase7b9dv_closeout.py

验证：

    PYTHONPATH=$PWD:$PWD/scripts .venv/bin/python -m pytest -q tests/test_phase7b9dv_closeout.py

机器报告为 outputs/phase7b9dv_closeout.json，图为 outputs/phase7b9dv_closeout.png。
