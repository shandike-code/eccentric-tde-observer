# 交接：小步下降检验（给下一个 agent）

## 0. 一句话现状

"小步下降检验"的科学结论已经拿到并入库：**该方向不可用，必须重做方向**。当前平台上还有三条延续链在跑，目的是把各自的辐射残差推过阶段 B 门槛 $2.5\times10^{-4}$，拿到门槛级收敛下的判决记录（预期仍是"物理域失败"轮次，不会有比值）。三条链跑完即本阶段工作收尾。

## 1. 目录、分支与同步状态

| 位置 | 路径 | 说明 |
|---|---|---|
| Mac 仓库 | `/Users/shandike/Downloads/A_USTCer/8.3/ustc-hpc-diagnostics-review` | 主工作副本 |
| 学校仓库 | `/home/scc/pb24511938/eccentric-tde-observer` | Slurm 侧，分支 `ustc-hpc-diagnostics` |
| GitHub | `shandike-code/eccentric-tde-observer`，分支 `ustc-hpc-diagnostics` | 需在 Mac 上推送 |

同步状态：Mac 与学校已同步到 `a3dac02`；**GitHub 落后**（最后一次成功推送是 `95ae303`），原因见 §6.4。恢复网络后先在 Mac 上 `git push origin ustc-hpc-diagnostics`。

## 2. 当前正在运行的东西（2026-09-18 16:55 核实）

三条 v3 延续链，各 8 worker、cpu_long、墙钟上限 12 小时，由**健壮监督器**驱动（每批 8 张映射，`--max-jobs 3`）：

| run（学校侧） | 对应步长 | 起始 R | 预算 | 当前进度 | 监督器日志 |
|---|---|---|---|---|---|
| `small-step-a15625-cont24-20260918` | $1/8$ | $3.37\times10^{-4}$ | 24 张 | maps 4，R $3.29\times10^{-4}$，1 轮 | `outputs/hpc/logs/<run>-robust-supervise.log` |
| `small-step-a078125-cont24-20260918` | $1/16$ | $3.83\times10^{-4}$ | 24 张 | maps 4，R $3.74\times10^{-4}$，1 轮 | 同上 |
| `small-step-a00390625-cont24-20260918` | $1/32$ | $3.86\times10^{-4}$ | 24 张 | maps 6，R $3.73\times10^{-4}$，1 轮 | 同上 |

另外还有一个 **tmux 会话 `tde-hhe`** 在登录节点常驻：

```
tde-hhe: 2 windows
  window status : TDE_STATUS_INTERVAL=300 bash operations/status_logger.sh
  window shell  : 空闲登录 shell
```

它每 5 分钟把三条链的 `状态/maps/R/轮次/待结算` 与节点负载追加到 `outputs/hpc/logs/tde-status.log`。**这是观测的主入口**，一条 `tail` 就能补齐任何时间段的轨迹。

## 3. 已定论的结论（可直接引用，无需重算）

| 结论 | 证据文件（仓库内） |
|---|---|
| $1/2$ 步候选的编码残差比值稳定在 1.1268（四轮），**不下降** | `handoff/linux-runs/2026-09-17-extension-run-verdict.md`、`handoff/evidence/ustc-baseline-replay-20260917.json` |
| $1/4$、$1/8$、$1/16$、$1/32$ 步的物质响应**全部离开物理域**（43→54→56→56 个单元） | `handoff/linux-runs/2026-09-18-small-step-verdict-not-descending.md`（$1/8$ 的旧判词，**已撤回**）、`.../2026-09-18-domain-failure-worsens-with-convergence.md`、`.../2026-09-18-domain-failure-saturated.md` |
| 失败随辐射收敛**加深并饱和**（缺口 −4.6/−6.0），不是未收敛假象 | 同上 + 图 `lecture/项目讲义/figures/2026-09-18-domain-failure.png` |
| 数值噪声底：三类扰动在 $10^{-14}$ 量级，比值信号比它大 15 个数量级 | `handoff/evidence/ustc-noise-floor-20260917.json` |
| 跨平台重放差异是末位舍入（1 ulp 经 log 放大到 $7.8\times10^{-12}$），不是实现差异 | `handoff/evidence/ustc-baseline-parity-mac-20260917.json` |

**已撤回、不要再引用**：`2026-09-18-small-step-verdict-not-descending.md` 里的 $1/8$ 判词（当时那条链实际跑的是 $1/2$ 步，原因见 §4.1）；`2026-09-18-domain-depth-tracks-R.md` 的结论段（单链推广，已在该文件顶部更正）。

## 4. 三个必须知道的坑（都是工程，不是物理）

### 4.1 候选的身份 = 它的物质态文件

`hpc/pipeline.py::run_pipeline` 在新建运行目录里发现 `trial_material.npz` 缺失时会调用 `migrate_trial()`，**静默复制固定的 $1/2$ 步候选**。2026-09-18 就是这样把两条"小步"链变成了 $1/2$ 步链，并逼出一次撤回。

现在 `operations/prepare_extension_run.py` 已经修好：**先复制物质态，再逐位断言** `encoded_state`、`base_encoded_state`、`finite_direction`、`base_residual`、`relaxation`；源缺文件或复制后被篡改都直接拒绝（6 项单元测试覆盖，含两条负路径）。**任何新建候选运行的脚本都必须保留这个断言**；只校验配置/种子/哈希不算通过检查。这条规则也已写进 `AGENTS.md`。

### 4.2 形式状态门里有一条 900 秒资源门

