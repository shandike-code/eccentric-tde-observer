# 三方向边界约束实验：80862 启动记录

2026-09-29 15:52:21 CST 提交，15:52:22 在 anode16 启动。作业 80862，run `outputs/hpc/x20-boundary-subspace-20260929`，数值代码 `463da2af06e7334b15962d7bd2ec4ed81c880952`。Mac、学校和 GitHub 已同步此提交。资源实际为 Students / qos_stu_cpu_long / 32 CPU / 128 GiB，16 个映射 worker；3 小时硬限至 18:52:22，不是完成时间预估。

上一批结果与新实验的推导见 `2026-09-29-x20-operator-results-and-subspace-plan.md`，精确执行约定见 `../protocols/x20-boundary-subspace-v1.md`。本次先三遍完整场扫描；所有预测门通过才写 full/half 候选，并各运行一张完整映射，最后做真实全场验证。最多一个提案、五遍场扫描、两张 map，零反馈、零新物质步。固定 x20 / old / phase1367 / dt / r20；任何失败都不自动换系数或扩预算。

## 起跑依据

```text
[PRE-RUN CHECK]

Code: PASS — Mac 22 项测试通过；学校 21 通过、1 跳过，后者明确依赖仅 Mac 接收的小工件。检查六个来源态、统一系数、全场正性、完整 76 块映射和进程内存守卫；shell 语法通过。
Logic: PASS — 来源已审计；候选与预测共享同一组仿射权重；预测失败即止，全部通过才执行真实 full/half，并判 12 门。
Physics: WARNING — 已测中点只支持旧历史连线的一致性，不证明新三方向子空间；净出射边界迭代变化等式不是物理总能量平衡。

Key Issues:
1. 不接受物质步，不迁移 r20，不更改物理时间步或能量定义。
2. 保留原正性、有限性、辐射、边界与资源门；无 floor/clip 或删频层。
3. 32 CPU / 128 GiB / 16 worker，3 小时有界实验，不盲重交。

Decision: RUN
```

学校测试日志 `outputs/review-20260925/x20-subspace-school-tests.log` 已复制到 Mac，结果 `21 passed, 1 skipped in 17.65s`。Mac 的 `x20-subspace-tests.log` 为 `22 passed in 0.83s`。测试包括小型解析仿射算子的三遍扫描闭环以及真实错误拒绝，未在登录节点启动转移计算。

## 已观察到的启动状态

15:53:05 实查 RUNNING，运行 43 秒，`status=preparing`，父 stderr 为空。此时尚未确认任何候选或 map 完成；初始化会完整核验大输入 SHA，不能用暂无映射或低 RSS 推断卡死。

学校只读监督由 `handoff/audit_tools/watch_x20_subspace.py` 执行，启动 PID 3077807，输出 `outputs/review-20260925/x20-subspace-watch-80862`，最长四小时，每 60 秒读状态，阶段变化时调用无工具的 `claude -p`。首份回执 `is_error=false`，实际模型 `deepseek-v4-flash[1m]`。CLI 的解释需独立核验，不能代替原始指标。Slurm 终态先保存，再调用 CLI，避免 accounting 过期。

Codex 原有“USTC HHe 运行审阅与决策”已更新为每 30 分钟跟进 80862：完成后接收小归档并按新 schema 复核，健康无变化保持安静；SSH 失联则提醒重连并暂停重复探测。不下载大 `.dat`，不重复提交，不改运行中数值依赖。

提交回执、监督启动、实时启动检查分别在 `../evidence/20260929-x20-subspace-launch.json`、`20260929-x20-subspace-watch-start.json`、`20260929-x20-subspace-start-check.json`。两端代码前置备份 `outputs/review-20260925/pre-80823-80826-review-20260929.bundle`；Mac 定时任务更新前备份 `automation-before-operator-results-20260929.toml` 和 `automation-before-subspace-80862-20260929.toml`。

这里只完成启动检查，尚未进行本作业 POST-RUN。接受数仍为 20；未获得收敛耦合柱或整盘可用的 I_nu。
