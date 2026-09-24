# 半幅仍失败，转向热能与布居方向诊断

76871于00:31:32—01:59:55运行，01:28:23、COMPLETED/0:0，anode18、32CPU/128GiB/16worker、stderr空。control4map及half8map、共3反馈对齐备，终态`half_rejected_requires_direction_review`，counter20/new0。

Mac新审计`operations/review_common_step21_probe.py`一次验证4627文件、456反馈与912map回执；SHA与来源、基态/候选/原方向/物理旧层/种子、逐块formal替换汇总、parent256x16/half128归层与ownership、能量恒等式/响应编码/范数/原门/四组合通过一致性核查。绘图已查看。Mac不重求物质ODE或大辐射场，decode继续8eps、字节身份与科学门不放宽。

归档`outputs/review-20260925/complete-1790272768073337262.tar.gz`，224612626 bytes，SHA256 `1a9b15bbefe8db2bc439dd449f87d8ec3ad71b3d970645962d6986e6f89fef84`；解包`common-step21-probe-76871-received`。证据`20260925-common-step21-probe-review.json/png`、终态`20260925-step21-probe-76871-terminal.json`。

|反馈对|heat|noise|最大单元原分母比|结论|
|---|---:|---:|---:|---|
|control|0.00013499250432116722|零位移不适用|不作有限步接受|7基态门通过|
|half04|0.0002046731518461649|0.17176039801120008|1.002537243327801|噪声和最大单元失败|
|half08|0.00013788486338433853|0.08150638450108187|1.002428929923715|仅最大单元失败|

half08 final三范数8.107841588151302/0.2593987289833129/2.7115713747676473；对原r20的L2/质量加权比0.9921481989419091/0.9904101123965965均改善。对新control四组合最大单元均>1，最不利1.002350582968345。6端点gas均正，最低6.146934199112307e12 erg/g；全部数组有限、进程exit0/资源门通过，峰/proc4042748KiB。map累计计算1734.7873872816563秒不是总墙钟01:28:23。

half4→8全场残差向量差三范数0.06322597155843437/0.0035915583946810993/0.024795751439804767；control pair漂移0.014683214545910844/0.0008417965829416005/0.004505276276309559。均非严格误差界。

## 两幅度的证据

新工具`operations/analyze_step21_amplitudes.py`从两份已审归档逐个核响应NPZ的SHA，生成`20260925-step21-amplitude-comparison.json/csv/png`。图已查看，均以本次新control final为共同对照，固定索引1/2比较，不混用最大值位置。

单元1的HeIII/HeI对数残差，control约0.92919246，完整1/128为1.05289916，半幅1/256为0.99017751；增加0.12370670/0.06098505。热能残差对应变化-0.03177785/-0.01573396，两个幅度呈近似比例，但未建立严格导数收敛。原最大单元2在半幅时近乎不动，单元1却上升并超过它；继续只缩幅缺少推动整体收敛的证据。

## 下一批

不接受21、不重交旧半幅、不再试1/512。新协议`common-step21-directions-v1.md`将r20拆为全部128层的热能方向与布居方向，各以1/256扰动接受态x20。仅改变试探位移，所有物理过程和四残差分量继续完整求解。

新基态对照4map通过后，两方向从相同control后继各自起跑8map/2pairs；合计最多20map/5pairs、4h、32CPU/128GiB/16worker，预计2–3小时只是批次成本。布居方向固定气体热能编码，电子数变化下温度由codec重新解码，不错误冻结温度。原r20分母、物理旧层、dt和所有门不变。原pair evaluator结果保留；即使某方向过门，外层仍diagnostic_only、promoted=False，不自动接受。物理域/资源/代码失败立即停。

完成后比较方向响应及两方向相加相对完整半幅的差异，结合基态/内层漂移判定是否足以构造新方向；不把有限差商叫作完整Jacobian。若数值噪声未解决就保留该限制，不伪造改进方向。

编辑前备份`pre-probe-final-audit.bundle`与`automation-before-probe-final-audit.toml`。旧数值代码、协议、大态均不改不删。当前仍仅20个正式接受的有限非线性步，耦合柱/径向相位表/整盘涌现强度尚未完成。

Mac124tests通过（0.95秒），覆盖两投影在全单元的分解、原方向分母/物理时间保持、布居方向固定热能而非温度、错误幅度/方向/解码/来源与条件停止。首轮一项越界测试输入只造成约48%温升，未超过50%门，程序正确未拒绝；修正测试为明确越界后全过，数值阈值/物理核未改。shell语法与diff检查通过；历史讲义未改、未宣称全库格式通过。

首次暂存后diff检查发现CSV默认CRLF被识别为行尾空白；已显式设CSV writer使用LF并转换这份CSV，数值未变，部署前再次核diff。

## 方向批次启动

Linux124tests通过（16.23秒），shell与跨两个新提交diff检查通过。数值提交`9e548db66c7ba4d8e13f848398d1a0aacada9ef1`三端一致后提交；学校备份`/home/scc/pb24511938/pre-step21-directions.bundle`。

作业76905于02:24:48提交、02:24:49在anode18启动，32CPU/128GiB、4h至06:24:49。run `outputs/hpc/common-step21-directions-20260925`，启动证据`20260925-step21-directions-76905-start.json`；初始preparing且stderr空，不据此宣称native预检或map完成。watcher tmux `step21-directions-76905`，18000秒，终态目标`outputs/review-20260925/scheduler-76905/scheduler-terminal.json`。
