# 82273首窗口在途巡检与独立审计准备

2026-09-30 20:48:40 CST快照：作业RUNNING，accelerated完成7张完整map，第8张active；historical尚未起跑，无已归档反馈对。stderr空。没有终态、物质反馈通过或校准资格的结论。

证据`handoff/evidence/20260930-x20-82273-first-window-progress.json`保存原scontrol、status、7条history及资源核对。完整map共532份process回执，正好7×76；0坏回执，maxworker3590752KiB<6GiB。config/trial SHA一致，native_mirrored_material_exact与physical_phase_and_dt_exact均真。map1残差2.838279287643072e-7，map7为2.7664443960806804e-7；该量是辐射映射缺陷，不是物质耦合残差或严格真解误差，不能由其很小推断反馈已稳定。

新工具`handoff/audit_tools/review_x20_window_feedback.py`以不可覆盖归档为输入，可审首对、两个/三个窗口及完整终态；不会直接读取远端正在写的run。它重新绑定82214真实full输出与81769 H16、inputs/trial、accepted20原r20、80195冻结信号，不沿用81769工具的80554 H24和source-preflight路径。重算完整512维响应差、所有四端点组合、频率归属、边界稳定归约及原反馈门。原反馈率核明确复用；Mac不重新积分物质ODE或辐射大场。

## 审计工具范围

部分工件返回reference_calibration_eligible=null；只有4对齐备、真实终态且两支16−8与cross16均通过才能给最终资格。工具不会因首对通过填true。硬物理域/原反馈门失败会明确拒绝成功审计并要求单独失败分析；这不是把失败归档丢掉，也不是已实现全部故障诊断。完全零差向量的定位份额返回null，不加floor。

9项新测试通过（首对不能冒充终态、缺失中间窗口、三类硬失败、窗口/cross率拒绝、零差与非法数组、真实源trial、旧job/放宽门/预算/换基准拒绝）。与4项82214审计测试合计13项曾分别运行通过。尚未在82273实际反馈归档上运行，所以不称“反馈已独立审计”。

待不可变archive落地后下载三件套`.tar.gz`、`.json`、`-receipt.json`，执行：

```bash
PYTHONPATH=.:src:scripts OPENBLAS_NUM_THREADS=1 .venv/bin/python \
  handoff/audit_tools/review_x20_window_feedback.py \
  --base <不含扩展名的归档basename> \
  --out outputs/review-20260925/x20-feedback-82273-<新里程碑>-received \
  --target handoff/evidence/20260930-x20-82273-<新里程碑>-review.json
```

仅真实终态完整32map4pair时额外传`--terminal handoff/evidence/20260930-x20-82273-terminal.json`。新目录拒绝覆盖，断言失败先查数据/实现，不改科学门。首对及中间快照不传terminal。若源归档首次核验发现引用/路径问题，仅修审计工具并保留失败接收目录，不能修运行中冻结源码或篡改来源。

本次没有提交新Slurm作业、增加预算或修改冻结数值文件。Mac先做pre-82273-first-window-review-20260930.bundle及automation-before-82273-first-window-review-20260930.toml备份；新工具、测试与小快照入Git。继续已授权82273，后续有界决策须等反馈证据。
