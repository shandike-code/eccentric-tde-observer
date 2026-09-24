# 76905拆分方向终态审计与固定物质精度检验

## 结论

76905在2026-09-25 02:24:49—04:49:26于anode18运行，32CPU/128GiB，COMPLETED/0:0，墙钟2:24:37，stderr为空。control4map、thermal8map、population8map共20map/5对反馈完成。两个方向均未接受，正式计数20/new0。`direction_budget_complete_requires_review`是预算完成，绝不是耦合解通过。

| 端点 | 加热相邻差（门0.001） | 内层噪声/信号（门0.1） | 原L2比 | 原质量加权比 | 原最差单元比 | 失败门 |
|---|---:|---:|---:|---:|---:|---|
| thermal08 | 0.0001282676353 | 0.03945624721 | 0.9940562158 | 0.9936512714 | 1.0031358222 | 最差单元 |
| population08 | 0.0001691257564 | 0.1117982162 | 1.0008251739 | 1.0021631177 | 0.9996378940 | 噪声、L2、质量加权 |

population08对新control四端点组合的三范数都收缩，但最不利质量加权比为0.9999971368，几乎贴门；它对原r20的L2、质量加权未收缩。保留这两个不同结论，不能替换原分母把失败变通过。thermal08对新control也仍最差单元恶化，最不利比1.0030031008。

## 独立验证范围

归档 `complete-1790282922279760917.tar.gz`，374321494字节，SHA256 `8ab3044404714d9d1c62420cbd41d1c9665c66660d6afac2f036584cbcd327ba`。Mac解包目录 `outputs/review-20260925/common-step21-directions-76905-received`。

`operations/review_common_step21_directions.py`核7708文件、760份反馈进程和1520份map进程回执。逐文件SHA、trial和投影方向、原r20、物理旧层、同一个新control种子来源、各case连续态链、逐块formal替换/和、9632频率ownership、256×16父网格与half128归层、能量账本、四编码残差、三范数、原门和新control四组合、完整态和资源均通过复算。所有源代码冻结声明另与Mac当前文件核对。Mac不重新积分物质ODE或下载9.41GiB辐射态；跨CPU解码容差为8个机器epsilon，字节/encoded身份及科学门不放宽。

全体端点气体热能正；峰/proc4041992KiB，每反馈态累计worker批墙钟低于900秒。map自身计算总计2888.4326秒，这不是总作业墙钟，后者包含初始化、哈希、大态保留、反馈和归档。各数组有限，未发现NaN/Inf、强度负值或资源失败。诊断图已检查；残差在所有层计算，图中材料索引不等于几何深度。

证据：`handoff/evidence/20260925-common-step21-directions-review.json/png`、`20260925-step21-directions-76905-terminal.json`。

## 为什么此时不拟合组合权重

`operations/analyze_step21_directions.py`在已核SHA的小工件上比较实际trial、响应温度/气体热能/电离能/HHe绝对布居及四分量。cell编号从0开始。

在固定cell1，新control残差为[2.4911909311,0.4922543079,0.0342322391,0.9291932352]；thermal08变化为[-0.0147089689,+0.0017316669,+0.0011290980,+0.0631561646]。热能编码的改变降低热残差，却增大HeIII/HeI对数残差，四分量总范数2.7042408313→2.7134835191。trial温度32807.6842→33128.4538K；响应温度396173.3999→394205.6209K，响应HeIII占比4.88049e-5→5.19279e-5。响应目标并未被接受。HeIII占比小不允许删除其log残差。

population08保持trial气体热能6255597836538.106erg/g，按电子数重新解码温度32807.6840555K，不能再把温度也冻结。cell1残差变化约[-0.0009807715,-0.0003095282,+0.0000047292,-0.0020863053]，作用小于热能方向。

| 向量差 | L2 | 质量加权 | 最差单元 |
|---|---:|---:|---:|
| thermal08 − 新control | 0.164845639 | 0.008156176 | 0.064879337 |
| population08 − 新control | 0.047647814 | 0.003298339 | 0.011352770 |
| thermal08 − thermal04 | 0.049188927 | 0.002614121 | 0.017443527 |
| population08 − population04 | 0.080650096 | 0.004438299 | 0.027386416 |
| 新control − 76871control | 0.055061046 | 0.003227446 | 0.015900779 |
| 两拆分变化之和 − 完整半幅变化（分别减各自control） | 0.084148593 | 0.005559983 | 0.018250940 |

布居方向跨4张map的向量漂移大于它对新control的信号。这不证明该方向永远无效，却足以阻止把当前差商当可靠Jacobian。cell1的拆分和近似重现完整半幅的分量变化，不代表全场已满足可加性：上表最后一行仍较大，而且混合了有限非线性和不同内层端点的误差，不能独断为某一种来源。这些漂移不是严格误差界。

证据：`handoff/evidence/20260925-step21-direction-comparison.json/csv/png`，图已检查。

## 下一批决策

新协议 `handoff/protocols/common-step21-direction-precision-v1.md`：三个物质状态逐字节不变，各从76905自身最新mapped场继续8张map，分别在新增4/8张重算反馈，共24张/6对；32CPU128GiB16worker，5小时上限，预计约3小时。新增control4/8分别比较候选对应轮次，原r20和全部科学门不变。物理/资源/血缘故障停止；零控制不稳定停止；非零方向noise或收缩失败仍完成已声明精度预算，不接受21、不自动混合或继续加算。

新文件 `operations/common_step21_direction_precision.py/.sbatch` 复用已验证的trial、零控制和反馈计算。准备阶段逐一核旧归档、源状态、seed及实际trial，不重建候选；复算全部物理反馈。新测试检查错误血缘、逐字段变动、零位移接受授权泄漏、固定预算和种子一致性；Mac共139 passed（1.02s）。代码走查发现从零control协议继承会带入禁止finite评估的授权，因此正式模板使用已审population08协议，零control单独关闭授权，非零case若继承零控制标记直接报错；未修改任何物理门或旧代码。