`scripts/phase7b9_formal_feedback_pair_adapter.py::_formal_state_gates()` 含 `each_state_wall_time_strictly_below_s: 900`。节点拥塞时单个反馈状态会超时，配对计算（正确地）失败。处置：**保留失败清单作证据（改名不删）+ 等负载回落重算**，不要改这条门。记录见 `handoff/linux-runs/2026-09-18-formal-state-walltime-gate.md`。

### 4.3 监督器会被过期作业记录杀死

`diagnostics/interval_supervise.py` 与 `hpc/supervise.py` 都用 `subprocess.check_output(["squeue","-j",...])` 查询状态，作业记录过期后该命令返回非零 → 抛异常 → 监督器退出。这两个文件都被既有运行的哈希钉住，**不能修改**。替代品是 `operations/interval_supervise_robust.py`：复用被钉住模块的 `submit`/`recovery_refusal`/`acknowledge_failed_job`/`CONTINUE` 语义，只把两处查询换成"查不到即视为已离开队列"，收据写到 `supervisor-robust.json`。**继续用这个**。

## 5. 下一步该做什么（按优先级）

1. **等三条 v3 链跑完**（预计各需 8–12 张映射跨过 $2.5\times10^{-4}$，约 1–2 小时；若预算用尽仍未达标，用同一个 `prepare_extension_run.py` 再建一轮延续——不要放宽门槛）。查看方式：

```bash
tail -6 outputs/hpc/logs/tde-status.log
squeue -u pb24511938 -o "%.8i %.38j %.4t %.8M"
```

2. **跑判词工具**，得到三条链全轮次的状态（有比值的给比值，无比值的给物理域失败统计）：

```bash
.venv-hpc/bin/python operations/small_step_verdict.py \
  --run outputs/hpc/small-step-a15625-cont24-20260918 \
  --run outputs/hpc/small-step-a078125-cont24-20260918 \
  --run outputs/hpc/small-step-a00390625-cont24-20260918
```

3. **收尾报告**：把三条链的门槛级收敛记录与最终判词写进 `handoff/linux-runs/`，与 §3 的证据并列，并明确写出"没有任何步长给出 $R(\alpha)<1$；更小步长的响应不物理"。

4. **进入阶段 D：重做方向**。入口条件已经定量（见 `handoff/linux-runs/2026-09-18-stage-d-finite-difference-design.md`）：
   - 实测噪声底在 $10^{-14}$ 量级；有限差分信号必须比它高至少 10 倍；
   - 已测信号随步长的关系（$1/16$ 步：$1606\times\alpha$；$1/8$ 步：$811\times\alpha$）说明**步长不能太大**（否则落在非线性/饱和区），也不能太小（否则埋进噪声）；
   - 7B9g 当年用相对步长 $1\text{e-}7$，得到的估计信号比实测噪声低 293 倍——这正是旧方向不可用的根源，重建时必须避免。

## 6. 操作纪律与运维要点

### 6.1 三重检查（用户强制要求，见记忆与 `AGENTS.md`）

任何代码在平台运行前必须完成代码/逻辑/物理三项检查，并按固定格式输出：

```text
[PRE-RUN CHECK]
Code: PASS / WARNING / BLOCK
Logic: PASS / WARNING / BLOCK
Physics: PASS / WARNING / BLOCK
Key Issues: 1... 2... 3...
Decision: RUN / DO NOT RUN
```

运行后还要做 Post-Run Check（warning/NaN/Inf、量级、趋势、图像 artifact、能否用物理模型解释）。优先级：物理正确 > 逻辑闭合 > 数值可靠 > 代码运行。

### 6.2 不许做的事

不得用 floor/clip/nan_to_num、不得改物理 dt、不得删除失败单元、不得把相邻漂移当误差上界、不得冻结旧 Q 冒充 Jacobian、不得放宽验收门。判词只在"两端点 R ≤ 门槛"的轮次上做。

### 6.3 SSH 与观测

- 连接：`ssh -o BatchMode=yes -o ControlPath=/Users/shandike/.ssh/tde-control/ustc.sock pb24511938@107.ustc.edu.cn`，命令整体加超时。
- 该套接字会周期性失效（今天断了六次），失效时**只通知用户一次**，请其在 Terminal 运行 `~/.ssh/tde-control/connect-ustc.command`（密码 + 动态码），然后暂停平台操作，不要读写密码。
- 观测优先走 tmux 里的状态记录器，而不是长时间挂 SSH 会话（长会话容易被断）。

### 6.4 已知的本地网络问题

Mac 上 GitHub 推送偶尔失败：`Failed to connect to 127.0.0.1 port 7888`（本机代理未运行）或 `SSL_ERROR_SYSCALL`（瞬时）。前者需要用户启动代理，后者重试即可。**学校侧与 Mac 侧的同步可用 `git bundle`**（本会话一直这样做），不依赖 GitHub。

## 7. 关键文件索引

| 类别 | 文件 |
|---|---|
| 判据工具 | `operations/small_step_verdict.py`、`operations/collect_encoded_ratios.py`、`operations/finite_difference_linearity.py` |
| 运行工具 | `operations/prepare_extension_run.py`（候选运行，带物质态断言）、`operations/prepare_small_step_trial.py`、`operations/interval_supervise_robust.py`（健壮监督器）、`operations/status_logger.sh`（状态记录器） |
| 本阶段报告 | `handoff/linux-runs/2026-09-18-*.md`（判词、失败走势、饱和、撤回、墙钟门、阶段 D 设计） |
| 小型证据 | `handoff/evidence/ustc-*.json` |
| 讲义（给用户） | `lecture/项目讲义/2026-09-18_小步下降检验_独立讲义.md`（含两张图） |

所有大文件（每个辐射态 9.41 GiB）都在学校平台存储，不进 Git；Git 只存代码、说明与小型证据。
