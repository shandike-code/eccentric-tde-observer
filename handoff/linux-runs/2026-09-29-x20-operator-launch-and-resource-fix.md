# 80823/80826已启动；80822资源参数错误记录

截至2026-09-29 14:45:51 CST，两个作业都在anode18运行：

| 作业 | 开始 | 资源 | 实际阶段 | 硬限 |
|---|---|---|---|---|
| 80823 midpoint | 14:40:00 | cpu_long32CPU128GiB，16worker | initializing_midpoint，0完整map，父stderr空 | 16:40:00 |
| 80826 scan-v2 | 14:43:40 | 默认4CPU16GiB，单扫描进程 | scanning，父stderr空 | 15:43:40 |

硬限不是完成时间预测。中点初始化仍完整复验历史config来源；旧config的依赖链包含大量外部大态，因此此时无map不能直接判死锁。两任务都没有已接受物质步，也未有本轮最终数值结论。

80823启动代码`0a6523bb2cbe885a4b7a03a274db00e4567e36ee`，80826入口修复代码`86cb1aa475d08b15eaae77dabd4442260644e93f`。Mac与学校已同步；0a6523b已推GitHub，86cb1aa的推送回执另核。随后仅交接文档变更不会改已冻结数值文件。

## 必须保留的启动失败

首交80822在14:40:00–14:40:10以FAILED/1:0退出，错误为`Request at least 6 GiB per worker plus 2 GiB parent headroom.`。原因是我在scan模式将4CPU错当成`require_allocation`的4个worker，要求内存26GiB；实际扫描仅单进程。未创建run、未扫描场、未做map或反馈。并非数据/物理故障。

我没有更改正在被80823使用的文件。新增`x20_history_scan_v2.py/.sbatch`，以一个扫描进程调用原内存守卫，再单独要求4CPU；科学扫描函数和协议完全不变。新增回归直接模拟4CPU16GiB环境并证明旧调用会拒绝，新入口通过；不足CPU/内存/缺Slurm仍拒绝。Mac/学校各14项相关测试通过后提交80826。旧80822终态和日志保留。

最初科学实现相关测试Mac87passed；学校85passed2skipped（两项Mac-only接收工件）；所有冻结入口shell语法及新增Python编译通过。不能用测试通过替代科学端点审计。

## 监督、记录与后续

两端备份`pre-80554-review-20260929.bundle`；资源修复前另存`pre-scan-resource-fix-20260929.bundle`。学校启动回执`outputs/review-20260925/x20-operator-launch-20260929.json`与`x20-scan-v2-launch-20260929.json`，Mac小证据在`handoff/evidence/20260929-x20-operator-*`和`20260929-x20-scan-*`。

学校只读CLI监督：`x20-midpoint-watch-80823`、`x20-scan-v2-watch-80826`，都在`outputs/review-20260925/`；脚本`handoff/audit_tools/watch_x20_operator.py`。当前已有CLI回执，watch更新时间仍正常；监督无编辑/调度权限，Codex独立决策。实际CLI服务模型以modelUsage为准，前次已实查deepseek-v4-flash[1m]，不把工具名当Claude模型身份。

Codex“USTC HHe 运行审阅与决策”已恢复ACTIVE、每30分钟。已替换旧80554运行中的过时说明，记录这两个新任务、80822错误、资源修复、冻结协议和严格后续分支。SSH失联时暂停自动跟进并提醒用户重新认证，不取消Slurm、不自动重交。

完成后仅接收最新小归档/receipt/manifest/terminal。新schema尚需独立审计：scan重算全部301个slab的Gram/正性区间/系数和边界谱；midpoint核76块与资源，重算301slab的仿射四比值。不能直接套旧pair审计，也不能称Mac已读完原始大场。若可行，另行冻结真实full/half候选验证；若不一致或无可行方向，按科学协议诊断算子/全频求解，而非盲加Picard或暗换r20。
