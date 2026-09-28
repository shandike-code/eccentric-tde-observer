# 79151晚期窗口确认：启动与接续入口

2026-09-28 16:19:02提交79151，16:19:04进入RUNNING/anode18。32CPU、128GiB、16worker、qos_stu_cpu_long；硬限至2026-09-29 00:19:04，不是完成ETA。数值代码`eecd62a487d7a24db80e07044fe26fdcadfd48c6`，运行目录`outputs/hpc/step21-late-direction-windows-20260928`。没有重交旧78950。

本地119tests/2.58s；学校115passed、4skipped/21.15s，跳过项依赖Mac接收目录。学校另用真实原始工件核验三组trial、native消费路径、原接受门/正式态门、配置SHA及各自种子存在/大小，均通过；预检不读大型辐射场。py_compile、bash -n通过。学校预检已取回`handoff/evidence/20260928-late-direction-preflight.json`。

16:24:17实测父status为preparing，但declaration已经生成，control初始化、0完整map、无active_map；thermal/population未创建。这说明prepare内完整源码/输入声明（包括三份大seed）核验已返回，不说明初始化、映射或任何反馈已经完成。父stderr为0字节，不能扩大成全部worker日志无warning。输入父声明含14份不同大文件声明，共116.375GiB；哈希与初始化确实有I/O成本，不能把preparing自动当作停滞或失败。

三份10099884032bytes后继态分别来自78950各自第16张，SHA如下：

- control：`2cb5320984731a38300c43a58ef9c38cd4bf917155ba2fad94bd69af2510e0cb`
- thermal：`e3a4199fcae498992ec6792f82a1577001eb170c1428bd0969f8b38427b8a17f`
- population：`13b1e1ca3e3b7d54aee164a499833b6d51acb88ee24067acf544b3949f2098c9`

执行control8/thermal8/population8，全部晚期门过才执行control16/thermal16/population16。第一项失败即停，不扩预算。相对于78950为第24/32张，物理dt、原r20、物质态和接受门固定，接受20不变。控制历史78594累计漂移仍报告原判决，但新局部实验不以该历史门控制派发；旧8→16失败永久保留。详见`handoff/protocols/step21-late-direction-windows-v1.md`，不能把新窗口通过称为全程稳定。

学校只读监督tmux `step21-late-79151`，入口`handoff/audit_tools/watch_late_direction_windows.py`，输出`outputs/review-20260925/late-direction-watch-79151`。每60秒取轻量快照，CLI仅在RUNNING/反馈里程碑/终态点评，工具禁用。首回执模型deepseek-v4-flash[1m]，其“当前无失败”只应理解为快照尚未报告失败，而非完成所有物理检查。16:22:30实测监督tmux存活。初始快照见`handoff/evidence/20260928-late-direction-initial-observation.json`。

## 下一次独立审计

新入口`handoff/audit_tools/review_late_direction_windows.py`复用已验证逐块/能量/原门审计，三类窗口和两类累计信号独立归约。`test_late_direction_review.py`与原反馈审计测试合计45passed/2.43s，包括真实78950两方向向量再现旧失败、零信号、累计失败、各停止位置及假通过拒绝。仅接口/负例/历史真实输入验证完成；**79151尚无反馈，新工件端到端审计未完成**。

先检查原79151及watch最新状态，已有终态则取`watch/scheduler-terminal.json`。只下载最新里程碑包；若complete已有则不重复中间包。完整审计命令：

```bash
PYTHONPATH=.:src:scripts MPLBACKEND=Agg .venv/bin/python handoff/audit_tools/review_late_direction_windows.py \
  --archive outputs/review-20260925/实际包.tar.gz \
  --receipt outputs/review-20260925/实际包-receipt.json \
  --received outputs/review-20260925/late-direction-79151-实际里程碑-received \
  --source outputs/review-20260925/refreshed-directions-78950-complete-received \
  --historical outputs/review-20260925/stationarity-78594-complete-received \
  --reference outputs/review-20260925/common-step21-76808-received/inputs \
  --physical-old outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz \
  --accepted outputs/review-20260924/common-confirmation20-76727-received/confirm2 \
  --terminal handoff/evidence/79151实际终态.json \
  --output handoff/evidence/新审计前缀
```

部分里程碑不传terminal。工具支持晚期漂移门失败的正常停止及inner-not-ready；物理域/原零位移七门/代码/资源失败会拒绝普通成功审计，须专门分析失败，不删除断言。检查图、所有有限量/尺度/原16门/正gas/RSS，保留原失败。任一早期失败后出现后续工作、预算超限或种子串组都应拒绝。

如两个晚期窗口最终均通过，再审查新的混合方向是否有三范数共同下降证据；另声明候选、真实映射反馈和同态确认，不能自动接受21。若失败，分解候选与控制变化，禁止无限重复同配置。没有自洽大气/整盘I_nu，不给未经验证的完成时间。

Mac备份`pre-refreshed-complete-review-20260928.bundle`，学校备份`pre-late-direction-20260928.bundle`，代码以增量bundle快进；GitHub已验证eecd62a。旧自动化全文备份`automation-before-late-direction-79151.toml`，均在`outputs/review-20260925`。只同步代码/报告/小工件，不传回或删除学校大场。

启动I/O补充：16:29:08仍RUNNING/10:04，control初始化0map。随后只读检查发现control/config.json继承55条>1GiB来源声明，按条目累计517.34375GiB；包含重复来源，不是新增存储占用。native_trial_audit.json已存在，三个工作态尚未创建。结合hpc/pipeline.py的执行顺序，这是进入run_pipeline后、创建工作态前的完整来源哈希阶段。不能据此声称死锁或物理失败。当前源码/配置冻结，不在运行中去重；未来另起版本可评估在保留每条身份断言的前提下避免同一字节重复读取。父stderr仍0，未有首map或新反馈结果。

独立审计与启动记录已同步到Mac/学校/GitHub的62abdc4；定时任务已切换到79151，每30分钟ACTIVE，健康静默、实质变化或需重连通知。这个文档后续补充不改变数值运行eecd62a。
