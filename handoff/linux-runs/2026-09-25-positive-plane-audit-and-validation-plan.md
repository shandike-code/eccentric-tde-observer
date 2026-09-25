# 77102独立复核与32核真实验证计划

## 已完成的证据

77102在anode04运行14:00:15—14:10:51，用时10分36秒，4CPU/16GiB，COMPLETED、ExitCode0:0、stderr0字节。
小归档`complete-1790316648108354528.tar.gz`为1,076,531字节，SHA256：
`492dfc12993113c06e179ca88cd8dd92d8bb93f5c1b229a7ee6ba8a00fa9d89a`。
Mac审计6个文件、683代码声明，复算每个约束的原始hex正规化、每轮优化器重放及602片全场指标汇总。
审计JSON/PNG为`handoff/evidence/20260925-positive-plane-review.*`；图已查看。

| case | 全场轮次 | 最终收集约束 | 最终负点 | 预测残差/旧残差 |
|---|---:|---:|---:|---:|
| control | 3 | 40 | 0 | 0.980458868751369 |
| thermal | 3 | 18 | 0 | 0.9725097569529314 |
| population | 2 | 22 | 0 | 0.975764149996243 |

三者的正性、系数L1/和、严格内部残差、最大范数改善、边界谱和总通量门都通过。
添加约束后最优可选集合缩小，预测改善减弱，最终才消除了全部负点；不能只挑第一轮看起来更快的结果。
没有新map、反馈或物质接受；接受步数20。共用优化器重放不是独立优化算法验证，Mac未重积分大场，有限搜索也不证明全场最优。

## 下一实验及选择依据

新增`operations/validate_step21_positive_plane.py/.sbatch`及独立协议`handoff/protocols/step21-positive-plane-validation-v1.md`。
既然三个预测通过，值得用真实映射检验；不再在系数平面盲扫，也不运行被拒绝的旧候选。
32CPU/128GiB、16worker、5小时硬上限；最多9张map/3反馈对，3case先各1张验证，然后control先行，候选条件反馈。
原trial、$x_{20}$、$r_{20}$、物理旧层与dt不变，任意负值不修补，保持原16门。
新目录`outputs/hpc/step21-positive-plane-validation-20260925`。没有自动promotion或自动续交。

## 代码与真实工件检查

Mac52项测试通过（0.71秒），包含18项新测试：输入身份、系数、精确候选公式、真实映射偏差、负预测、候选篡改、停止、上限和归档来源被替换。
初次1项失败来自测试临时目录在仓库外，修正测试的ROOT隔离后通过；不是放松生产路径检查。
Shell语法、py_compile检查通过。真实小工件核对三个case的四态链及编码/方向/残差身份通过。
Mac直接调用Linux原生逐位解码检查时温度失败；这与已有跨CPU指数差异一致。没有修改运行时的逐位检查。
Mac按既有8eps尺度复核解码通过，Linux起跑前仍要求本机逐位身份检查通过。没有据此修改物理门。

[PRE-RUN CHECK]

Code: PASS — 四态普通流式读取、原float64差分顺序、候选逐位回查；新目录/partial发布、信号传播和三map上限有测试。
Logic: PASS — 77102审计到76957四态，再到新候选、真实map和反馈；先复制trial再初始化；原控制与新控制并存。
Physics: WARNING — 仿射预测仍须真实T检验；2%至3%内部残差改善并不保证物质残差改善。

Key Issues:
1. 弱尾不删，所有点零容忍负值。
2. 同一固定物质的多个辐射态不代表多个接受物质态。
3. 总项目完成时间未得到验证，本批次只承诺有界执行。

Decision: RUN — Linux测试与真实小工件身份核验通过、三端Git一致后提交。

## 备份

Mac：`outputs/review-20260925/pre-positive-plane-review.bundle`和`automation-before-positive-plane-review.toml`。
学校：`/home/scc/pb24511938/pre-positive-plane-review.bundle`。旧77102/76957目录、协议、dat均未改。

## 已起跑77126

2026-09-25 14:49:28提交并启动，anode04，`qos_stu_cpu_long`，32CPU/128GiB，硬上限19:49:28。
数值代码`d08c32dffdaa036585ef6bbe8f9e1bb35fdf9e0b`。Linux52tests通过（20.53秒），三个真实trial本机逐位解码与四态身份检查全通过。
提交前三端代码一致且clean。14:50:18快照仍在准备校验、stderr0；尚未声称完成新map。
watcher为tmux `step21-posval-77126`，21600秒，终态写入`outputs/review-20260925/scheduler-77126/scheduler-terminal.json`。

新增Mac入口`handoff/audit_tools/review_step21_positive_plane_maps.py`，用于三case首张真实map归档的独立聚合。
对应完整三反馈对入口`handoff/audit_tools/review_step21_positive_plane_feedback.py`复用已有已验证的逐块率/加热/物质账本审计逻辑，
改为新四态血缘及76957基准。两个入口尚未在本轮真实新工件上端到端运行，不能预称通过。
若批次因control、映射或物理域失败提前停止，应按实际产物做部分审计，不能删掉完整审计器断言强行套成六端点成功。
审计工具不被作业导入，不在当前运行数值代码声明内；只追加它们与报告不会改变运行依赖。
