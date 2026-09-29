# 81647启动：四张原映射与更长方向的统计收集

2026-09-30 06:27:55 CST提交81647，06:27:56在anode06开始。实配Students/qos_stu_cpu_long、32CPU、128GiB、16 worker，两小时硬限至08:27:56；此硬限不是完成预计时间。run `outputs/hpc/x20-long-chord-20260930`，数值代码 `bd0060b255dd24208d0a602f2b7008d7d7f9424f` 已Mac/学校/GitHub同步。

06:30:07实查RUNNING2分11秒、`status=preparing`、父stderr空。正在做来源完整性预检，尚未有map完成证据。不能依据没有输出块或资源暂空推断死锁或绕过大文件哈希。

本批从冻结x20的late16源输出做四张原map，保留late19→late20真实对，相对原锚点late15形成一条更长方向。之后一次全场扫描收集原六态和新两态的5×5 Gram、八个9632组边界谱及301分片；原4×4子块必须复现。0反馈、0新物质接受、0外推候选；原r20及接受数20不变。更长方向不保证独立或有效。协议 `../protocols/x20-long-chord-v1.md`。

Mac28tests通过；学校25passed3skipped，三项跳过依赖Mac小数据结果，已在Mac通过。测试覆盖原映射接口、四张硬预算、缺回执即停、信号阻止派发、5×5直接缺陷对照、分母上界、对偶残差修复和篡改证据拒绝。shell语法、Python编译和diff检查通过。两端Git均通过bundle备份和ff-only更新，无force/reset；备份Mac `pre-fullspace-20260930.bundle`、学校 `pre-long-chord-20260930.bundle`。

学校只读watch `handoff/audit_tools/watch_x20_long_chord.py`，目录 `outputs/review-20260925/x20-long-chord-watch-81647`，启动PID1632452、预算10800秒；每60秒查询调度/小JSON，状态或完成张数改变才调用无工具CLI。首回执正常，实际模型deepseek-v4-flash[1m]。PID与状态仅是启动快照，下轮检查新鲜度。watch先落调度终态再调用CLI，不能让调度记录过期后失去证据。

回执 `../evidence/20260930-x20-long-chord-launch.json`、`watch-start.json`及`start-check.json`（后三者均带完整 `20260930-x20-long-chord-` 前缀）。完成后仅下载小归档/清单/receipt/terminal；独立核四map连续SHA、304进程回执、源trial/native/phase/dt、保留新对、完整分片与边界测度。新空间是四个位移系数、五个仿射权重，旧三维求解器不能直接套用5×5Gram；需新命名通用实现及测试/审计。近相关新方向可能通过更长位移扩展同权重上限下的可达集合，不能仅因数值秩没升就断言毫无作用；欠分辨或Gram舍入问题要明示处理界限，不静默裁掉特征值。

已经完成的旧3D排除证据及决定见 `2026-09-30-x20-fullspace-exclusion-and-long-chord.md`。讲义§86–87、图和CLI独立复核记录已更新。当前没有新的耦合收敛或整盘I_nu完成结论。
