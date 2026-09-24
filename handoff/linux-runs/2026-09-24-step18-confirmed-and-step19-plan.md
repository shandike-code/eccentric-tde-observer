# 第18步独立接受与第19步有界试探

## 结论与证据

76469（anode17，cpu_long32CPU/128GiB/16worker）于13:30:09—14:49:47完成，COMPLETED/0:0、1:19:38，stderr空。control4map与confirm1/2各2map全部落地，三对反馈共456个worker。Mac新审计`operations/review_common_confirmation18.py`验证4021个文件、456反馈与608map回执，原16门、三范数、新基态四组合、种子/物质身份、逐块代数/归层/所有权、完整态/能量账本/响应编码、资源均复现通过。首次复算完成，无NaN/Inf或运行warning；图已检查，低编号峰与高编号尾部没有删除/裁剪。

接受记录`handoff/evidence/20260924-accepted-step18.json`将已确认有限非线性步从17增到18；接受confirm2/trial_material.npz本身，不把G(x18)当成物质。不改旧run计数，不推进物理时间。耦合柱与整盘I_nu仍未完成。

|端点对|原子加热变化（门1e-3）|内层噪声比（门0.1）|判决|
|---|---:|---:|---|
|control|4.840830518548e-4|零控制不作有限步判决|七门通过|
|confirm1|4.751954201532e-4|0.02788431590746|16门及四组合通过|
|confirm2|3.184973373205e-4|0.02408841823390|16门及四组合通过|

confirm2对本批新control四组合最不利三比：L2 0.973612502299、质量加权0.904119121230、最大单元0.994029750121。六端点最低气体热能6.176483838083e12 erg/g，全部为正。最大/proc4037028KiB，所有原生与独立进程门通过，map计算累计1279.003375秒；它不是总作业墙钟。

confirm1final→confirm2final的L2范数8.501401356257→8.505715711377、mass 0.276022745916→0.276117137480、max 2.720110528726→2.720335486405均略回升。两残差向量之差三范数0.051051629971/0.003544151744/0.015552698161；基态两端点漂移0.026947994698/0.001984151646/0.007983099460。这些是实测有限间隔漂移，不是严格误差界，过门不等于全状态固定点已收敛。

## 归档与复算边界

完整小工件`outputs/review-20260924/complete-1790232561220852887.tar.gz`，223466176bytes，SHA256 e2695168a189031c1b15996c6590c185b49ed20bbe3fb65abda6a2bb2e479b97；解包`common-confirmation18-76469-received`。审计JSON/PNG为`20260924-common-confirmation18-review`，Slurm终态`20260924-confirmation18-76469-terminal.json`。新审计独立复算账本恒等式、响应编码和范数，没有在Mac重求物质ODE或9.41GiB辐射态。跨CPU decode沿用8eps，文件SHA和encoded精确、科学门不放宽。

## 下一批

固定候选x18+r18/128，r18来自本次confirm2final，三范数8.505715711377/0.276117137480/2.720335486405。在新目录最多8maps2pairs，第4/8张分开判定；第19步不自动接受，不减物理dt，不回到已经失败过的1/64大步。详见`handoff/protocols/common-outer-step19-v1.md`。此前confirm1和confirm2通过并不证明新方向的小步必过，必须真实重算。

每步备份：Mac `pre-step18-acceptance-review.bundle`及`automation-before-step18-acceptance-review.toml`；旧文件、旧协议和dat不改。所有新代码、测试、小型审计与说明入Git，数值大态只留学校。预计这次8maps2pairs约一至两小时仅是最近批次耗时参考，不是整体自洽解完成承诺。

## 起跑前验证

新驱动及依赖75项本地测试通过（0.92秒），覆盖接受来源被替换、物理dt被改、非零基态、错误方向/分母、超trust、旧1/64幅度、原native完整态/零控制/保留端点；shell语法和diff检查通过。旧Markdown只读检查仍报告同样6份既有lecture，清单保留在`step19-markdown-legacy-check.log`，未修改历史讲义，不宣称全库格式通过。新审计代码和第19步驱动另建，已冻结文件不改。

## 15:21第19步试探已启动

76509于15:21:55在anode02 RUNNING，cpu_long32CPU128GiB/16worker，4小时至19:21:55；数值代码`8e814e9b20c3fccd87b8660d9048e01cd82f1bc7`。Mac75tests0.92秒、Linux75tests20.14秒，三端SHA一致、工作树干净后提交。启动16秒时status尚未生成、declaration未写、stderr空，只能说进程启动，不能推定native预检或map已完成。真实来源和native预检在allocation内进行。

只读tmux watcher `step19-76509`运行上限5小时，终态写入`outputs/review-20260924/scheduler-76509/scheduler-terminal.json`，不会重交或取消。学校备份`/home/scc/pb24511938/pre-step19.bundle`。起跑证据`handoff/evidence/20260924-step19-76509-start.json`；保持18已接受步、第19步未接受。定时任务继续监督实测资源与第4/8张判决。

## 15:58第一对反馈：仅内层噪声门未过

76509仍RUNNING36:37，stderr空；前4map完成，辐射res依次6.442378168325e-5、3.811557801597e-5、2.319712924674e-5、1.528145872326e-5。pair04原15/16，唯一inner_noise_resolved_pass=False，噪声比0.10712357080956236高于原0.1门，不能因只超约7.1%而圆整成通过。三种heating约3.71905568374e-4，通过；原r18分母三范数比0.981524689053 / 0.975527778648 / 0.996261950182，相对76469confirm2两端点的四组合也全收缩。

两端点最低气体热能5.807187694284e12 / 5.900875275247e12 erg/g，12完整态检查均通过；152反馈进程回执全部exit0/memory guard pass，最大/proc4039544KiB，原生3944.867MiB，每态批墙钟323.1606615 / 339.4780800秒。previous三范数8.371289286090 / 0.270319083510 / 2.711967446085，final为8.348569968784 / 0.269359937772 / 2.710166736835。只是中期学校侧证据，未代替终态Mac独立审计。

父status=mapping/completed_maps4，子active_map5、已提交0块，按既定8map预算继续。不自动加map、改幅度或放宽noise门。小的全局辐射残差不足以保证物质试步信号已与内层反馈变化分开，pair04不支持接受19；计数仍18/new0。备份pre-step19-pair04-progress.bundle与automation-before-step19-pair04-progress.toml，证据20260924-step19-76509-pair04-progress.json。本次无运行代码修改、无新科学作业。
