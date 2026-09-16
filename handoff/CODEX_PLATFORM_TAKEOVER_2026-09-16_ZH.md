# 2026-09-16：Codex 接管平台决策，Claude Code 监督

用户已授权 Codex 经 `pb24511938@107.ustc.edu.cn` 调试、决定下一步和提交计算；平台 Claude Code 负责监督。密码与动态密码由用户在 Mac Terminal 输入，连接复用不保存这两种凭据。

## 接管时实测

- 登录节点 `tradmin-02`，项目 `/home/scc/pb24511938/eccentric-tde-observer`，学校提交 `d628dd9`，工作树干净。已将学校提交经 SSH 拉回 Mac 诊断分支，保留全部合并历史。
- 现有科学 run `outputs/hpc/hhe-r025-cont64`，2 workers / 4 CPU / 16G，独立监督器 PID 2083668。接管时 map59 已提交，map60 正在作业 64391 运行。保留该监督器的唯一提交权，不重复起跑。
- 新版本信号恢复报告已落地：2bec4d9 下作业 63687/63691，22 个已提交块恢复前后 SHA 相同、mtime 无变化。
- `sacctmgr show assoc` 仍只列默认 QOS，但实际 `sbatch --test-only --partition=Students --qos=qos_stu_cpu_long --cpus-per-task=8 --mem=52G --time=02:00:00 --wrap=true` 已通过。以实际提交预检为权限证据；预估开跑时间不是保证。
- `qos_stu_cpu_long` 查得 `MaxWall=3-00:00:00`，`MaxTRESPerUser=cpu=32,mem=128G,gres/gpu=0`。额度与实际 job allocation 分开记录，未申请全部额度。

## 科学判断已发生的变化

第 13、14 轮的两个物质响应均已进入正热能域，第 14 轮 previous/final 失败层数都是 0。最差层转为 cell64，剩余气体热能分别约为该层旧气体热能的 1.159% / 1.381%。此前“负热能始终未消失”的状态不再适用于新端点。

第 14 轮正式指标：

| 指标 | 值 |
| --- | --- |
| atomic heating 相邻变化 | 0.003409950337291241（门 0.001，未过） |
| inner noise / trial signal | 0.017843802854908133（门 0.1，通过） |
| candidate/base L2 residual | 1.1432662362898658 |
| candidate/base mass weighted residual | 2.2013061818789743 |
| candidate/base maximum cell residual | 1.23246641591141 |

三种物质残差均未收缩。加热稳定性尚未通过，所以这些残差不能被当作已经排除了全部内层误差的最终判决；但也没有依据承诺继续堆 map 就会接受候选。现有 64 张预算完成后必须审阅，不自动追加同样的 64/128 张。

## 当前执行决策

1. 保留现有科学 run 和提交器，让其按既定 64 张/16 轮预算完成；故障或接受即停，不更改冻结配置、物理 dt、阈值或旧结果。
2. 在独立 `cpu_long` allocation 内比较同一冻结种子下 2、4、8 workers，各完整 76 块 map 一次。申请 8 CPU / 52G / 2h；不因为方案允许 72h 就占满 72h。
3. 种子使用已终止的 `hhe-diag-r025`，其最终 SHA 为 `eb4c30283322c41ca130db9f6efa1234de0349945e057869e032dd9e736d26a8`。每组拥有独立三态，不写种子、不混入科学预算。哈希校验、初始化和计算均在 allocation 内运行。
4. 比较完整输出 SHA、RSS、map 墙钟、包含初始化的总墙钟。同机同输入只改变 worker 数时输出差异需要调查；本测试要求逐位相同，不以变化的指标掩饰差异。一次顺序比较有缓存和顺序偏差，只作为初筛，不能证明全程线性加速。
5. 最终并发数和后续科学候选由 Codex 根据实测决定。当前没有授权监督程序自动扩额、自动回溯或修改算子；代码与科学判断仍由 Codex 执行。

## 新增运行入口

`operations/` 独立于被现有 run 冻结的 `diagnostics/*.py|*.sbatch`、`src/`、`scripts/` 和 `hpc/`，不改变其文件字节。

```bash
TDE_BENCHMARK_RUN=outputs/hpc/cpu-scaling-20260916 \
TDE_BENCHMARK_TEMPLATE=outputs/hpc/hhe-diag-r025 \
TDE_BENCHMARK_SEED_RUN=outputs/hpc/hhe-diag-r025 \
sbatch --parsable operations/cpu_scaling.sbatch
```

只提交一次；再次执行前检查队列和目标目录，已有目录会拒绝覆盖。性能试验如中断/失败保留数据并交 Codex 处理，不自动重复三组计算。

轻量监督用 `operations/claude_watch.py`，运行在登录节点的独立 tmux 会话；每 60 秒读取 JSON 与 Slurm 状态。只在新增反馈轮次、终态、性能结果、失败或科学进展停滞一小时后调用模型，不对每块/每张 map 调用。队列等待和科学停滞须由状态区分解释。两项任务结束后监督器退出并明确要求 Codex 审阅；最长监督 24h。

Claude Code 通过 `-p --tools "" --no-session-persistence --output-format json` 读取有界状态快照，无工具执行权。现有配置的实际模型返回为 **deepseek-v4-flash[1m]**；这里的 Claude Code 是 CLI 名称，不代表 Anthropic Claude 模型。未改动用户模型或认证配置。报告保留实际模型名、费用和时间；不输出凭据。

监督输出含 `watch.json`（健康与终态）、`latest.json`（真实状态）、`latest_review.md`（最新模型解读）及各次 JSON 报告。模型意见不替代原始科学门或 Slurm 状态；API/程序失败会明确记为 `watch_failed`，不会伪称仍在监督。

## 验证

Mac 当前 70 项相关测试通过：原合并后的 62 项与新增 8 项监督事件/性能一致性测试；sbatch shell 语法检查通过。性能实测必须等新 Slurm allocation 的结果，不能把这些测试写成已测出加速。
