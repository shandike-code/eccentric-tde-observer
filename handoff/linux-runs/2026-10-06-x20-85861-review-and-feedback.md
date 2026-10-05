# 85861真实映射独立通过，准备有界正式反馈

85861于2026-10-06 04:41:01–05:51:18真实COMPLETED0:0，Slurm1h10m17s。anode02/Students/qos_stu_cpu_long，32CPU128GiB/16worker；数值68452895c7953a4540d285a02e200b61f5b0cf3d。watch保存原始终态，后续06:02查询已Invalid job id，不改写当时查询结果。batch-exit只确认Python退出0，与真实调度证据分开。

程序4197.540961428545秒，父RSS1042059264B，最大worker3601644KiB，stderr0。full/half两张map分别166.437508973293和194.7881103651598秒；整体作业含源哈希、初始化、候选写入与比较，不能用单map耗时代替总成本。此前初始化source核验进度快照保留，没有跳哈希或改运行依赖。

归档complete-1791237072183870863.tar.gz，4596766B，SHA 7778e9779fbf4dd718ab64c0ddbfbcec646f6743e47ed7554e7aa67f1bcade0e，0dat。收件outputs/review-20260925/x20-85859-true-85861-received；batch-exit与scheduler-terminal单独获取。

review_x20_85861_true.py首次完整E2E通过325工件、799源码git show、34直接小来源及八dat的已审清单绑定，152worker回执、全部块频率所有权、trial/native/源算子、八场inode/size/mtime与clean/HEAD前后一致。301片以80位归并完整统计，原16门独立复核全过。Mac未重读大场或重算ODE；来源85821真实终态已核，84026未知仍false。

| 量（均按原锚点定义归一化） | full | half |
|---|---:|---:|
| 真实缺陷L2比 | 0.43799316541626593 | 0.6891454844260803 |
| 真实缺陷Linf比 | 0.5356181530970169 | 0.7678090765034457 |
| 预测误差L2比 | 3.517713240732378e-9 | 1.9185153515635243e-9 |
| 预测误差Linf比 | 5.497664612936512e-9 | 2.974146429949261e-9 |
| 边界L1/锚点边界L1 | 0.9261583749699049 | 0.8412397416901023 |
| 边界bol/锚点边界bol | 0.10000033076773784 | 0.5500009046213512 |

真实缺陷T(q)−q、预测误差T(q)−p、half仿射一致性三者分别审阅；最后一项L2比4.387550144768473e-10、Linf比6.308795457468129e-10，不是half缺陷降幅或未知固定点距离。full真实输出SHA 64992a047808bc99eed6463d11fba4cff655970b426f1141ee2efbdf164135de。2map、0反馈、0物质，accepted20/r20不变。

POST-RUN：stderr无警告，分片统计有限、平方非负，152worker成功且通过原内存保护，原16门复算一致。预测与真实映射接近只说明当前固定背景上的仿射预测准确，不给严格物理误差界；尚未验证正式加热或响应稳定。未新作图，不据此宣告校准或整盘I_nu。

下一步独立决定：按x20-85861-seed-feedback-v1.md，仅以本次真实full输出启动historical最多16map，在第8/16张后各测一对正式反馈。新16−8窗口、相对加速前85821H16、相对保存82518A16的四组合分别报告。保存A不重算；85821已有窗口及跨保存A加热失败仍保留。4h硬限，物理/资源/来源硬失败停止，漂移失败只完成既定窗口，不自动续交。


学校CLI实际deepseek-v4-flash[1m]。终态草稿把已完成的学校实测写为“待独立实测”，已改为待Mac独立审阅。讲义草稿将原锚点认成新full输入/输出、把三系数当作half标量、说真实缺陷数值未给，并误把Decimal80位称为extended精度，均独立纠正，原稿与review保留。讲义139已据实际代码重写。


## 85875启动与下一轮审阅

新数值提交4bace16902cbc2ef6f9f584f26f07a2928eecb93，Mac80项相关测试0.91秒；学校新/旧反馈入口同组先44pass/6fail（19.97秒），原因是旧84026测试收件目录已有部分文件却缺summary.json。按已审原归档SHA和清单补齐20652B小文件后，同组50项12.72秒全部通过，未改断言或数值。shell/diff检查通过。学校实际prepare小来源预检902项、29.99352598秒，trial逐位/native/相位/原能量和算子链通过；九个dat只查存在和大小，完整SHA仍由正式Slurm执行。

两端完整pre-85861-feedback-code-20261006.bundle已verify。增量85861-review-feedback-code-20261006.bundle=51665B，SHA 28dcf38685cc45efabb5aea374011e572cc9f6d951f38081a0e3aeddb2eb1e51，verify/fetch新ref/ff-only从学校6845289更新到4bace16，未reset或force。数值提交已push，学校运行中不再同步后续Mac文档。

2026-10-06 06:14:08提交85875，随即实际RUNNING于anode02/Students/qos_stu_cpu_long，32CPU128GiB16worker，4h硬限10:14:08、USR1提前900秒。06:15:23快照preparing、stderr0、4bace16/clean，尚无declaration、完整map或反馈。计划16map/2pair不是已完成数量。

watch PID2694432只是启动凭据，start_new_session/PYTHONPATH/Node PATH已记录，输出x20-85861-feedback-watch-85875；先保存真实scheduler-terminal再无工具CLI，预算18000秒/60秒间隔。首稿实际deepseek-v4-flash[1m]将85821两次误写82521，已独立改正并保留原文。

Mac已准备review_x20_85875_feedback.py，明确绑定85875/4bace16、85861真实种子、85821前态和保存82518参考，并分别保留source85821true/84026false。终态及部分pair须新收件目录独立审阅，不能以组件预检替代完整E2E；硬失败走独立失败审阅。ROOT=outputs/review-20260925，需archive-stem.tar.gz、同stem-receipt.json/同stem.json、85875-stderr.log、85875-batch-exit.json，终态另保存完整scheduler/execution快照。

正式命令：PYTHONPATH=.:src:scripts OPENBLAS_NUM_THREADS=1 .venv/bin/python handoff/audit_tools/review_x20_85875_feedback.py --job 85875 --base <archive-stem> --out outputs/review-20260925/x20-85861-feedback-85875-received --target handoff/evidence/20261006-x20-85875-final-review.json --terminal handoff/evidence/20261006-x20-85875-terminal.json。部分pair采用不同新目录/target且不传terminal。只有child退出时保留调度unknown，不伪造COMPLETED。


06:18:18续查：85875实际RUNNING累计4分10秒，声明已生成，historical child=initializing、history0、active_map=null，environment尚无。学校4bace16/clean、stderr0；不能把声明或父preparing标签当成已派发map。新的Mac审阅器87相关tests0.91秒通过；800源码git show、893现有小来源、9dat既有清单绑定预检通过，当前run两项inputs留待冻结归档。这不是pair08/pair16完整E2E，证据20261006-x20-85875-reviewer-preflight.json。实际观察保存在observation-02.json。
