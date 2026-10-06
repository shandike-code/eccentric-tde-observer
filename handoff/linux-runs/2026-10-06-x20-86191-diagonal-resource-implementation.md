# 对角共享资源封装：两端小合成验收

另名version4封装已实现并完成两端小合成，本轮没有真实dat读取/下载、Slurm提交、map、反馈、ODE或物质步。Mac起点7a294a4759baded5037bc114899addc5a45d4d0d clean；学校生产4b02b0865ed45103770a6ecf63638c9696bd0a62 clean，未同步生产。旧85889/86061/86191预算关闭，完整301片DO NOT RUN。

## 实现与身份

新增operations/x20_85889_chord_diagonal_resource.py/.sbatch、diagonal_contract.py、diagonal_receipt.py，以及独立review_x20_85889_chord_diagonal_resource.py；新exercise与两组tests另名保存。旧driver/contract/receipt/reviewer、diagonal/square/scanner及全部旧协议字节未变。显式diagonal.slab_statistics只调用一次，无生产FunctionType、monkeypatch、任意kernel/reference参数；保留原binary64表达式与完整longdouble归约。72product/114sum是既有核调用计数，不是本轮生产性能或RSS证据。

新contract保留86061四历史JSON固定大小SHA，共66216B。exact新增字典键序检查；完整slab类型、列表顺序/长度、全部十进制字符串及零符号严格比较，另由原Decimal80审阅全部矩与误差。旧version3和85889/86061/86191冒新job显式拒绝。square与diagonal两项固定SHA均必需。

生产main新增必填--code-freeze，前后完整tracked py/sbatch清单与外部冻结清单核。配置前、native前核后及执行后检查实际项目module的file/spec origin为checkout内普通文件，逐SHA对清单；同名外部模块、缺失依赖、错误来源拒绝。环境另记录解释器、Python/NumPy版本与实际路径；不声称认证全部系统库或任意恶意进程。独立审阅CLI也用纯标准库核自身已载入项目模块，不导入数值扫描器。np.geterr固定divide=warn/over=warn/under=ignore/invalid=warn，入口和结束核；不seterr静默修正，原helper内部errstate不改。

前全SHA→六原句柄不可变bytes片hash→同bytes只读frombuffer新核一次→同原句柄seek重读→后全SHA不变；全SHA另有句柄。来源/归档前后核与28阶段、失败留存、严格1500s/6GiB生命周期门保留。shell分别转发USR1、TERM和INT并保留实际子进程信号。单个阻塞底层调用仍不保证立即响应。

外部submission审阅参数必填。ticket格式固定argv为sbatch --parsable和sbatch绝对路径，完整CHORD参数用exports记录；独立sbatch大小SHA、commit/job/run、code/binding摘要、started实际参数、原scontrol Command/WorkDir/可用SubmitTime都核，六场共同根目录还须等于外部WorkDir。code/binding摘要明确为json-ascii-compact-insertion-order-v1内容编码的SHA，由独立传入对象重算；不是任意缩进JSON原文件的SHA，也不是密码学执行证明。真实新提交ticket尚未产生，不能将虚构测试回执用于生产。

## 两端证据与失败保留

最终Mac384tests/2.28s，学校隔离384tests/7.24s，无skip；其中108项新封装/完整生产审阅、245项既有四核、31项v2。首次Mac377过1失败：foreign-origin测试传空清单，在目标分支前触发正确的unfrozen-module拒绝；修夹具提供完整清单后验证外部origin拒绝，未放宽断言。日志tests-01原样保留；后续378/379/383/384过程日志齐。学校首轮383/9.46s，复审补六场根目录对外部WorkDir绑定及拒绝测试后最终384/7.24s，两个隔离目录都保留。

新测试实际确认新核仅一次且输入基于同一只读bytes；首片外损坏/源变、完整摘要键序/零号/类型、square缺失或错误SHA、错diagonalSHA、版本/旧Job/错误importorigin/错误策略、运行中策略变化、时间/RSS/三信号/部分失败目录、收件链接重名越界损坏均拒。完整review_run用固定历史小摘要与虚构900002/job/时标/来源路径构造28阶段正负例；前后同时伪造runtime/native路径、外部binding/提交记录/根目录仍被拒。这不是实际production main、native前置或Slurm验收。

最终显式小E2E为33×2×3、T(x)=.5x+4。实际走新execute/authenticated_probe/receipt/review_evidence，21个场阶段，虚构900001调度。旧probe合成.bin读18432B，新driver37440B，每端本条E2E共55872B，非整套tests总读量。35成员小包往返通过；学校11个传输工件先manifest再逐大小SHA，Mac重新收件和独立review_evidence通过，完整slab与片/全SHA跨平台严格同。本样例不能泛化所有极小量：Mac LD52/1024、学校63/16384，保留已有极小差平方差异。Mac峰值RSS38699008B、学校36175872B只属于小E2E。

每次测试前后记录代码清单，最终fixture1686份源码/脚本加9历史小JSON，1695文件两端核同；这是隔离测试清单，未包含六份diagnostics源码/脚本。新增八文件后的完整tracked代码拟清单为1692项，另存待下阶段按实际提交冻结。生产入口仍枚举全部tracked py/sbatch，不以fixture清单替代。最终代码、parity、tests、学校日志及原失败均在outputs/review-20260925/20261006-diagonal-resource-*；Mac E2E目录diagonal-resource-e2e-20261006及-02，学校diagonal-resource-fixture-20261006及-02，最终收件diagonal-resource-school-e2e-20261006-02。

两端pre-diagonal-resource-implementation-20261006.bundle完整verify。准备CLI首系统python3调用报编码错误，原UTF8脚本保留并经解码检查；项目.venv解释器执行同文件成功。附加语法检查首次误把sbatch交给Python AST而失败，限定.py并另bash -n后通过；均非数值失败或来源断言放宽。

## POST-RUN与下一项

PRE-RUN为Code/Logic PASS、Physics WARNING，只准备份、实现和小合成。POST-RUN：最终测试及两端E2E通过，没有未处理数值警告、NaN/Inf或图；溢出警告与非有限拒绝由既有核测试覆盖，不承诺警告次数完全相同。数值示例仅解析仿射合成，无新物理趋势或生产资源量。

学校无工具CLI实际deepseek-v4-flash[1m]，42.2822705s，输入新版contract与driver全文及给定事实，非完整依赖/tests/reviewer源码或性能审计。其自报SHA疑问由代码中独立外部对象重算澄清；文件系统泛问没有实测支持，未弱化stat；生产checkout尚未同步属于下一阶段前置门。draft/review均保存，讲义164独立修订后追加。

下一项先读本报告与x20-86191-diagonal-resource-v1.md，核两端clean/exactHEAD、新完整bundle，再准备真实326小源/801原源码/current native六runtime/trial/归档链的独立前置核（拒dat配置hook），审阅生产main剩余路径与当次外部代码/来源冻结。只有完整PRE-RUN后才能独立决定一次新资源Job；六全SHA仍须未来新Slurm内前后执行。本轮没有新预算，不重交86191、不扩原3300s/Slurm1h、不全301片。submission_ready/production_resource_verified/controlled_speedup_measured/full_scan_authorized=false；accepted20、baseline/calibration/strictboundfalse与跨16响应失败/五率通过保持，HHe未完成。
