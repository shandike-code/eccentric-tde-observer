# 回溯再次失败：停止缩步，分解固定态源一致性差异

75819在anode02使用32CPU/128GiB/16worker，于2026-09-23 11:40:40—12:29:15运行48:35，FAILED 1:0。控制2map/1pair完成；1/64候选完成4map，第一轮两端正式反馈态均gate_failed，物质响应尚未执行，half1/128未运行。根failed、pending round1 feedback保留。squeue返回Invalid job id是历史已回收；SSH正常，独立watcher保存了终态，不能把该错误当断线。

## 工件与唯一失败项

失败包outputs/hpc/step16-backtrack-20260923/archives/failed-1790137738589080740.tar.gz，109680055字节，SHA256 `c0e53063359ae553a73305b84dddfce2a2154f61d0a8c02bff8d602ff8c42ca0`；Mac outputs/review-20260921/75819-failed.tar.gz及75819-failed-received。2046文件清单size/SHA通过。审前Git备份pre-75819-source-audit.bundle在同目录。新只读review_step16_backtrack_failure.py按实际alpha1/64/round1审阅，不修改之前的1/32审阅器。

两端76partial按原顺序重加，与完整反馈、parent及half数组逐位一致；实际物质位移、native身份、旧层/分母、协议claim和连续端点通过。两端仅formal_global失败，其余10类状态条件通过。没有证据支持OOM、超时、缺块或非有限数组解释本次停止。

| 量 | previous | final |
|---|---:|---:|
| 原子/逆四力体积L1相对差 | 1.3338102788830914e-5 | 1.3341367871401486e-5 |
| 原子/逆四力净积分相对差 | 0.0012080263125529619 | 0.0011627872078922939 |
| 原子净加热积分 | 5.782620448210918e11 | 6.007918210909016e11 |
| 逆四力净加热积分 | 5.789614454811868e11 | 6.014912273957769e11 |
| 绝对积分差 | 6.994006600949707e8 | 6.994063048752441e8 |
| 原子/直接共动加热L1差 | 1.9681811789556303e-12 | 1.9712094573505496e-12 |

积分单位erg s^-1 cm^-2。原net门仍1e-3。注意本次净积分为正，上一次1/32为负；两个候选和辐射历史不同，不能把这两个点当作受控同态导数。现只有15个已接受并双确认的有限步；本轮无新接受步，物质气体热能/三范数/噪声未评估，不沿用控制或上次首轮的值。

## 决策与新诊断

按先前声明停止继续缩步，不恢复75784或75819，不尝试1/128。转向固定失败端点的源项差异分解，原门不改。

源码scripts/phase7b7f_assembled_diagnostics.py的正式路径为：同一全局强度及halo生成共动强度，构造extinction=absorption+scattering和emissivity=thermal+scattering*J；按原频率重映射计算实验室系碰撞源，再积分能量/动量并逆Lorentz变换。原子加热与直接共动加热差约1e-12；与逆四力的差约1e-5（体积尺度），在净积分抵消后超过1e-3。此证据把当前主要差异定位到后一条计算路径，不证明具体重映射或离散公式有bug，也未排除有限频域截断。

新operations/formal_source_split.py在75819 full/feedback-round1 final的原物质和原辐射字节上逐块调用原assembled_block_diagnostics。首先要求原rate/direct/formal三数组逐位重现，随后仅在当前进程的_local_fields上分别保留吸收、热发射、散射，重算三分项；退出或异常后恢复原函数，不改磁盘冻结模块。每个分项使用原频率、角度、深度和真实beta，输出沿深度数组及逐块柱积分。

固定辐射下碰撞源对这三项线性，分项之和与原结果的最大误差以分项绝对尺度归一，要求不超过1e-12作为诊断算术检查；该检查不是替换原科学门。另将beta和parent_beta设零进行一个诊断对照，活动区.dat仍只读，外部halo随诊断beta构建；这是反事实对照，不是新的物理解或接受候选。β=0检查不能单独证明真实β下误差消失的阶数。

每块共5次源诊断（原始、三分项、beta0），不做辐射map、不推进物质或物理时间。先默认4CPU/16GiB只测block24；原生逐位重放、线性检查、6GiB native和独立/proc门通过后才32CPU/128GiB/16worker覆盖76块。试运行最多20分钟，全76块最多1小时、380次块源函数调用，无自动续投。每批完成后响应停止信号，不再派下一批；目录已存在即拒绝，当前版本不支持未经审阅的原地恢复。

准备时在allocation核.dat及完整来源，声明冻结源claim、全部操作/诊断代码及原依赖；worker核小输入、parent前后核全部claims。完整76块原三数组求和须与存储完整反馈逐位一致；分项及beta0结果仅作诊断。两个内存门、hugepage0、stdlib relay保留。原失败大态不会被写入或删除。

PRE-RUN：Code对照原源函数、测试分项不改物质/强度输入及异常恢复；Logic固定态分项而非反推新响应，先单块再全域；Physics线性成立但差异原因未定，不允许用诊断分项修补正式结果。RUN。首轮测试发现未提交入口一处括号语法错误，已修复；最终4项测试与两个sbatch语法检查通过。POST-RUN：回溯包两端唯一失败独立复现、数据有限且归属完整；源分项实际Linux结果尚待试运行。新数值提交、调度及报告后附。

## 逐块抵消与实际提交

已存final partial的带符号柱积分差逐块相加为-6.994063048751974e8，而逐块积分绝对值之和为7.874720907447229e12 erg s^-1 cm^-2。block24为最大负贡献-7.223387971857146e11，block49正贡献6.55460073584456e11。明细20260923-75819-frequency-difference.json。lab/comoving同名频带并不选择同一组光子，块间频率迁移/抵消不应被逐块误判为总能量误差；必须全76块求和，不能用top块替代完整柱结果。

数值代码bcb248efaf2206628376b8b2bb9ac1876b833321已同步三端，学校4项测试通过。75845默认4CPU/16GiB于13:01:25在anode01启动，单block24试运行、20分钟墙钟。75847于13:02:25提交，32CPU/128GiB/16worker、1小时墙钟，Slurm afterok:75845成功依赖；全频入口还会核pilot报告与源claim。13:04:53初查pilot RUNNING/preparing、stderr空，75847 PENDING/Dependency；没有把排队当作32核已在计算，也未宣称pilot通过。

对应run为outputs/hpc/formal-source-split-{pilot,all}-20260923。只读watchers PID1178849/1178852，outputs/review-20260923/scheduler-{75845,75847}，各30秒采样最多7200秒，均脱离SSH且无提交/取消能力。launch证据20260923-{75845,75847}-launch.json保存资源与依赖状态。学校备份outputs/review-20260923/pre-formal-source-split.bundle。

定时审阅已保持每30分钟ACTIVE并改为源分项诊断，明确不继续缩步、不更改原门、pilot失败后的无效依赖处理、全频审计要求及SSH断线提醒。更新前后TOML在Mac outputs/review-20260921/automation-{before,after}-source-split.toml。数值提交与后续调度说明提交分别记录。
