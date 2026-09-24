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
