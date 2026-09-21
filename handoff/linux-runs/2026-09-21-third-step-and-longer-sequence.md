# 第三步验收与第 4–6 步有界连续批次

## 已完成的第三步

74795 在 anode17 使用 32 CPU、128 GiB、16 worker，于 2026-09-21 18:03:04–19:29:39 CST 运行，实测 1:26:35，调度终态 `COMPLETED / 0:0`。第二步同态确认用 6 map / 3 pair；第三步用控制 2 map / 1 pair 与 full 8 map / 2 pair，总计 16 map / 6 pair。half 未启动。

Mac 审阅 `operations/review_numbered_outer_step.py`：3135 个文件哈希/大小一致；正式协议、试探态、新分母、旧物理时间层、两个端点及各 76 块反馈所有权一致；用存储残差与单元质量重算范数一致。原响应本次未在 Mac 重求，后续 allocation 的源重放负责这一项。

| 指标 | 第三步基态 | 第三步接受端点 | 比值 |
|---|---:|---:|---:|
| L2 | 14.964594827177153 | 14.721189792895425 | 0.9837346057749801 |
| 质量加权 | 0.570058277341267 | 0.5563709119835132 | 0.9759895331726587 |
| 最差单元 | 3.4369149496023157 | 3.415325968663742 | 0.9937185000923366 |

原 16 门全过，新控制态 previous/final 与候选 previous/final 四组合三范数全部小于 1。原子/直接/正式加热指标分别为 0.000245310682589676、0.0002453106825858316、0.0002453104914613203，门为 0.001；噪声/信号 0.04924637623494988，门为 0.1。两端点都无失败物质单元，最小剩余气体热能分别为 8.543927618497172e12 与 8.533267314253543e12 erg/g。

760 个原 map 块报告有限且强度非负；1216 份过程收据返回码与独立内存门全过。native 峰值 3501.734375 MiB，独立 `/proc` 峰值 4039580 KiB，均低于原 6 GiB 门。审阅图已目视检查：八张 map 残差下降；第二轮通过没有抹掉第一轮 14/16、内层与噪声门失败的历史。

第三个有限物质步被接受；这不是代表柱收敛，更不是整盘大气或最终强度。最差单元本步仅改善约 0.63%，没有依据外推最终完成时间。

最终第三步小包：

- 学校：`outputs/hpc/confirm2-then-step3-20260921/next-step/archives/accepted-review-1789990109973973905.tar.gz`
- 140803330 bytes，SHA256 `4f62018cdee55ac1eecdb9d1fd2290a9b95bda6bab702aad1d81ce3d8734b398`。
- Mac：`outputs/review-20260921/74795-step3-accepted.tar.gz` 与 `74795-step3-accepted-received/`。
- Git 证据：`handoff/evidence/20260921-74795-step3-accepted.json`、同名 PNG。
- 终态与顶层状态：`outputs/review-20260921/74795-terminal.json`、`74795-final-status.json`。

## 扩大单次任务量的决定

用户要求减少提前跑完后等待安排的空档。新增三个顺序依赖的外层步，使用同一 allocation 自动衔接；不是同时把不同未确认基态的候选并行运行。保留当前幅度和所有物理门，以这三个步实测残差收益和同态漂移，再决定是否更改数值策略；不授权无限重复小步。

新代码 `operations/numbered_confirmation_step.py` 是已运行成功组合驱动的编号化副本，保留其源重放、候选生成、协议重定基态及全部校验。变化是从实际源正式协议读取已接受步编号与其原分母来源，并在新声明中固定。旧文件不改。

`operations/bounded_outer_sequence.py` 调用该模块，固定从已审阅第三步开始，依次：

1. `step4/confirmation` 重放第三步，做固定第三步物质态的 control、confirm2、confirm4，共最多 6 map / 3 pair。两次确认原门及 fresh control 四组合三范数全通过才进入 `step4/next-step`。
2. 第四步先控制 2 map / 1 pair，再 full 最多 8 map / 2 pair，必要时 half 最多 8 map / 2 pair。候选一经接受即停止该候选分支；接受与 fresh control 收缩同时满足才考虑续接。
3. 同样流程用于 `step5` 和 `step6`。每一步都重新冻结经确认的基态及实际残差方向，不复用过期方向或分母。
4. 第六步通过后，在 `final-confirmation` 再做 6 map / 3 pair 同态精度确认；整批终态只称 `complete_requires_review`，`coupled_column_accepted` 永远为 false。

