# 77126：control首张真实映射的独立审计

## 结论与边界

control首张真实map通过原验证检查；thermal仍初始化，population尚未初始化，本轮无物质反馈结论。
15:41:13快照：77126 RUNNING 51:45、32CPU/anode04、stderr0，control history1/active=None。
原条件批次按协议继续，不追加任务、不改门、接受步数仍20。

Mac取回`control-validation-1790321671820796475.tar.gz`，2,750,098字节，SHA256：
`94656dc44dfd521bddff3fea0bac385aa7d5b055cd4b3eb68973590c94fc82c5`。
解包到`outputs/review-20260925/step21-positive-validation-77126-control-received`。
77102已核归档另解包到`outputs/review-20260925/step21-positive-plane-77102-received`。

`handoff/audit_tools/review_step21_positive_plane_maps.py`仅增加显式`--cases control`入口，原检查不变，输出记录审计范围。
真实归档端到端通过168文件、684代码哈希声明、76进程回执、602片全场极值重新聚合及原门复算。
已查看`handoff/evidence/20260925-positive-validation-control-review.png`；JSON同名前缀。
Mac没有重算大型场，也没有重算其全场L2平方和；该部分仍是运行端记录。

| 指标 | 实测 |
|---|---:|
| global残差 | 4.9937817096107006e-6 |
| 与旧control残差比 | 0.9804588686808425 |
| 边界谱L1 | 3.773778449305713e-6 |
| 边界bolometric | 2.6946363478745092e-6 |
| 最大预测误差/全场强度尺度 | 9.698960299799072e-15 |
| 最大预测误差/最大真实变化 | 1.9422075020085704e-9 |
| 最差slab预测误差/自身尺度 | 0.008552997290154296 |
| 最差slab自身映射变化 | 0.16868755395937454 |
| 最差block74自身相对变化 | 0.15989095169793915 |
| 真实map墙钟 | 206.4135620445013秒 |
| 最大worker进程RSS | 3520640 KiB |

最差slab为频率索引[9488,9504)，尺度3.618032768489e-310，最大预测误差3.09450244646e-312。
全场尺度0.03863303480258114。全局和局部采用不同归一化；不能由全局小误差推出每个单元的误差都小。
没有负值修补、弱尾删除或对舍入来源的确证。未证明物质残差收缩、自洽柱或整盘强度已完成。

## 时间与资源解释

提交14:49:28，到declaration落盘15:18:49为29分21秒，属于输入准备阶段；没有把这段时间逐项分摊给哈希和I/O的计时证据。
control候选落盘15:19:29，初始化身份记录15:29:06，首map状态落盘15:32:53。
这些时间说明本轮主要额外开销发生在准备/初始化，不能用42分钟整体墙钟推断单map变慢。
不在运行中改动冻结依赖以优化校验，后续若反复成为瓶颈再单独剖析。

## 前后检查与备份

PRE-RUN：代码只增加范围参数；科学公式、门和独立聚合不变；只审control，禁止冒充三case完成。RUN。
POST-RUN：无warning/NaN/Inf或资源门失败；非负块、频率唯一归属、候选/四态/trial身份通过；弱尾误差已记录，图无遗漏。
真实工件检查不等同Mac重新积分或物理自洽证明。

Mac备份`outputs/review-20260925/pre-positive-control-audit.bundle`、`automation-before-positive-control-audit.toml`；
学校`/home/scc/pb24511938/pre-positive-control-audit.bundle`。运行数值代码、协议、tests及dat均未改。
Claude讲义草稿已独立核查并纠正“684代码断言”为“684代码哈希声明”，且不把准备时间全部归于已精确计时的SHA。
