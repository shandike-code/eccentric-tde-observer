# 全频源分项诊断未完成：四个尾块取证

75845默认4CPU/16GiB block24试运行于13:01:25—13:14:29在anode01完成，墙钟13:04、COMPLETED 0:0、stderr空。原始rate/direct/formal数组逐位重现；线性分项加和最大相对差4.274541644693036e-15，native峰值1477.3515625 MiB，独立/proc1512808 KiB。beta0的块净差-3.54638671875 erg s^-1 cm^-2（相对2.839341967209133e-12）。此为一个块的诊断，不代表全柱结论。

75847按成功依赖于13:14:29启动，在anode03用32CPU/128GiB/16worker至13:33:58，墙钟19:29，FAILED 1:0。72个块成功，71—74四块在新增线性算术检查中失败，均有进程收据、内存门通过；未生成全频summary。最大已成功相对差是block70 direct的5.864090697923844e-13；不能将其与缺失四块拼成“全频通过”。失败不是原正式反馈态门重新判定，也没有新物质步。

原诊断的缺陷是在线性检查超1e-12时立即抛异常，没有持久化具体绝对误差/尺度及分项数组。因此当前不足以判定是小量归一放大、舍入还是源计算问题，禁止直接放宽阈值或跳过尾块。

新独立operations/source_split_tail_evidence.py/.sbatch只重算71—74。原源三数组仍须逐位重现；原1e-12阈值保留，所有相对差、绝对差、归一尺度和linear_check_passed原样保存。进程正常退出只表示取证完整，根状态evidence_complete与measurement_only_not_acceptance明确不接受失败检查，不替代原full诊断failed。各块仍计算beta0，原生及独立/proc 6GiB内存守卫不变。默认4CPU/16GiB、2worker、4块共20次源函数调用、20分钟墙钟，新目录outputs/hpc/source-split-tail-evidence-20260923；无自动续投、无物质/辐射map更新。

诊断声明发现旧完整claims包含约320.177 GiB（去重319.894 GiB）的历史祖先大态，导致单块准备/结束校验昂贵。新固定态取证只读取当前final的9.41GiB辐射态，核该态和全部实际小输入/代码；保留旧完整声明及哈希，明确列出historical_dat_not_read_or_rehashed。旧完整声明先前校验事实保留，不声称本次又重新验了全祖先链；不改变当前输入身份或原科学门。物质/几何及原依赖小文件仍核，parent前后复核，worker核小依赖。

PRE-RUN：Code保存失败事实、测试微小绝对差仍失败/抵消尺度/无floor零态；Logic只补缺失证据，不补造全频接受；Physics误差量级未知，待实测。RUN。Mac取证与原分项/积分审计共7项测试通过、sbatch语法通过。备份outputs/review-20260921/pre-source-split-failure.bundle。package_source_split_review.py只归档终态诊断的小JSON/NPZ和调度证据，生成size/SHA清单，不含dat。原75845/75847及正式物理失败态均不改。
