# 共同物理频域源项协议：独立四力复算

## 已执行

四端点边界诊断结论与失败历史见同日`2026-09-23-source-split-tail-check.md`。本轮直接实现另一条lab四力积分路径，不从旧路径差值回填结果。冻结协议见`handoff/protocols/common-frequency-source-v1.md`。

新增`operations/common_frequency_four_force.py`按lab频组与角度/深度依赖窗口的交集逐段积分；先求能量、动量矩，再逆变换。共享原P0微物理系数和交叠原语，独立于原子加热及原direct的积分次序；合成测试的标量oracle使用两个网格断点并集，另行核lab两矩和direct共动源。代码和协议明确不把本阶段当全物质反馈接受，也不宣称有限频率覆盖收敛。

`common_frequency_audit.py`先逐位重放原每块三个源数组，然后计算新四力。两态完整汇总时要求9632共动频组恰各一次，76块原源和与历史完整反馈逐位一致。原子加热使用历史反馈的atomic_rate_heating字段，保留旧formal与新common的体积L1/净积分差及原子/direct，沿用原门阈值和分母。source比较通过不等于所有态门/16个接受门通过，物质响应尚不求值。

数值代码commit `18faf3c`，协议数学格式在运行前单独整理；实际声明/提交代码版本`fe2d0c13f3b945351a3b9c5484b3db4bb725827a`。旧数值文件未修改。Mac和学校20项测试通过，包括常量解析解、不连续双网格、正负/零速度、分割可加性和非法域拒绝；sbatch语法及Python编译通过。normalizer只对新协议逐项审阅后应用，未操作旧讲义。

## PRE-RUN CHECK

Code: PASS — 窗口、射线和深度轴/有限性检查；物理域外直接拒绝；独立oracle测试；原数组必须逐位重放；native和proc双6GiB守卫。

Logic: PASS — 共动窗口先变为每条射线的lab窗口，在lab求碰撞源两矩后变回物质加热；未输入旧路径差值或原子加热来构造新值。条件全频任务重新验证pilot summary及声明哈希，不仅依赖调度退出码。

Physics: WARNING — 这只检验现有P0和已有有限频域，域外halo仍来自历史边界构造；不证明频率截断可忽略，更不证明全柱/全盘自洽。

Key Issues: 保留全部历史失败；不放宽原formal_global阈值；本阶段零新map/零新物质步。

Decision: RUN

## 已提交的有界条件批次

- 75907，`common-frequency-pilot-20260923`，final block24，默认4CPU16GiB/单worker，30分钟上限，15:20:09提交。pilot direct/common体积L1另须小于1e-10。
- 75908，`common-frequency-pair-20260923`，afterok:75907，cpu_long32CPU128GiB/16worker，previous/final各76块，总152块、2小时上限。声明和源验核均在allocation内，无自动重试、无原地恢复。
- 只读watchers PID3302000/3302056，分别写`outputs/review-20260923/scheduler-75907`和`...-75908`，30秒采样最多10800秒。失败后不提交新任务；若pilot失败导致全频依赖无效，应取消无效待依赖任务，先审错误。

备份：Mac `outputs/review-20260921/pre-common-frequency-domain.bundle`；学校`outputs/review-20260923/pre-common-frequency.bundle`。小报告和launch证据进Git，大态保留学校、不入Git。

下一审阅：终态后核原生/proc/时间/NaN/频组拥有/逐位回放，下载小型JSON/NPZ及清单/归档SHA；Mac独立复算两态的旧/新量及图。若源一致性通过，再设计独立版本的完整反馈桥，实际求正热能、噪声和三残差，原失败态不追认。若新算子失败，保存证据并定位，不能直接改门或跳过尾部。

## 75907原生单块通过，75908已用32核运行

75907在anode01于15:20:10—15:21:03完成，53秒、COMPLETED 0:0，stderr空。native峰值1478.46484375 MiB，独立/proc1513948 KiB；原三个源数组位级重放通过。direct/common体积L1为3.715042206950478e-12，净积分差比例3.8649859149008917e-13，绝对差的深度积分4.717606860640085 erg s^-1 cm^-2。这是block24预检，不能推广为76块结果。

pilot summary中沿用的atomic_vs_common标签，在单块模式实际取original source_rate数组，体积差8.920193619888485e-12；本轮没有重算该块独立atomic率核。完整两态分支明确使用完整原反馈的atomic_rate_heating数组。Mac证据单列`pilot_rate_label_is_source_rate_not_recomputed_atomic_rate=true`，避免名称使人误以为已复算全部原子率。此标签问题不改原声明或判据，完整态的定义没有该歧义。

原生pilot包614769 bytes，SHA256 `6a996ca20a0ec211b9bb5b03ebac0e9d1c9ffd94a22940974799641848a277f7`；Mac `outputs/review-20260921/common-frequency-pilot-75907.tar.gz`及同名received目录。11文件大小/SHA通过，Mac用`operations/review_common_frequency.py`核原partial、worker汇总、资源收据、数组有限性、原分母和源门；所有复算指标与Linux记录逐字值一致。PNG已目视，新common和source-rate曲线重合，旧同名频带的偏差单列；原数据中的细深度结构仍保留，未平滑。

75908在pilot成功后已用32CPU/128GiB/16worker运行；15:24附近读到previous完成48/76、final尚未启动、stderr空。首批完整两态结果尚待审阅，不能凭pilot解除全源门。

## 完整反馈桥的后续接口审查

现有`phase7b9_formal_feedback_pair_adapter.py`有受哈希约束的`reuse_completed_feedback_manifests`路径，以及`_material_response_residual`和`trial_feedback_pair_diagnostics`。这些纯响应/验收函数可复用，旧文件不改；但不能将原failed manifest改成complete，也不能跳过新态其余门。

候选下一实现：在新目录创建版本化的common频域源协议及两个新反馈工件，rate/direct/原子率/网格字段原样复用已经审计的固定态，new formal来自完整独立lab复算；parent/half的formal字段从新4096深度数组按原256×16映射重新生成。先对所有态门逐项复验（含拥有权、正率/有限、镜像、新common源一致性和资源/实际审计耗时），并保存旧判决对照。源协议必须有自己的hash与明确的common频域语义，不能借旧protocol_sha宣称新工件属于旧计算。

仅新态门真实通过后才可创建完整反馈对的独立协议，保持原16门数值，实际求两端点的响应、正气体热能、噪声及三个残差。精确decoded/native候选身份和同一物理旧层必须再核；Linux原环境执行。新协议的物质接受仍须额外的基态/四组合残差收缩与信赖域/双确认流程，不能直接将pair的有限接受报告当作第16步最终完成。频带外物理截断预算仍单列未解决。
