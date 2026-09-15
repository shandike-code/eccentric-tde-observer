# 本地提交 `1040b7b` 的保全

**背景：** 学校侧上个会话在 `hpc/supervise.py` 里加了 `sacct` 失败时回退到 `scontrol` 的逻辑。
本集群 `slurmdbd` 没有作业记录，`sacct` 对任何作业都返回空，旧的 sacct-only 版监督器会在
10 次轮询后抛 `RuntimeError` 停止自动续交。**cold 夜间轮 16 次自动接续全靠这个修复。**

该提交**从未推送到远端**（学校侧 `github.com` 被出口策略阻断）。

## 提交图

```
远端 main:  f35aa78 → c4d735e → c5b9208f → 9e100f84 → cfbbf112
本地 main:  f35aa78 → c4d735e → 1040b7b          ← HEAD，远端不存在
```

共同祖先 `c4d735e`。

```
1040b7b95bf4b247361b66078487bee8da9f8dfa
shandike-code <310837749+shandike-code@users.noreply.github.com>
Mon Sep 14 17:44:58 2026 +0800

Fall back to scontrol when sacct records no job completions
```

改动：`hpc/supervise.py`（+45/−7）、`environment-linux.txt`（新增）、
`handoff/linux-runs/2026-09-14-{smoke-62570,block-check-62576,block-check-62585}.md`（新增）。

## 文件

| 文件 | 说明 |
|---|---|
| `commits.txt` | 提交图、提交详情、与远端的关系 |
| `1040b7b-scontrol-fallback.patch` | `git format-patch -1 1040b7b` 的完整补丁，sha256 `29aae391b129773fac5a084be1a34f52711015fae2311c109c36e5630b33c899` |

## 关键 blob 对照

| 文件 | 本地 `1040b7b` | 远端 `main` |
|---|---|---|
| `hpc/supervise.py` | `c366da8b7ebd5b3d3d173ee7abf3a39e4d8860c9`（含 `scontrol_state`） | `1a239109774546ca4a5b36e69e0641e2d5a2b21f`（sacct-only） |

## 具备连接时怎么同步

**不要** `git reset --hard`，也**不要**用 `git pull` 去覆盖本地工作树——那会撤掉该修复，
并击穿已有 run 的冻结源哈希（`config.json` 固定了 `src/`、`scripts/`、`hpc/` 下每个 `.py` 的 sha256，
运行入口每次做全量 `verify_claims(hash_files=True)`）。

建议路径（在能访问 `github.com` 的一侧操作）：

```bash
# 方式一：直接推这个提交（学校侧有凭据时）
git push origin 1040b7b:main          # 若远端 main 未再前进，这是快进

# 方式二：远端已前进时，把这一个提交摘过去
git fetch origin main
git rebase origin/main                # 在本地 1040b7b 所在分支
# 或：git cherry-pick 1040b7b

# 方式三：无法直接推时，用本目录的补丁
git am handoff/local-commit-1040b7b/1040b7b-scontrol-fallback.patch
```

合并结果必须复核 `hpc/supervise.py` 同时保留**远端的新逻辑**与**scontrol 回退**，
不能简单地二选一。
