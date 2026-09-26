# 本地旧辐射检查点第二轮清理（2026-09-26）

用户在首轮清理后要求继续清理，本轮删除六个旧大场：phase7b7e_damped_matter_radiation_map.dat、phase7b7i_second_radiation_map.dat、phase7b8b_secant_radiation_map.dat、phase7b8e_backtracked_radiation_map.dat，以及phase7b9d_work/state_a.dat、state_b.dat。每个9.40625 GiB，本轮56.4375 GiB，两轮共112.875 GiB。

前四个分别是早期物质方向、第二次映射、secant和backtracked试探映射，旧协议和小结果完整保留。后两个旧缓冲的后续收敛态phase7b9e2_work/state_a.dat、state_b.dat保留；并保留正式验收三态、迁移双种子、所有其余大检查点与当前Mac审计输入。学校计算不使用本轮Mac旧大场，未执行任何远端数据删除。

执行前核验路径、非符号链接、完整文件大小、inode/mtime，lsof确认六个路径无打开描述符；逐文件先写删除清单再删除，回执见../evidence/20260926-local-checkpoint-cleanup-round2.json。未复制大场备份、未重算内容SHA；旧阶段完整大场重放需要重新生成，不能保证原字节恢复。

已保留旧库存清单为历史快照，不将它当作当前文件清单。本轮未清理48GiB的学校审计下载目录：其中包含当前审计依赖，不按下载日期整目录删除。原代码与小报告没有改动。
