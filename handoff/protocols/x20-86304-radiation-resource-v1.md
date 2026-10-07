# 86304当前六场独立首片资源协议 v1

## 状态、目的与范围

本协议仅冻结下一实施阶段的验收约定，不授予生产预算，不生成提交ticket。全部旧Job预算关闭；完整301片仍DO NOT RUN。新来源适配和小合成已完成，见2026-10-07-x20-86304-source-adapter.md；这不等于生产main或当前native验收。

拟议一次作业只统计当前86304六场的频组[0,32)，每场32×32×4096个binary64值，六场共201326592B。测量完整来源核、六场前后全SHA、一次冻结diagonal统计及同片重读的墙钟和峰值RSS。其余9600频组仅核全SHA，不产生统计。不得换片、增加第二片、重复计时或恢复失败目录；没有map、反馈、ODE、物质更新、候选场或原子核重算。

全场H1仍是四个P/F组合的映射后差范数比是否均严格小于1。首片只给注明[0,32)的局部比值，不能给全场H1判决；输出global_h1=null和full_field_statistics_complete=false。零分母的该组合比值、投影或余弦为null，不把未定义当通过。H1不是物质接受门。

## 当前对象与来源闭合

六场按AP/AF/AM/HP/HF/HM顺序，固定来自86304的endpoints-map08；每场10099884032B、shape9632×32×4096、little-endian binary64。完整路径/SHA从已固定SHA的小适配结果及原86304最终审计双向核；不得让CLI接受任意六场或替换源job。原85889 M只认证新seed，当前P→F为第7张，F→M为第8张，反馈使用P/F，不需要T(M)。原source84026调度未知继续保留。

实施前另生成固定外部来源清单：新适配320份JSON及其原独立审阅基准、两原归档manifest/终态审计、两支native_trial_audit与initialized_identity、当前trial、原physical_old/base/r20、当前两native打开路径/全部runtime输入、原几何与频率配置依赖。逐项明确来源、大小、SHA、位置和必要性，去重计数并冻结；不得把旧326/801/1696计数硬套到新来源或新代码。当前320只核声明，未重载native或物理数组，必须补足这些门。

新的live适配只读取原配置和物理数组，配置期间hook拒dat打开、拒初始化与map/反馈/ODE调用；不调用会migrate_trial的新run初始化。逐位核trial的encoded_state/base_encoded_state/finite_direction/base_residual/relaxation与固定原x20，再核学校native的温度、H/He布居、密度、能量及镜像dtype/shape/bytes，phase1367、dt889.419892762322、9632组/32方向/4096层/76核心块。Mac重新decode与学校可能有已记录末位差，不能将Mac重decode逐位等价当成已通过。固定原物理能量、r20和80195尺度不变。

上述科学来源在新Slurm内前后核。配置/小数组来源可在实施验收阶段先单独有界只读检查，但不能代替新作业实际前后核。NPZ默认小于1MiB；唯一已授权例外为17159976B、SHA33f248d5cf35ac07fffd139e1cd99d4edefa590debf7e109f67f2dbc57adf455的原physical_old_time_level.npz，不推广例外。

归档payload前后各核原85889的303877902B/SHAf20c313bc92af5730a16d7a9c604793873719bd710b53d0fc763813349cd120c及86304的154064839B/SHA595a01a5373980afd28acdb7224cd74321561da005892297e0995f5c9207a0b8。这是原已审归档的完整性绑定，不重跑旧全包数值审阅；两包两遍合计915885482B逻辑payload。

## 新身份与数值接口

拟另名operations/x20_86304_radiation_resource.py、同名.sbatch、x20_86304_radiation_contract.py、x20_86304_radiation_live.py、x20_86304_radiation_receipt.py和handoff/audit_tools/review_x20_86304_radiation_resource.py；实施前查重。独立schema标识86304-radiation-resource-v1，source_job=86304与当次新execution_job分开。不得调用旧driver.main，或仅更换旧binder的job/map16/history。测试可故障注入，生产禁止FunctionType、monkeypatch或可替换kernel/reference参数。

显式调用冻结operations/x20_85889_chord_scan_diagonal.py的slab_statistics一次，SHA a3737320592fac5511d5f8c979524919b5fd9229e36634b64b7e8437cc0b0896；导入square辅助SHA61e6c6d559975f7f863282209eb1ad016c4594f7f898f0c7e0a5d515878c862b，原scanner及全部传递依赖亦冻结。不能改binary64减法树、操作数顺序、完整longdouble求和、直接小差矩/绝对项、Linf、重建误差、原场极值或非零乘积下溢拒绝。不混入scratch/out=、np.square、分块归约、BLAS/einsum、FMA/fastmath、大Gram相减或裁剪。

