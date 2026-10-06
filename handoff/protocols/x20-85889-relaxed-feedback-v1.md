# 85889之后：用户授权十倍响应容差的有界双支尝试 v1

2026-10-07用户明确选择“先放宽10倍，继续有界尝试”。本约定只新增探索性响应一致性门：全部previous/final四组合、L2/质量/Max-cell三范数，响应完整512维向量先相减再取原范数；除以原r20严格小于0.01，除以冻结80195原四P−C信号严格小于1.0。旧0.001/0.1结果并列保留，等于门限仍失败，不改分母，不把r20替换成最新残差。

旧AGENTS关于不放宽门的历史限制不覆盖本次用户明确授权的这两项响应容差。正性、守恒、物质物理域、频率所有权、来源完整性、内部辐射1e-4、边界及原七门、五类率/加热门、实际物质残差收缩判据全部不变。不得clip、floor、nan_to_num、删失败单元、改物理dt/能量或拟合保存A。放宽到信号1.0会允许与原试步信号同量级的差异，不能声称原严格方向精度已获保障；通过仅是新约定下的探索性一致，非自洽大气或正式校准完成。

## 来源与范围

唯一来源是已完整审阅的85889，数值提交9555a78a77b9025e30405684dee2669d9e43baee，真实COMPLETED0:0。两支从各自iteration16真实mapped_final输出开始，不取反馈final输入，不重新初始化另一物质试态。

- A：outputs/hpc/x20-85875-matched-feedback-20261006/accelerated/endpoints-map16/mapped_final.dat，10099884032B，SHA3f6c898f765e9854e378579f0f2fdc65fabe4def2f09d2a9554a4334d1a827b7。
- H：同根historical/endpoints-map16/mapped_final.dat，10099884032B，SHA6e10ec8904295909314a8cfa9022f541d0875209d4a42397d28e47728eed59eb。

固定同x20、old/base/r20、trial全部数组dtype/shape/bytes、phase1367、dt889.419892762322、9632频组/32方向/4096层/76块。先写trial再初始化，native镜像复核。两支各新增8张map，各在新map8后做一对previous/final正式反馈，总上限16map/2pair/0material；不是恢复85889或扩原32map预算。新map8的反馈输入对应累计map23/24输入，与旧pair16输入间隔8张map；mapped_final是累计map24输出，不混淆二者。

两支各自新pair8对旧85889同支pair16的全部四组合是本次窗口变化；新H8对新A8是匹配新增8张后的跨支比较。另存新H8对保存旧85889 A16诊断，reference_recomputed=false；不得误标旧82518或替代新双支比较。旧两支16−8窗口与旧跨支失败保留。本次既有跨16数据即使十倍仍在质量范数两门失败，因此不是把旧实验改判为通过。

## 执行与终止

另名operations/x20_85889_relaxed_feedback.py/.sbatch及独立review_x20_85889_relaxed_feedback.py，原驱动/率核/物质ODE/协议不改。原child构造器只接收明确的每支8张配置，不替换数值函数。按A8、H8顺序；原物理域/原七门/内层未就绪或执行故障即停止，不跑后续工作。响应窗口漂移只记录，不因A窗口未过而跳过H导致不成对。终态须两支均完整后才能判断新探索门。

候选资源一次单节点32CPU128GiB、16worker、线程1，Students/qos_stu_cpu_long，Slurm4小时、USR1提前900秒，每父/worker RSS严格小于6GiB；新map派发在生命周期达到13500秒停止，Slurm兜底，不保证阻塞调用即时中断。至少18个单场大小的空闲空间，保留失败和端点，不删旧场。两端完整bundle备份verify、exactHEADclean、冻结全部tracked py/sbatch、学校当前native/runtime及来源轻量前置后才具体PRE-RUN决定单次提交。真实dat完整SHA在Slurm生产prepare及结束时核；登录前置仅stat，不声称已重哈希。

新目录outputs/hpc/x20-85889-relaxed-feedback-20261007独占，不自动恢复、续交、追加预算、缩物理步或接受21。提交前保存外部实际脚本/argv/commit/run及原始返回，不明不重交；外部只读observer有限时长覆盖排队和4小时硬限，保存真实终态原始scontrol，不依赖作业自报成功。终态及小归档需独立审阅，不下载dat。

## 独立验证

新旧容差边界、恰好等于门限、NaN/Inf/bool/缺组合/缺范数拒绝，原比较对象不被改写；独立逐向量范数归并，原80195全部四P−C尺度与原r20重新核。新8张硬限、partial map、单个失败/超RSS不能放行，原七门及五率仍必需；旧严格false和新探索true可同时存在，但reference_calibration_eligible和baseline_replaced仍false。

生产审阅核实际16map/2pair、1216映射块回执/304反馈块回执、76块核心频率所有权、trial/native、全部响应向量/五率、来源及冻结代码、首尾场stat与SHA记录、真实COMPLETED0:0/child0。新探索通过与旧严格通过分别记录，未完成用unknown/None，不冒充true。保留84026原调度未知。

本协议本身不提交作业。全部实现与两端验收、来源前置、当次具体PRE-RUN通过后才允许一次上述预算；不启动全301片差场统计，不扩旧86290/86191等预算。无最终大气、全轨道/全盘I_nu或严格误差界声明。