每个组合周期最多 24 map / 8 pair，三周期加最后确认的硬上限 **78 map / 27 pair，最多三个新增接受物质步**。若每步仍走 full 八图接受，实际约 **54 map / 21 pair**。按最近 1:26:35 的周期与约 38 分钟确认，约 5 小时是规划估算；它取决于控制稳定性、I/O 与接受路径，12 小时是作业上限。不能用这个估算承诺最终大气完成。

## 不可越过的边界

- full 幅度 1/256，half 幅度 1/512；原 codec/trust 与全部接受门不变。
- 非线性迭代不推进物理时间：旧时间层、phase 1367、dt 889.419892762322 s、密度和能量定义沿原来源继承校验。
- 每步 source raw material response 实际重算并与保存残差逐位比较，重算派生门；大态 seed hash 只在 allocation 内。
- 新 trial 必须先写后初始化；完整 encoded/base/direction/residual/alpha 与 native T/H/He/density/phase/dt 都核验。
- `accepted-stepN.json` 固定每步来源及摘要、协议、状态、fresh control SHA。每一阶段继续原小工件归档，历史 dat 全保留。
- 当前自动源重放仅支持 full、8 张已结算 map、2 个已结算反馈组。如果 full 提前四图被接受或 half 被接受，保留正式接受并停在 `accepted_shape_requires_review`，不将其误称失败，也不擅自套入八图假设。
- 同态确认失败、基态不稳定、候选预算耗尽或 fresh control 不收缩均止步，不能越过到下一外层。程序/资源故障优先，禁止自动重提 Slurm。
- 总预算含活动 map 和 pending pair；恢复不重置。原 pending 反馈/账本先于新图。USR1/TERM 同时保护块边界与阶段间边界，整个序列单锁。
- 32 CPU、128 GiB、16 worker；原 native 与独立 `/proc` 6 GiB 双门、hugepage=0、标准库 relay 不变。
- 根声明预留全部 78 个完整状态大小的保守可用空间；不为连跑删除旧检查点。

## 检验与备份

修改前 Git bundle：`outputs/review-20260921/pre-outer-sequence.bundle`；定时任务原配置 `automation-before-outer-sequence.toml`。

Mac：114 passed / 4 Linux 专用 skipped。测试覆盖新序列跨三步衔接、末次确认、任意周期科学停止、程序故障、阶段间信号、78/27 边界含 active/pending、半步/早期接受停审、恢复预算不可变；编号化副本继承组合驱动测试并新增真实协议编号/哈希/物理时间/fresh-control 校验。原 rebase、候选身份、协议生成、内存/信号测试一并回归。shell 语法通过。

首轮测试命令引用不存在的 `test_constrained_hybrid_batch.py`，未运行任何测试；改为实际 `test_constrained_hybrid.py` 后得到上述结果。没有把未运行当作通过。Linux 专用四项需在学校合成测试中实际运行，通过后才提交。

提交前 PRE-RUN：Code 核查上述输入/编号/shape/有限性/预算及回归结果；Logic 核查源重放→同态确认→新基态→候选→原门+fresh control→下一步；Physics 不改模型/单位/守恒/物理时间，有限接受不当收敛。每组反馈后仍由正式协议与独立账本给出 POST 门和物理域证据；完整人工趋势、图与最终解释在心跳审阅中补齐。

## 实际提交及启动核验

- 科学代码提交 `4016d19dabcc1d579ad5ebb6586252b23e5e1715`，Mac、学校与 GitHub 分支引用已核一致。
- 学校合成回归 **118 passed in 18.42s**，4 项 Linux 专用检查全部实际通过。
- 作业 **74845**，`outputs/hpc/outer-steps456-20260921`，2026-09-21 19:48:17 CST 在 anode17 启动，32 CPU / 128 GiB，12 小时上限至 2026-09-22 07:48:17。
- 19:50:51 CST：RUNNING，step4/confirmation 正在准备；`source-gate-replay.json` 已落地，实际原物质响应与第三步保存残差逐位一致，9 个派生门全 true；重算候选三范数与 Mac 审阅一致。stderr 空。这是运行中的源预检，不是第四步接受。
- 调度终态只读捕获器 PID 2795690，`outputs/review-20260921/scheduler-74845/`；30 秒采样，最多 24 小时，不提交或取消作业。
- “USTC HHe 运行审阅与决策”已更新至本批完整合同与分支，ACTIVE、30 分钟。工具写入后读回逐字核对 prompt 成功；Mac 备份 `automation-after-outer-sequence.toml`。正常阶段自动衔接，无变化不通知，真正 SSH 认证断线再提醒用户并暂停心跳。
- Markdown 全仓扫描仅报告六份既有 lecture 文件，未触碰它们。该旧脚本默认扫描 README/docs/lecture，不覆盖 handoff，本报告另行检查；没有将全仓退出码 1 说成全绿。
