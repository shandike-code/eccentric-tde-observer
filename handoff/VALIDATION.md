# 本机交接验证，2026-09-14

验证平台是 Apple M4 / macOS / Python 3.12；没有把本机验证冒充学校 Linux 或 Slurm 已完成运行。

- `bash -n hpc/submit.sh hpc/job.sbatch` 通过。
- `hpc/smoke.py`：124 passed，2.41 s。覆盖明确列出的物理组件控制，以及交接恢复、
  残差定义、频率归属、双态门槛、已提交块续跑/损坏检测和停止信号。
- 把 Git 待提交文件复制到没有历史 `outputs/` 的新目录；只恢复 runtime 包，
  完成 10867 个成员的压缩包与逐文件 SHA 校验、cold 配置准备。
- 同一干净副本运行 smoke：124 passed，2.37 s。
- 同一干净副本实际运行 `hpc/check_block.py --local-validation`：初始化一个
  `128 × 32 × 4096` 块，新旧辐射 worker **逐位一致**，最大差为 0。
  新 worker 耗时约 5.37 s、峰值 RSS 2449 MiB；H/He 反馈 worker 约 6.18 s、2955 MiB，
  输出数值有限。详见 `clean_runtime_block_validation.json`。

单块测试使用其余频率块为零的合成稀疏输入；它验证入口与原物理核的连接，不能证明完整柱
收敛、全频反馈闭合、物质试步通过或 Linux 性能。`--local-validation` 只允许开发 Mac 的
这个有界单块检查；学校 Linux 使用 `bash hpc/submit.sh block-check`。

单块检查的协议包含合成重复端点，未调用完整反馈对验收。其 `feedback_protocol.json`
仅是测试夹具，不能作为生产双态收敛证据，也不能交给 pipeline 续跑。

本轮较早对原项目做的全历史测试是 1118 passed、13 failed（81.81 s）：11 个旧讲义路径，
1 个 Markdown 规范测试，1 个检查点库存数量过期。新增交接测试后未将这次旧计数重新包装成
“全套通过”；也没有为使测试通过而修改原数值源码、冻结 phase runner 或历史结果。

Git 提交不含 `.venv`、大辐射态、计算输出或凭据。发布包保留必要输入与可选历史小型结果；
每个包的精确大小和 SHA 由 `runtime_bundle.json` / `artifact_bundle.json` 给出。

尚需学校端执行：资源/依赖验证、单块迁移控制、一次完整 76 块映射 benchmark、真实作业
中断续跑，以及完整双态 H/He 反馈和当前物质候选判定。其后的科学里程碑见 `AGENT_TASKS_ZH.md`。
