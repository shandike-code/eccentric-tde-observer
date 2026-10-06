# 86061后显式复用资源封装：两端合成验收

本轮实现新驱动、独立审阅器和收件工具，完成两端小合成与负路径验证。生产仍DO NOT RUN：没有新Job预算，没有同步学校生产checkout，没有读取或下载真实dat。Mac起始794ecc47e218a2b9d3e17438e0e4e8137739396a；学校82aea66f68dd9f1abc27a8268ffd5e1bfa34f418保持clean。旧85889/86061预算继续关闭。

## 新实现与不变的计算

新增`operations/x20_85889_chord_reuse_resource.py/.sbatch`、`x20_85889_chord_reuse_contract.py`、`x20_85889_chord_reuse_receipt.py`，以及独立`handoff/audit_tools/review_x20_85889_chord_reuse_resource.py`、合成exercise和58项封装tests。旧scanner、复用slab、v1/v2封装及旧独立数值审阅器均未修改。完整新文件大小SHA在`20261006-chord-reuse-resource-code-final.json`与小审计中。

新driver显式调用已冻结的reuse.slab_statistics一次，没有FunctionType或生产monkeypatch。前全SHA全部过后，六首片从各自句柄读取不可变bytes，先hash，同一bytes的frombuffer只读数组交给新核。保活至调用及同片后核结束；同片重读使用原句柄seek(0)，前后fstat和路径stat与初值一致。全场hash阶段另有各自句柄。统计中的减法树、cast、乘积顺序、完整归约、重建摘要和下溢拒绝沿原核。

生产入口固定86061历史probe/result/terminal/原review四份字节pins，不能传任意synthetic reference替代。生产算术环境NumPy2.5.2、LD63/16384、nearest0在大场读取前核；字段声明与历史基准在开始统计前核。完整slab逐类型/键/数组长度顺序/十进制字符串比较，零符号保留；还运行原独立Decimal80数值检查。审阅器与纯合约不导入scanner。测试用的共同review_evidence接受显式小参考，生产review_run只接受固定pins，两者不能混称。

小JSON拒重复键/非有限常量和溢出解析浮点；计数拒bool。小文件用O_NOFOLLOW、有界初始长度+1读取及句柄/路径前后stat；历史pin和接收压缩包也采用该路径。scontrol重复键拒绝。收件前核外部receipt、整包及每成员，拒链接/目录/越界路径/重复名/非白名单后缀/损坏内容，单成员32MiB、总64MiB；已有目录不覆盖。33成员小包只含JSON，无dat。

## 生命周期和未来生产要求

生产计划28阶段；共同数值路径为21个场阶段：前全SHA、六片各read/hash、新slab、六片重读、后全SHA。生产另外包含allocation/code/history、前后binding/live、code-after和comparison。各阶段monotonic偏移/耗时/已知payload平均速率与累计进程峰值RSS留存；累计峰值不能说成独立阶段峰值。live阶段payload列原归档字节，耗时包含native等工作，不是纯归档设备带宽。小来源与旧801源码、runtime依赖的大小SHA清单保存在binding/live证据；这些清单大小不能相加冒称去重后的实际设备I/O。

程序生命周期小于1500秒、RSS小于6442450944B，Slurm1800秒/USR1提前300秒、单节点4CPU16GiB/线程1为新协议拟定限制，尚未授予新作业。失败/信号/时间/RSS留下failure，拒不完整目录；单次底层阻塞不保证协作检查立刻中断。原全扫描3300秒/Slurm1小时预算未扩大。

未来归档须将实际日志中的child回执原字节另存为run内`batch-exit.json`，把运行目录外观察器的真实终态原字节另存为`scheduler-terminal.json`，外部原件继续保留；并把新提交回执的job ID独立传给Mac审阅。新review_run要求外部expected_commit、完整冻结code manifest、独立binding与terminal、expected_job_id，逐项对照包内副本、allocation/result/child。要求真实新job COMPLETED0:0、childexit0、全部阶段、无failure。包SHA只认证字节；旧86061终态不能认证新job，合成900001也不是实际提交。

