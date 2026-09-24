# 第20步候选审阅与确认计划

76639于19:20:23—20:13:24完成，53:01、COMPLETED/0:0，anode17、32CPU/128GiB/16worker，stderr空。8张map及2pairs齐备，终态`candidate_supported_requires_review`，counter19/new0。旧Slurm ID已经过期，watcher捕捉到完整终态，非SSH故障。

Mac新审计`operations/review_common_step20.py`一次通过3087文件SHA、304反馈与608map进程回执。逐块加热替换/汇总、parent/half归层、频率所有权、完整态/能量账本/正气体热能/响应编码与三范数、原16门/基态四组合、x19/r19/alpha1/128/种子链/trust均核验。没有把上一轮的失败集合当作本轮预设；pair04各门按实际数据复算。

|反馈对|加热变化|noise|原门|四组合|
|---|---:|---:|---|---|
|pair04|3.432392702729e-4|0.1153912633846|15/16，仅noise失败|通过|
|pair08|1.668440770357e-4|0.04215081392916|16/16|通过|

pair08 final三范数8.167786423625182/0.26171358696364666/2.7046134257644168；相对原r19比0.9805019341823921/0.9748063170440359/0.9981400007647373。四组合最不利0.9807976473542539/0.975311536294605/0.9981758241749997，最差单元改善仅约0.18%，因此不直接接受20，继续新基态和两轮同态确认。

四端点最低gas5.76271746219243e12 erg/g，全部正；pair08 previous/final最低6.043745380685727e12/6.087565859857023e12 erg/g。审计数组全部有限，进程exit0与内存/墙钟门全部通过；最大/proc4039644KiB，map计算累计1051.1735431156121秒，不是整批墙钟。图已查看，低材料索引峰和高索引小尾保留，不解释成未经验证的几何表层/中层。

map4final到8final向量差三范数0.0911498895062219/0.005186556857382897/0.037890864237396925只是有限间隔漂移，不是严格误差界。Mac复算原始反馈代数、账本恒等式与响应编码/范数，未重求物质ODE或大型辐射态。跨CPU decoder沿用8eps，raw文件和encoded身份精确；科学门未放宽，第4张失败不追认。

归档`outputs/review-20260924/complete-1790251986297386087.tar.gz`，149414672bytes，SHA256 `cc14876aa0cd70f35927895c56f0fd1e01c5209d8ea57a4bb1d668acf3a6f5ca`；解包`common-step20-76639-received`。新inputs明确是x19/r19，不误用76509的x18/r18。证据`20260924-common-step20-review.json/png`、`20260924-step20-76639-terminal.json`。

下一批协议`common-confirmation-step20-v1.md`：control4maps、confirm1/2各2maps，共最多8maps/3pairs。保持固定候选和r19，任何失败停止，只有两轮确认及Mac独立审计通过才另立接受20记录。预计本批1–2小时只是成本范围；仍未得到可用于整盘观测光谱的自洽大气解。

备份`pre-step20-review.bundle`与`automation-before-step20-review.toml`。新审计/确认驱动/测试另命名，旧代码不改。初始新驱动草稿的机械替换误改了exact_trial的历史导入路径，在逐行diff审阅时已修回`common_step18_backtrack`，尚未测试或部署前即纠正，未产生任何错误科学作业。

本地71项测试通过（0.87秒），覆盖源物质/种子/方向/幅度/时间层身份、零控制禁接受、顺序失败停止、资源与端点保留；shell语法和diff检查通过。Markdown只读检查仍为同样6份历史lecture，日志`confirmation20-markdown-legacy-check.log`保留，未改旧文件、不宣称全库格式通过。

## 确认批次76727已启动

Linux同组71tests通过（15.32秒），学校备份`/home/scc/pb24511938/pre-confirmation20.bundle`。数值提交`0350808fa2cd48f57ab54b5698bda104dd64e33a`已Mac/学校/GitHub一致；GitHub推送再次报HTTP2错误，但ls-remote确认远端实际已更新，未强推或改代理。

76727于21:24:59提交、21:25:00在anode05启动，cpu_long32CPU/128GiB/16worker，4h至2026-09-25 01:25:00。21:25:18快照RUNNING/18秒、preparing、declaration不存在、stderr空，不能据此宣布native预检或map已完成。启动证据`handoff/evidence/20260924-confirmation20-76727-start.json`，counter19/new0。

只读watcher tmux `confirmation20-76727`、18000秒，终态目标`outputs/review-20260924/scheduler-76727/scheduler-terminal.json`；不取消/重交。定时跟进改为监督本批，不再监督已完成76639。整批预计1–2小时只是参考近期成本，任一门失败停止，全部通过仍需Mac独立审计才能接受20。

## 21:59基态对照通过，第一轮确认初始化中

76727仍RUNNING、32CPU/anode05、stderr空，watcher存活。21:59:31快照：control完成4张map，内层残差依次1.133739966789e-5、1.106546353941e-5、1.080130539620e-5、1.054475663197e-5；无active map。父case=confirm1/mapping，但child确切为initializing、history空；不能把父状态说成第一轮map完成。confirm2尚不存在。

control七门全部通过，加热变化1.232469858932e-4；零位移对照未接受为有限物质步。76639pair08相对新control的四组合三范数全收缩，最不利L2/质量加权/最大单元比0.9799286796544463/0.973782550873061/0.9980555606655376，因此允许按既定顺序继续confirm1。

control两端点最低气体热能6.374365797152031e12/6.405896961560273e12 erg/g，0失败单元；各12项完整态检查通过。152反馈进程回执exit0/memory门通过，峰/proc4038924KiB，原生3944.26171875MiB，两态累计worker批墙钟304.911143/307.738313秒。prev三范数8.335819597277/0.268802134697/2.709882628138，final8.337629833981/0.268913127595/2.709940557447，仍有小幅漂移。

这是学校中期读数，未替代终态Mac逐块审阅。原r19和候选均不变，接受数19/new0；不追加map、不改门、不提交新作业。证据`20260924-confirmation20-76727-control-progress.json`；备份`pre-confirmation20-control-progress.bundle`、`automation-before-confirmation20-control-progress.toml`。本轮仅保存小记录，未改运行代码或旧数值工件。