每组合直接五向量为$d=H-A$、$r_{\rm A}=T(A)-A$、$r_{\rm H}=T(H)-H$、$e=r_{\rm H}-r_{\rm A}$、$d'=T(H)-T(A)$。基底为$[H_{\rm F}-A_{\rm F},A_{\rm F}-A_{\rm P},A_{\rm M}-A_{\rm F},H_{\rm F}-H_{\rm P},H_{\rm M}-H_{\rm F}]$。保存五基底完整矩及四组合各完整5×5直接矩、绝对乘积和、Linf、重建误差和六场极值。无权求和矩的量纲为存储强度平方，不是能量/光度或质量加权内积。

保持既有数值检查：$\tau=64N\epsilon_{\rm LD}<0.01$，矩、PSD全部主子式、重建Cauchy尺度与直接矩一致性均用原独立Decimal80审阅。逐点重建及恒等式先以$32\epsilon_{64}$乘六源绝对尺度加8个最小binary64次正规量核，不用伪大重建误差掩盖错误系数。该规则是数值一致性门，不是严格舍入界。零号、键序、类型、长度、完整十进制字符串保留，37位输出不是37位可靠精度。

当前六场没有已认证的真实首片数值基准。因此取消旧86061摘要相等门在新对象上的适用性，不等于降低旧协议门；旧协议保持原字节。新作业用原独立Decimal80审阅所有矩和重建一致性，另核来源、执行链及事前逐单元合成oracle。Mac不读真实dat，不能声称Decimal审阅重新逐单元算过当前真实内积；它核摘要内部数值一致性。将来如需真实原值独立重算，须另定范围和预算，不能在本次暗增第二核。

## 代码、环境与执行生命周期

完整新提交全部tracked py/sbatch前后对外部冻结清单；实际已加载项目模块的file/spec origin必须为该checkout普通文件并匹配SHA，拒外部同名/链接/未冻结模块。新文件须已提交，不能拿旧1696清单当新全清单。环境包另记解释器与NumPy实际路径、Python/NumPy/BLAS版本；计划学校NumPy2.5.2、longdouble nmant63/maxexp16384、FE_TONEAREST0。入口及全部导入后、结束前geterr固定warn/warn/ignore/warn，不seterr静默纠正。变化须失败保存和另审，Mac LD52/1024合成能力差异保留。

拟资源：单节点4CPU、16GiB、Students/qos_stu_default，单个数值进程，无数值子worker；OMP/BLAS/MKL/NumExpr线程1。Slurm1800秒，USR1提前300秒；程序完整生命周期严格小于1500秒，数值进程累计峰值RSS严格小于6442450944B。来源配置、全SHA、统计、结束核均计入1500秒，不能在计时开始前做昂贵来源工作。实测scontrol分配和环境须相符。短暂scontrol/git等工具进程另记录，禁止派生数值worker；进程树即时RSS及已结束子进程rusage另列，不把父/子历史峰值简单相加当同时峰值；整个作业由16GiB分配约束。此资源只是拟定上限，尚未授予。

固定顺序：独占目录与started → 分配/代码/origin/来源/归档/native前核 → 六全场前SHA全部通过 → 六首片原句柄读取不可变bytes并SHA → 同bytes frombuffer只读数组单次diagonal核 → 原句柄seek(0)同片重读SHA → 六全场后SHA → 来源/归档/native/代码/origin后核 → result/finished。原六首片句柄贯穿统计和重读；全SHA可用另句柄，不能说全程只开六次。各次fd/path的dev/inode/size/mtime_ns/ctime_ns在本作业内一致，链接/替换/短读/多余尾字节/错误SHA直接拒绝。跨节点dev可不同，不硬套历史全部stat相等。

两遍六完整场121198608384B，加六首片两遍402653184B，正常field逻辑payload121601261568B；归档915885482B另列，来源、代码、配置及小证据逐清单计量。正常EOF探测零字节；异常每场每遍最多额外1B即拒。hash缓冲不重复计为设备读取；所有数字不是磁盘设备I/O或速度保证。不得下载/写入真实dat。

每阶段monotonic开始/结束/耗时、实际payload/速率和累计peak RSS留存；次序不重叠且总时间覆盖。合作停止在hash块/片读/矩间/缓存命中及阶段前后检查，不能保证立即中断阻塞调用。USR1/TERM/INT转发并留证，shell wait正确处理打断；信号、RSS、超时、来源或数值失败都保留failure和已完成阶段，不写成功、不续跑、不换片、不重交。Slurm硬限兜底，300秒余量不保证成功清理。

