# cpu_long 超时：保全现场，只补 final 反馈

## 事实与备份

作业 73241 的 stderr 明确记录 `2026-09-19T14:12:01 ... CANCELLED ... DUE TO TIME LIMIT`。不是物理判决，也不能称作整个实验完成。14:29 巡检时队列空，`scontrol` 记录已过期；控制状态停在 feedback。

两张 map 完整提交，墙钟分别 3617.02、3387.58 s，输入算子残差为 6.477113e-4、5.872830e-4。previous 反馈 76/76 块全部提交，累积块批次墙钟 5345.35 s，正式状态门通过；final manifest 为 running、零个已提交块。超时发生在 final 阶段开始后。

完整小工件（含块、输入快照与日志，排除 dat/lock）已双端备份：学校家目录和 Mac `outputs/review-20260919/common-seed-73241-timeout-small.tar.gz`。两端 SHA256 `61779f85852f60efccda2acfc47316727f5c0aff9a0f7b3c3d2de0d21d165a85` 一致。大辐射态保留原位。改代码前另存 `pre-feedback-recovery-2ffe610.bundle`。

previous 的有限反馈已有 11 个非正目标热能单元，最差目标/旧气体热能 -0.89241879；这是 alpha=.0078125 物质在历史基态辐射输入上的结果，不是收敛反馈。最终必须连同 final 和内层残差判断；不能与最小候选不同精度的短程结果混成物理无解证明。

## 恢复设计

新增 `operations/recover_common_seed_feedback.py/.sbatch`，代码 `30217f6`。使用新目录 `outputs/hpc/common-seed-a0078125-feedback-recovery-20260919`，原超时 run、协议、manifest、块、map、状态全部保持不变。

1. 校验原 config/trial/dependencies、两张 map 的反馈输入身份，以及 previous 完成状态、协议/辐射血缘和 76 个块的唯一归属。保存 previous 工件快照并验证 SHA。
2. 明确要求原 final manifest 尚无已提交块，拒绝把其他状态当作本次恢复现场。
3. 新协议从旧协议深复制，只改变输出路径及并发 16→2；sources、所有科学配置、状态门、接受门、授权保持原值。previous 使用原协议下的已完成工件，final 使用新协议；结果保留两份协议 SHA，不伪装成同一协议产生。
4. 仅调用 final 状态反馈求值，再复算两个端点账本与同尺度方程残差；没有任何 map 或物质接受调用。

新资源默认 4 CPU/16G、2 worker、2.5 h、排除本次异常慢的 anode01。换节点与降低并发是操作上的保守恢复选择，尚不能据此证明哪一个因素导致性能差异。保留原每状态 7200 s 资源门：新 final 是一次独立重新评估，其墙钟不冒充包含旧超时作业全部成本；旧作业 3.5 h 消耗保留在本报告。没有自动续交。

Mac 相关 26 项测试通过，包括只改变路径/并发、拒绝不完整或错误血缘的 previous、重复块归属拒绝，以及既有候选身份/内存保护测试。起跑还需学校同组测试和新任务回执确认。

学校同组测试 **26 passed**，已提交恢复作业 **73297**。恢复驱动先做全部输入与原反馈验证，再执行新 final 反馈；实际完成状态以新目录 `control_status.json` 和 `control_result.json` 为准。

## POST-RUN CHECK 与下一判据

原作业达到墙钟上限，final 不完整，无完整反馈对及接受判决；不能把 control_status 仍为 feedback 当作仍有进程。已完成 map 的 RSS 约 3.5 GiB/worker、previous 状态门通过，无科学阈值被放宽。恢复完成后先核全部小工件哈希及两个反馈状态，再比较正热能、相邻率/加热和三个方程范数，决定有界精度延续；当前不能认证方向、接受物质步或宣布模型无解。
