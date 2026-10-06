# 85875窗口通过后的双历史新反馈验证

状态：独立入口、批处理、审阅器和测试已实现，尚未完成两端预检或提交；必须通过本协议全部前置检查后才能运行。不是85875的恢复或预算扩展。

## 科学问题与固定条件

85875完整16map/2pair经独立审计通过，真实COMPLETED0:0。H16−H8全部三范数/r20和/冻结信号通过，但H16对保存82518A16的响应仍失败；五类率/加热门通过。82518A此前窗口通过不保证保存端点就是固定点。下一项同时重新演化两种历史，检验新增预算匹配后的有限一致性，不以保存A拟合H或预设哪支为真解。

x20、原物理旧时间层、base/r20、phase1367、dt889.419892762322秒、9632×32×4096网格、128物质层、原转移/率/响应核不变。trial先写再init，逐位比较encoded/base/direction/r20/relaxation及native物理镜像。80195尺度从全部四P−C完整512维向量各范数取最小，禁止换分母、floor、clip、nan_to_num、改能量或删失败层。

## 两个唯一真实种子

- accelerated：82518 accelerated/endpoints-map16/mapped_final.dat，SHA256 `03d7c7ff5717e4871c35450e774992b79e729f919a986e93d732dd3250801fb2`。
- historical：85875 historical/endpoints-map16/mapped_final.dat，SHA256 `8814597bcd42c968341a59ea17ab85b5c51c0780cbc9079ee595e952da1b0bfb`。

两者各10099884032字节；完整路径前缀分别outputs/hpc/x20-global-window-feedback-20261001和outputs/hpc/x20-85861-seed-feedback-20261006。必须逐项绑定已审归档manifest、history iteration16输出SHA、实际学校文件。这里取mapped_final，不取原反馈的final（iteration16输入）。两支有共同来源历史，不是独立随机初值；只匹配新增map数量，不匹配累计年龄。

准备阶段核82518与85875真实终态、完整审计、trial/native/算子配置和小来源字节。source85821真实终态保持true，祖先84026未知保持false/null。生产阶段源大场前后SHA、inode/size/mtime及源码/HEAD/clean前后全核，任何不符停止。Mac只收排除dat的小归档，不下载或Git提交dat。

## 有限执行与判据

拟用Students/qos_stu_cpu_long、32CPU128GiB、16worker、6h独立硬限，USR1提前900s；每worker和父RSS<6GiB，free至少24份完整场。6h是预算上限，不是由单map外推的预计耗时。运行目录拟为outputs/hpc/x20-85875-matched-feedback-20261006，存在则拒绝，不能自动恢复。

顺序accelerated8→historical8→accelerated16→historical16，总32map、4pair、0新物质步。原内层ready、七门、物理域、资源、来源/代码完整性失败立即停并归档。第8张跨支漂移只测量；仅窗口或跨支漂移失败允许完成已经声明的另一支同龄端点，不增加数量或跳过失败。

最终须两支新16−8窗口、两支新16端点四组合响应均满足全部L2/质量/Max-cell除以原r20≤0.001且除以冻结80195信号≤0.1；跨支四组合五项率/加热原门全部通过。先完整向量相减再取范数。各支对自己旧pair16的变化独立报告，不替代新窗口或跨支判决；另保留新H对保存A的诊断，明确那是旧参考。

新实验的A、H反馈都重新计算，可声明matched_new_two_branch_experiment=true；这不回写85875的reference_recomputed=false。所有数值门全过只给reference_calibration_eligible候选资格，仍需独立审阅；baseline_replaced=false、accepted20、new_material_steps0、strict_error_boundfalse始终保持。失败不得自动追加32map、校准、接受21或宣告完整I_nu。

## 提交之前和终态之后

提交之前核两端clean/exactHEAD、完整Git bundle verify；新增独立入口、sbatch、来源/负路径/预算/门判据测试和审阅器。学校真实小来源预检必须核两种种子、完整来源归档、逐位trial/native和算子同一性；预检不冒充生产大场前后SHA。Mac/学校测试通过后再次给出具体Code/Logic/Physics PRE-RUN，使用verify+fetch新ref+ff-only同步，禁止reset/force。

每对及complete/failed/interrupted自动排除dat归档。batch-exit另外保存；watch先真实scheduler-terminal落盘再调用无工具CLI。终态独立核32map/4pair最多2432map及608feedback回执、全部四组合512向量和冻结信号、源/代码/资源/正物理域、所有门与新旧参考解释。Slurm未知时如实保留，不能借Python退出或下游成功造COMPLETED。然后完成POST-RUN、报告及学校CLI中文讲义的独立纠错，才决定下一项行动。

## 实现与边界细节

入口 operations/x20_85875_matched_feedback.py 和同名 sbatch；审阅器 handoff/audit_tools/review_x20_85875_matched_feedback.py、watch_x20_85875_matched_feedback.py。沿用原比较核的严格小于判据，恰好等于0.001或0.1不因本协议的上限记法而放行；没有放宽旧门。所有新旧比较均完整保留。生产准备和终态均检查全部声明来源SHA；登录节点轻量预检只对dat核存在与大小，不能冒充完整SHA核验。