## 外部提交、终态和独立收件

未来实际启动前单独PRE-RUN决定一次预算。外部提交器先持久化意图，记录sbatch完整大小SHA、argv、所有环境导出、expected_commit/run/外部code-binding内容摘要，再单次sbatch并保存原始stdout/stderr/rc与时标；未知结果不重交。当次job不得是86304、85889、86061、86191、86290等旧job。核真实scontrol Command/WorkDir/JobId/可用SubmitTime与ticket，started/allocation/result/childexit互相绑定；SHA或终态单项不是执行证明。

独立运行目录外observer拟最多2400秒、每10秒只读，实际终态即保存原始文本/时标退出；排队耗尽记未知，后续只读观察独立决定，不能由此重复提交。成功必须真实新job COMPLETED0:0、childexit0、全部阶段/result/finished、无failure、完整来源和数值审阅同时成立。batch只证子进程返回；旧86304终态只认证来源。

归档只收显式白名单普通JSON/日志，单文件32MiB、总64MiB；拒dat、NPZ、大二进制、链接、目录、越界、重名、重复键、bool冒整数、非有限数。必要数组比较摘要记录dtype/shape/bytes SHA，原数组仍以固定外部来源核验。整包及全部成员大小SHA先核，再Mac独占收件。独立review_run不导入数值scanner，要求外部当次ticket/终态/代码/当前来源绑定；不能仅消费包内自报true。原提交与观察器证据保留外部原件。

## 实施验收、后续统计和当前决定

新生产封装另名实现后，两端至多129×2×3合成.bin实际走新execute、一次显式新核、来源替身隔离、receipt往返和完整review_run，虚构job/调度标明合成。包括错旧来源/错map/错seed/native/runtime、前后同时错源、缺square或错origin、首片外损坏、读取中替换、SHA/shape/顺序/读量错、第二核调用、信号/墙钟/RSS/部分失败目录、旧终态冒新job、ticket错误、缺阶段、重叠时间、假成功等负例。冻结源码与完整摘要、独立Decimal80逐单元oracle均核；生产不得接受synthetic基准或跳来源参数。当前35项小合成只认证原适配和slab接线，不代替这些新封装测试。

后续全301片若提出，必须另协议与一次明确预算，先解释当前首片实测仅局部成本，是否足够支持全扫仍未知；保留每32组恰好一次、核心块/末尾覆盖、全部逐片摘要、按频组升序确定归并和Decimal80重建。当前不实现并发、不从18.40569秒旧首片或新首片乘301承诺完成，不自动扩大旧3300秒/1小时。首片通过也不触发下一作业。

本阶段Code/Logic为设计审阅，Physics WARNING；Decision: DO NOT RUN生产。production_driver_implemented、production_resource_verified、submission_ready、new_production_authorized、full_scan_authorized均false。accepted20/newmaterial0、原严格与十倍探索判决、正性守恒、dt/能量/r20/80195不变；无新自洽大气、谱半径、全域收缩、真解、误差界或ETA结论。

## 全文独立审阅后的明确项

这里$N$为当前slab元素数，首片$N=32\times32\times4096=4194304$；不是9632个频组，也不是301片数。76核心块按连续128组分配，最后块32组，每组只属于一个核心块。令$E_{i}$为第$i$个向量的实测重建误差平方和，$D_{i i}$为直接矩对角，则原Cauchy误差尺度为$\sqrt{E_{i} D_{j j}}+\sqrt{E_{j} D_{i i}}+\sqrt{E_{i} E_{j}}$，另加原绝对项归约容差；不从此推物理解误差。

原review_x20_85889_chord_scan.review要求完整shape覆盖和三遍全场读量，不能直接用在本首片协议。新独立review_run可以调用其冻结matrix/summarize等纯Decimal数学helper，必须另核真实shape9632×32×4096、唯一slab [0,32)、本协议两全SHA加首片两遍读量；不得伪改shape为32或伪造其余300片来满足原入口。所有统计范围标记均必须是局部。

六原场极值须是有限实数并满足非负和min不大于max，与零分母比值null是不同字段；不能把null喂给极值归并。首片六源201326592B只是源bytes payload，差向量、longdouble缓存和临时数组另占内存，不能据此推RSS小于6GiB。约81MB/s只是忽略其他工作时的必要平均payload速率，不证明共享盘或本次计算可行。SHA绑定字节身份，科学来源还依赖映射/native/执行证据和原独立审计，不把SHA相同提升为内容物理正确。