后续只在结果确实将方向信号与漂移分开时提出组合候选并全场重算确认。暂不能保证第21步成功，更不能给出整个大气表或整盘强度的完成日期。当前没有物理无解证据。

## 备份与预运行核查

Mac `outputs/review-20260925/pre-directions-final-audit.bundle` 与 `automation-before-directions-final-audit.toml`；学校 `/home/scc/pb24511938/pre-step21-direction-precision.bundle`。历史大态、源代码和旧run均保留。

[PRE-RUN CHECK]

Code: PASS — 明确三份trial/各自seed，原trial身份/native核、零控制授权隔离、预算和故障停止；139项本地测试、shell/diff检查通过。学校测试通过后方可提交。
Logic: PASS — 已审失败结果→固定物质精度诊断→六次反馈→独立复核；不跳到混合方向或接受。
Physics: WARNING — 内层噪声尚未解决，试验只检验固定物质下反馈稳定性；原物理dt、四分量和能量定义不变。

Key Issues:
1. 原r20分母与新control同时保存，不用较好看的比较代替。
2. 相邻漂移、跨轮漂移和信号分别报告，均非严格误差界。
3. 整批保持accepted20/new0；任何过门都需另行确认。

Decision: RUN — 仅限学校测试、SHA和资源检查通过后的上述24张map预算。

## 学校测试与启动

数值提交 `a03b6c07accb78a490d2bca4f1385e7111f93668` 已在Mac、学校与GitHub核对一致。学校139 passed（15.94s），shell/diff通过、工作树干净后提交。作业 **76931** 于2026-09-25 05:04:27提交、05:04:28在anode18启动，32CPU/128GiB，5小时上限至10:04:28。启动阶段日志为空，counter20/new0；详细状态见 `handoff/evidence/20260925-step21-direction-precision-76931-start.json`。

独立watcher：tmux `step21-direction-precision-76931`，21600秒预算，终态写 `outputs/review-20260925/scheduler-76931/scheduler-terminal.json`。定时审阅保持30分钟，仅有实质变化通知。Markdown检查仍只有历史六份lecture被报告，未改写历史文件，不声称全库格式通过。

## 05:53:04监督：control八张map完成，第8张反馈未结算

76931仍RUNNING，父status=feedback/control/after_maps8，control历史8张、active_map=None；thermal和population尚无state。watcher活跃、stderr为空，counter20/new0。此状态不是整批完成，也不代表第8张反馈通过。

control新增map4反馈已完成，七项零控制检查均通过：heat=0.00013841281578990975，两个端点气体热能为正（最低6.522904547399723e12erg/g）、完整态检查全部通过。152份反馈进程回执exit0、memory_guard通过，峰/proc4040452KiB；两反馈态累计worker批墙钟293.9671和300.2226秒，均低于900秒。

map4 final响应三范数8.187797731938714 / 0.26284566357214456 / 2.7055067489828524；与固定r20的向量差三范数0.16423261047541357 / 0.00964431096012722 / 0.0481635025245177。相邻反馈过门不等于响应已不再漂移，这个差也不是误差界。继续原协议，待control8过门才执行后续两候选，没有新增预算或修改数值代码。

小快照 `handoff/evidence/20260925-direction-precision-76931-control-progress.json` 保存所读文件SHA、原始summary/decision/postcheck、state/history、队列和回执汇总。本次为运行控制核查，非完整归档的独立数值复算；终态仍须按协议审计。备份 `outputs/review-20260925/pre-precision-control-progress.bundle`、`automation-before-precision-control-progress.toml`。仅新增证据和报告，不重跑数值测试。

## 06:41:54监督：control两轮完成，thermal第8张进行中

76931仍RUNNING，control8map及两对反馈完成；thermal历史7张，第8张已提交65/76块，首对反馈完成；population尚无state。stderr空、watcher活，counter20/new0。未触发原协议停止条件，继续既定预算，不提前接受或追加任务。

control新增map8七门全过，heat=0.00014104704491574703，final三范数8.191483113279789 / 0.26311744907262197 / 2.7055624902297626。对原r20的向量差三范数0.20745484198910874 / 0.01242251395335983 / 0.05853962224253224，较新增map4进一步增大；这表明原基态响应与当前更精细辐射态之间仍有漂移，不能把相邻加热过门等同于完整响应收敛，也不能把该差当严格误差界。

thermal新增map4原15/16门通过，仅最大单元收缩失败。heat=0.00013658213824362087，noise=0.034676398608881415；final三范数8.124244425750867 / 0.26037542683871495 / 2.7135432059724547；原r20比0.9941553972332184 / 0.9941392418203898 / 1.0031578875543417，新control对应map4四组合最大单元最不利比1.0029772321419077。该失败机制与76905的thermal08一致，但整批精度检验仍待完成。

三个已完成反馈对均无物理响应异常、气体热能正、完整态通过。新增control8与thermal4共304份反馈进程回执exit0/内存通过，峰/proc4038592KiB；连同control4共456份，峰4040452KiB。上述四个新增反馈态累计worker批墙钟均约291—305秒，低于900秒。

小快照 `handoff/evidence/20260925-direction-precision-76931-thermal-progress.json` 保存原始摘要、状态和所读文件SHA。仅运行控制检查，尚非整批独立数值审计；未改冻结代码、未重跑测试。备份 `outputs/review-20260925/pre-precision-thermal-progress.bundle`、`automation-before-precision-thermal-progress.toml`。
