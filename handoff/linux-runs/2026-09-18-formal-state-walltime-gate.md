# 运行记录：形式状态门里的资源限制（900 秒墙钟）

## 现象

2026-09-18 08:5x，α=0.0078125 链（`small-step-a078125-cont48-20260917`）在结算第 1 轮欠账时作业 **72347** 失败：

```
scripts/phase7b9_formal_feedback_pair_adapter.py, line 991, in run_pair
  raise RuntimeError("formal H/He feedback state gate failed")
```

监督器按设计停止并要求人工检查（收据里已记录 `TIMEOUT 72222` 与本次失败的记账），没有盲目重试。

## 根因：不是物理门，是资源门

`scripts/phase7b9_formal_feedback_pair_adapter.py::_formal_state_gates()` 逐条为：

```python
"block_count_exactly": 76,
"owned_frequency_group_count_exactly": 9632,
"minimum_comoving_mean_intensity_at_least": 0.0,
"all_rates_and_arrays_finite": True,
"all_atomic_rates_at_least": 0.0,
"atomic_rate_vs_direct_comoving_heating_volume_l1_below": 1.0e-10,
"atomic_rate_vs_inverse_four_force_volume_l1_below": 1.0e-3,
"atomic_rate_vs_inverse_four_force_global_fraction_below": 1.0e-3,
"maximum_parent_mirror_residual_below": 1.0e-8,
"each_process_peak_rss_strictly_below_mib": 6144.0,
"each_state_wall_time_strictly_below_s": 900.0,
```

最后一条是**资源门**。当节点被其他用户压满时（当时 `CPUAlloc=122/128`、`CPULoad=108.75`），单个反馈状态的计算墙钟超过 900 秒，于是 `previous_manifest`/`final_manifest` 的 `status != "complete"`，`run_pair` 抛错。

对照证据：同一夜里 ext16 的反馈状态只用 270–290 秒（远低于 900），a15625 早期的探针轮次也全部通过；而这条链的 map 墙钟已被拥塞拖到 550/2306/496/**3131** 秒。也就是说：**物理上没有任何门被冒犯，失败完全来自共享节点的瞬时拥塞**。

## 处理

1. 记账失败作业（`--retry-failed-job 72347`）后重启该链；重试作业 **72348** 已提交并运行。
2. 重试时节点负载已回落到 `CPUAlloc=62/128`、`CPULoad=35.99`，900 秒门大概率能过。反馈状态的分块清单本身是可恢复的，重试会从已完成的块继续。
3. 该轮的两个端点 R = 1.5212e-3（map 3）与 1.2807e-3（map 4），远高于阶段 B 门槛 2.5e-4，因此这一轮即便结算成功也只是"暂态点"，不参与判词；它的价值仅在于补全 α→0 一侧的趋势。

## 对后续的约束（已写入操作纪律）

在共享节点上运行形式反馈时，`each_state_wall_time_strictly_below_s = 900` 是一条硬约束：若节点拥塞使反馈状态超过 900 秒，作业会（正确地）失败而不是产出低质量反馈。遇到这种情况的标准动作是"记账 + 等负载回落 + 重试"，**不修改这条门**——它是防止把拥塞期算出的状态当作合格反馈的保护。
