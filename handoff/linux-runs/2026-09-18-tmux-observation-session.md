# 学校侧 tmux 常驻观测会话（tde-hhe）

## 它解决什么、不解决什么

- **解决**：观测被本机 SSH 连接断开而中断的问题。昨天晚上断线期间我完全看不到平台状态；现在记录器在登录节点的 tmux 里持续写日志，重连一次 `tail` 就能补看整段空档。
- **不解决**：本机认证过期本身。SSH master 套接字仍会失效，仍需用户在 Terminal 重新认证；要减少这一点需要改本机 `~/.ssh/config` 的 `ControlPersist`，那是另一项改动，未执行。
- **不参与计算**：记录器只读 `state.json`、`squeue`、`scontrol`，只追加自己的日志；不提交、不取消、不重启、不改任何 run 状态，也不做任何策略判断——故障只记录，仍由人确认后处理，符合"监督器遇故障必须停下"的纪律。

## 会话结构

```
tde-hhe: 2 windows (created 2026-09-18 09:11:25)
  window status : TDE_STATUS_INTERVAL=300 bash operations/status_logger.sh
  window shell  : 空的登录 shell，供人工检查
```

日志：`outputs/hpc/logs/tde-status.log`（追加式，每 5 分钟一行）。

## 日常用法（一条 SSH 命令即可）

```bash
# 最近一小时的状态轨迹
tail -12 outputs/hpc/logs/tde-status.log
# 会话是否还在
tmux ls
# 看某个窗口
tmux capture-pane -p -t tde-hhe:status | tail -5
```

记录器脚本：`operations/status_logger.sh`（提交 806daf7）。它按 `TDE_STATUS_RUNS` 里列出的 run 逐个读取 `state.json`，输出 `status/maps/末轮R/rounds/pending`，并附带节点负载与本人队列快照；读不到的 run 记为 `unreadable(<异常类型>)` 而不中断。

## 部署时的检查（按用户 2026-09-18 的强制协议）

- Code：`bash -n` 在 Mac 与 Linux 均通过；本机合成 run 实测逐行输出、循环间隔、缺失 run 与 `scontrol/squeue` 不可用两条负路径。
- Logic：唯一输入是各 run 的 `state.json` 与调度器只读查询；输出只追加到自己的日志；无策略判断。
- Physics：N/A（不做任何物理计算）。
- 运行后观察：首行记录与三条链的实际状态逐项一致（a00390625 maps1/R4.9663e-03、a078125 maps6/R9.8201e-04、a15625 maps43/R9.2192e-05），未出现 NaN/Inf 或异常。