## 实际两端验证

最终Mac132tests0.55秒、学校132tests5.46秒：58新封装+43既有reuse+31v2相关。首次119成功；补E2E后123通过/1失败，原因是测试预期ValueError、实际正确拒覆盖而抛FileExistsError；改为精确要求FileExistsError，随后124/129/132通过。失败日志tests-02完整保留，未放宽数值断言。原代码的NaN/Inf、極小值、缓存命中停止等测试仍通过；新测字段/片外损坏、源变化、历史pin篡改、任一摘要差/多缺键/顺序/精度/零符号、bool计数、假旧job、child失败、错时序/资源、缺核清单、失败目录和安全收件。

独立小E2E明确33×2×3，原probe实读18432B，新driver实读37440B，该单条E2E每端合计55872B合成.bin；不是整套tests的总读量。同平台新旧全部slab相等，原Decimal80核过。本样例跨平台slab、片SHA、全SHA相同；学校包33成员在Mac核大小SHA后，独立共同审阅再次通过。两端NumPy2.5.2/nearest0，MacLD52/1024、学校63/16384。小E2E峰值RSS35438592B/32243712B不代表生产峰值。

E2E实际走execute→21场阶段→小比较/共同review_evidence→archive→receive。调度/commit字段明确synthetic，不能说生产review_run真实E2E已通过；没有运行生产main中原85889来源/native/28阶段认证。本轮只核固定历史小JSON的pins，没有重跑旧86061生产数值审阅、旧8588工件审计、真实native或303877902B原归档。

学校隔离fixture-20261006及-02/-03，生产目录未同步。最终48文件逐SHA同，其中44个代码/测试/脚本、4个历史小JSON。最终清单`20261006-chord-reuse-resource-fixture-03.json`；Mac E2E `chord-reuse-resource-e2e-20261006-03`，学校下载小件`chord-reuse-resource-school-20261006-03`，独立parity-final-03与各版日志保留。

## 独立纠错、保存与下一项

学校无工具CLI事实/关键摘录审阅55.384秒，实际deepseek-v4-flash[1m]。原稿保留。采纳有界小文件/重复调度键加固后两端重验；纠正0.51秒写51秒、bool已拒却说待确认、单次调用被说成缺独立核验等。外部调度回执的来源不可由SHA替代，这个边界保留。CLI不是完整源码审计；Codex另逐段实读新文件与调用依赖。

讲义156追加，旧458461B前缀SHA1a87300e600f6d46baac6e38a32525ecfce64e8420698081c94da6c734d5856e逐字节不变；无图。两端pre-chord-reuse-resource-implementation-20261006.bundle完整verify，Mac25971713B、学校25850357B。小证据为`handoff/evidence/20261006-chord-reuse-resource-implementation-review.json`。

[POST-RUN CHECK]

Code: PASS（有限合成范围），132项两端通过，只有上述测试异常类型错误已修并保留日志；没有非预期浮点警告/NaN/Inf或物理断言放宽。Logic: PASS（显式数值路径、严格比较与小包），生产完整来源/native/真实终态仍未运行。Physics: WARNING，小合成仅解释数值与证据处理，无新物理趋势、图、全场Gram或提速实测。Decision: DO NOT RUN生产。

下一项先冻结代码、对生产路径/独立review_run的全部验收门完成剩余准备，核当前native/依赖/小源/归档，保存完整PRE-RUN；两端bundle备份verify/fetch/ff-only后才独立决定一次有界资源Job。真实六场SHA须在获准的新Slurm内前后完成。不要把合成成功当预算，不恢复86061、不重复85889、不自动完整301片。accepted20/0新map反馈ODE物质、baseline/calibration/strictbound=false，既有窗口响应通过、跨16响应失败/五率通过保持，HHe未完成。
