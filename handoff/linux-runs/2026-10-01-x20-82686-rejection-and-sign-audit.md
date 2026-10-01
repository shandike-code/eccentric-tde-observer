# 82686 拒绝结果与后续符号审计

82686 于 2026-10-01 10:19:35–10:27:22 CST 正常完成，Slurm COMPLETED/0:0。程序耗时456.378秒，峰值RSS 934211584字节，stderr为空，0新map/反馈/物质步。

7文件包105683字节，SHA256 `c3400f900e427de3f7d9c742f0de5bb81caad0621705425341add7d7dc10612c`。Mac 使用原审计入口完成真实工件端到端复核：来源、代码、301分片、固定系数及小目标证书一致。证据见 `handoff/evidence/20261001-x20-historical-heating-prediction-82686-review.json`。

正式判决为 `prediction_rejected_requires_review`，唯一已求值门为 `full_field_nonnegative=false`；其余门未求值。9440分片的input/predicted-output最小值均为−5e−324，9472分片均为−1e−323；两个half的存储最小值均为0。不能把未求值的门描述为通过，也不能根据极小量级豁免非负条件。

下一任务按 `handoff/protocols/x20-subnormal-audit-v1.md` 检查这些负点的精确符号。4CPU16GiB1小时，0新物理迭代；不直接启动32CPU被拒候选。20项定向测试已在Mac通过，含半步精确负值舍入为零、精确抵消、重复计数、预算拒绝和非有限输入拒绝。实际学校结果仍待取得。

备份：Mac `outputs/review-20260925/pre-82686-review-20261001.bundle`；同步前学校保存当前提交bundle。原场与判决均保留。没有得到新的自洽大气或整盘强度。

## 82740 已独立审结

11:05:45启动，程序191.322925秒，RSS581074944字节，COMPLETED/0:0，stderr空。小包45791字节，SHA256 `5026f0a0ddf4f8ee1d3a78bffa215bb364d5e95ab44780112cc1769bf40af5ee`。独立整数证书审计入口首次真实E2E通过，逐项核代码、源声明、7文件和全部8组源四元组；本地没有重读学校大场。计数与证据见 `handoff/evidence/20261001-x20-subnormal-82740-review.json`。

157782个原存储负点的精确full均负，half均正；这只证明给定存储源的代数性质，不是原连续物理解结论。原方案保持拒绝。沿原方向全局减半建立一次新预测，协议 `x20-historical-half-prediction-v1.md`，完整301片保留原11门，0map/反馈/物质；通过仍须独立审计和另行真实映射验证。25项定向测试Mac通过。
