# 联合系数上限实验 80925 启动记录

2026-09-29 16:41:23 CST 提交，16:41:24 在 anode04 开始。作业80925、run `outputs/hpc/x20-capped-subspace-20260929`，数值代码 `55f70b2ab900bedf912959373fc9742c94e8b989`，已同步Mac、学校、GitHub。

实际资源 Students / qos_stu_cpu_long / 32CPU / 128GiB，16映射worker，3小时硬限至19:41:24。这是本批截止，不是最终科学完成时间。账号其他项目作业不属于本任务，未操作。

## PRE-RUN

```text
[PRE-RUN CHECK]

Code: PASS — Mac 27项回归通过；学校25通过、2跳过（Mac专属接收工件），小型完整仿射场与70位十进制独立KKT对照通过。shell语法与Python编译通过。
Logic: PASS — 同一来源Gram，直接联合权重L1上限17与边界等式。先重新全场正性和十门预测，全部通过才各执行一张full/half原映射并核十二门。
Physics: WARNING — 0.7838889仅固定Gram上的代数预测，未证明新全场正性、边界谱或真实算子一致性；没有新反馈或物质收敛证据。

Key Issues:
1. 固定x20、old、phase/dt、网格和原r20，不改能量定义、系数上限或接受门。
2. 单批最多一个提案、四遍全场扫描、两张map、零反馈和零物质步；失败停止。
3. cpu_long32CPU128GiB、16worker、3小时；父/worker<6GiB，不盲重交。

Decision: RUN
```

## 实测启动与监督

16:43:54，scontrol显示RUNNING2分30秒，状态 `two_pass_capped_prediction`，父stderr为空。说明输入核验完成并进入新候选的全场扫描，尚未确认预测门或真实map通过。

学校只读watch为 `handoff/audit_tools/watch_x20_capped.py`，启动PID3735137，输出 `outputs/review-20260925/x20-capped-watch-80925`，预算14400秒；每60秒读状态，阶段变化调用无工具CLI。首份回执 `is_error=false`，实际模型deepseek-v4-flash[1m]。CLI解释不得替代独立审计。作业终态在调用CLI之前保存。

Codex定时“USTC HHe 运行审阅与决策”已更新为每30分钟跟进80925。完成后下载小归档并按新schema核验；健康无变化静默，失联提醒重连，不反复提交、不取消其他项目。

起跑三份证据：`../evidence/20260929-x20-capped-launch.json`、`20260929-x20-capped-watch-start.json`、`20260929-x20-capped-start-check.json`。学校测试日志已复制Mac：`outputs/review-20260925/x20-joint-cap-school-tests.log`（25 passed, 2 skipped in 19.37s）。两端前置备份 `pre-80862-review-20260929.bundle`，Mac定时内容前置备份 `automation-before-80862-review-20260929.toml`。

科学依据见 `2026-09-29-x20-subspace-review-and-joint-cap-plan.md`，协议 `../protocols/x20-capped-subspace-v1.md`。80862旧失败、全部旧物理门和原r20保留；本批尚未做POST-RUN检查，接受数仍20，无自洽耦合柱或整盘I_nu。
