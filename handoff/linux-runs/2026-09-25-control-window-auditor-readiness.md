# 77264：首个窗口前的审计工具准备

## 现场证据

2026-09-25 18:31:37，77264 RUNNING 00:43:13，32CPU/anode04；8张map完成，active_map=None，stderr0。
root status仍是mapping/completed_maps7，因为第8张后的端点保留/协议准备尚未写下一阶段状态。
没有完整pair08或归档，不据此宣布反馈稳定，也不把root文字状态当作停止证据。
完整history快照在`handoff/evidence/20260925-control-windows-8map-progress.json`。

本次不提交新数值作业、不改77264预算或科学门。活跃operations/src/scripts/diagnostics/协议/tests均未动。

## 新审计入口与实际通过范围

新增`handoff/audit_tools/review_step21_control_windows.py`及同目录`test_control_window_review.py`。
14个新解析/负路径测试加6个生产窗口回归，共20 passed（1.05秒）。

独立窗口实现从完整向量按层计算平方和，用math.fsum汇总，再计算L2/质量加权/最大层范数。
不导入生产window_comparison，也不将标量范数之差当向量差。覆盖4种端点组合，固定原r20分母。
负路径覆盖缺端点、NaN、零质量、零分母、伪造通过、修改比值、seed改变、预算/节奏改变、promotion/rebase以及未列清单文件。

已将新工具的反馈核验部分用于旧77126/control pair03：152条反馈回执、块替换/汇总、9632频率归属、
4096→256→128归层、残差编码/范数、7个零控制门均复核通过。
另把旧布居与物理旧层逐位对齐，并从物理旧温度/布居代数计算总能，核对账本旧能量锚。
这里复用了原能量定义和编码器，没有重新积分物质ODE或大型场，不能称独立微物理求解。

独立重算76957→77126控制窗口，比值与既有预检相符；最坏质量加权向量差/原r20质量范数
为0.018841006608752625。它是旧两批的数值，不是新77264窗口结果。
记录`handoff/evidence/20260925-control-window-auditor-legacy-replay.json`。
新归档收取、声明/种子、8/16端点和root汇总整条流程尚未有新工件端到端验证，明确标记未完成。

## 下一次可直接执行的入口

取得并校验pair08或complete包和对应receipt后，用新的received目录，执行：

```bash
PYTHONPATH="$PWD:$PWD/src:$PWD/scripts" MPLBACKEND=Agg .venv/bin/python \
 handoff/audit_tools/review_step21_control_windows.py \
 --archive outputs/review-20260925/实际包名.tar.gz \
 --receipt outputs/review-20260925/实际包名-receipt.json \
 --received outputs/review-20260925/step21-control-windows-77264-pair08-received \
 --reference outputs/review-20260925/common-step21-76808-received/inputs \
 --physical-old outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz \
 --prior-confirmed outputs/review-20260924/common-confirmation20-76727-received/confirm2 \
 --prior-control outputs/review-20260925/step21-positive-validation-77126-complete-received \
 --output handoff/evidence/20260925-control-windows-pair08-review
```

complete包应使用另一个received目录和输出前缀。入口支持已完成且原7门通过的pair08、pair08+pair16归档；
若出现中断/物理失败包，需按失败阶段做专项审计，不能去掉成功断言硬套。
独立核原门与源77126一致、无promotion/rebase、固定trial/物理旧层/r20、map频率覆盖/弱尾自身尺度变化/回执资源，
逐对比窗口decision与root summary。结果JSON与PNG都要查看；独立范数复算比较容差1e-12沿用原审计尺度，科学判决仍用严格1e-3。

PRE-RUN：输入/结构/单位/来源已查，窗口新实现独立；保留物理门与复核边界。RUN。
POST-RUN：20测试与旧真实反馈回放通过，无warning/NaN/Inf/域或资源错误；无新物理解或新窗口判决。
备份Mac `outputs/review-20260925/pre-control-window-auditor.bundle`与`automation-before-control-window-auditor.toml`；
学校`/home/scc/pb24511938/pre-control-window-auditor.bundle`。新文件仅handoff审计范围，不被正在运行的数值代码导入。

Claude讲义草稿已核对并追加第16节：其“独立求解保证结论不依赖工件是否正确”的表述过强，
改为独立求解仍须检验共享方程/初值/离散化与物理假设。仅窗口归约独立实现；反馈核验仍复用已有编码器、能量定义和state_checks，未宣称整条微物理实现独立。
