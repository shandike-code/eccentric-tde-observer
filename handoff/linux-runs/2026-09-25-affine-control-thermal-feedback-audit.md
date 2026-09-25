# 76957中期反馈审计：control稳定，thermal仍拒绝

本报告审计control和thermal两个完成的反馈对。人口布居候选population的反馈尚未纳入此快照，不预判其通过或失败；整批76957及最终源哈希复验还未宣告完成。正式接受数仍20。

## 工件和可复算边界

归档`thermal-feedback-1790306543699693228.tar.gz`，152442522字节，SHA256 `2fc9bcc72ecf107cff21e3415116f955a9a31db7e7114b6f285c87ba726320c6`。Mac路径`outputs/review-20260925/`，解包`step21-affine-76957-thermal-feedback-received`。

新独立脚本`handoff/audit_tools/review_step21_affine_feedback.py`适配本批3map/pair03，支持明确标为中期的已完成pair快照，未把它冒充最终summary。核2950文件SHA、680冻结代码声明、304反馈进程及532map进程回执。这份快照包含control/thermal各3map和population首map，共7map，不代表当前实时进度停在7。

复核范围包括：固定trial与76931字节相同；原x20/r20/物理旧层/密度/dt；原子的逐块输出与common formal替换逐位对应；9632频率ownership及完整块和；parent256×16和half128归层；各端点能量账本与响应能量恒等式；全部四编码残差、原门和新control四组合；trial trust region、内层残差/边界门和进程资源。跨CPU解码仍仅8个机器epsilon容差，不更改任何科学门。Mac没有重新积分物质ODE或读取大型辐射态。

证据`handoff/evidence/20260925-step21-affine-first-two-feedback-review.json/png`，图已查看。所有四个反馈端点气体热能为正，最低7.002907937070961e12erg/g；最大/proc4044636KiB，未见非有限数组、非正物质响应或资源门失败。

## 判定

| 指标 | control final | thermal final |
|---|---:|---:|
| 残差L2 | 8.2219343082 | 8.1515759758 |
| 质量加权残差 | 0.2658904867 | 0.2630879464 |
| 最大单元残差 | 2.7058661291 | 2.7139609887 |
| 相邻加热指标 | 0.0001727456 | 0.0001762732 |

control零位移稳定性门通过，只允许继续比较候选，不是接受一个新的物质步。

thermal相对原r20的三残差比为0.9974999308、1.0044959110、1.0033123358，原16门中质量加权和最大单元门失败。其内层噪声比0.0152099700小于0.1，加热门也通过，但这些不能抵消收缩门失败。对新的control做四种端点组合，最大单元比最坏1.0030029349，同样失败。因此无论保留原参考还是检查新控制，thermal都不能接受。

## 相邻稳定与历史漂移不能混同

物质trial完全相同的control，本次final与旧r20的向量差L2=0.5135387635；本次final与previous仅差0.0066071731。后一数值是相邻端点跨度，前者是不同辐射精度历史下的响应变化；两者都不是已建立的真值误差界，不能据此宣称发散或全误差已知。

与76931末端相比，同一control和thermal的响应L2变化分别0.3092373480、0.2387878930。辐射外推确实改变了物质反馈的评估结果，所以不能只用相邻加热门或原noise通过来保证方向可靠。原r20比较和当前control比较继续同时保留，不能选一个更有利的分母替换原判定。

## 当前决策

允许76957按已冻结的条件预算完成population反馈和最终源身份复验。没有额外提交、没有改活跃数值依赖、没有刷新接受数。全批最多9map/3pair，物理dt、原子核、所有原科学门不变。完整工件落地后再决定下一阶段，不能从thermal单方向失败推断模型无自洽解。

本地备份`outputs/review-20260925/pre-affine-feedback-audit.bundle`、`automation-before-affine-feedback-audit.toml`。审计工具在`handoff/audit_tools/`，不由作业导入。首次运行的`--prior-confirmed`漏写`confirm2`子目录，按真实目录修正后全量重跑；另修复新元数据字段引用了绘图同名变量的问题，重跑并断言审计case恰为control/thermal。两者未改动平台数值结果。Markdown检查不批量改历史六份讲义。

11:41:22实时进度：9/9张map均完成，无active半态；control和thermal两个反馈对均完成，population的previous为76/76块完成、final为64/76块，stderr空，watcher活。快照`handoff/evidence/20260925-step21-affine-first-two-feedback-progress.json`。这与审计归档的历史快照范围分开记录。
