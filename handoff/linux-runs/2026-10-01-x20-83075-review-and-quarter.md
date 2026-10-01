# 83075精确符号审计与明确1/4候选

83075于22:37:57–22:41:00完成，COMPLETED/0:0，程序177.598885秒，峰值604639232字节，stderr空。小包83075-subnormal-review.tar.gz为47218字节，SHA256 `833b67902a2b6b3f06f1dd5bcb3877c5e45b472609cad18be07df9b1bf799bd6`。Mac按d258271核源码/源声明，以独立整数通分核全/半组合符号、rounded hex和局部上界，首次E2E通过；未下载或重算大场。

| 分片 | 类型 | 存储负点数 | 不同源四元组数 |
|---|---|---:|---:|
| 9440 | input | 8234 | 3 |
| 9440 | predicted_output | 8378 | 3 |
| 9440 | half_input | 2520 | 1 |
| 9440 | half_predicted_output | 3482 | 1 |
| 9472 | input | 177186 | 8 |
| 9472 | predicted_output | 184548 | 9 |
| 9472 | half_input | 80830 | 3 |
| 9472 | half_predicted_output | 75392 | 3 |

full两场共378346个存储负点，精确full全部负；half两场162224个存储负点，精确half全部负。full与half坐标存在重叠，不把两组合并说独立点数。最紧已检查局部原full方向上界为0.26355809157293997，未发现0上界。不能推论未检查零点或其它片精确非负，也不排除源本身离散/舍入误差，更不是连续物理解负。

因此在完成审计后重新声明单个候选：统一沿原方向1/4步，c=[0,-1.8,0.9485574831263044]。它低于已审局部上界，但尚不保证完整场。默认4CPU16GiB/1h只读八个已有场，重新全部301片和原11门，不写候选、0map/feedback/material。通过后还须独立审计和32核真实full/half映射。原83063full/half拒绝保留，不clip、不改变物理dt/能量/r20。

新驱动operations/x20_83063_quarter_prediction.py，协议handoff/protocols/x20-83063-quarter-prediction-v1.md；Mac17测试通过0.96s，包括独立整数上界、覆盖/错误门拒绝、原全场候选核。完整新E2E待batch，不能提前说1/4安全。备份pre-83075-review-20261001.bundle。
