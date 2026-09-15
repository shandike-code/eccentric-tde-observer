# 本地提交 `1040b7b` 的保全

> **2026-09-15 更新：本文件初版有两处错误，已改正。**
> 初版称「`git push origin 1040b7b:main` 若是快进即可」，但远端 `main` 当时**已经前进到
> `cfbbf112`**，该 push 会被拒；初版又称「GitHub 从集群完全阻断」，后来实测**不成立**。
> 见 §3。

## 背景

学校侧上个会话在 `hpc/supervise.py` 里加了 `sacct` 失败时回退到 `scontrol` 的逻辑。
本集群 `slurmdbd` 没有作业记录，`sacct` 对任何作业都返回空，旧的 sacct-only 版监督器会在
10 次轮询后抛 `RuntimeError` 停止自动续交。**cold 夜间轮 16 次自动接续全靠这个修复。**

## 1. 提交图

```
1040b7b95bf4b247361b66078487bee8da9f8dfa
shandike-code <310837749+shandike-code@users.noreply.github.com>
Mon Sep 14 17:44:58 2026 +0800

Fall back to scontrol when sacct records no job completions
```

```
远端 main:  f35aa78 → c4d735e → c5b9208f → 9e100f84 → cfbbf112
诊断分支:   f35aa78 → c4d735e → 1040b7b → 6423e4c → 5ad7fa6 → d3ec351
两者共同祖先：c4d735e
```

改动：`hpc/supervise.py`（+45/−7）、`environment-linux.txt`（新增）、
`handoff/linux-runs/2026-09-14-{smoke-62570,block-check-62576,block-check-62585}.md`（新增）。

## 2. 现状：`1040b7b` 已经可达，不必再单独推

`1040b7b` 是 `ustc-hpc-diagnostics` 分支的祖先，而该分支已在远端
（Mac 侧 pull 了学校导出的 bundle 后推送）：

```
$ git ls-remote --heads origin
cfbbf112...  refs/heads/main
d3ec3511...  refs/heads/ustc-hpc-diagnostics
$ git merge-base --is-ancestor 1040b7b origin/ustc-hpc-diagnostics && echo yes
yes
```

**所以「`1040b7b` 在远端不可达」这个问题已经不存在。** 它可以通过诊断分支取到：

```bash
git fetch origin
git log --oneline origin/ustc-hpc-diagnostics | head    # 会看到 1040b7b
git show origin/ustc-hpc-diagnostics:hpc/supervise.py | grep -c scontrol_state   # -> 2
```

剩下的是**是否要把这个修复并进 `main`**——那是合并决策，由用户定，不是本文件该建议的。

| 文件 | 本地 `1040b7b` | 远端 `main` (`cfbbf112`) |
|---|---|---|
| `hpc/supervise.py` | `c366da8b7ebd5b3d3d173ee7abf3a39e4d8860c9`（含 `scontrol_state`） | `1a239109774546ca4a5b36e69e0641e2d5a2b21f`（sacct-only） |

## 3. 关于网络与认证（改正初版）

实测（2026-09-15）：

- **git 走 HTTPS 到 `github.com` 是通的**：`git ls-remote --heads https://github.com/...`
  返回 `0` 并列出 refs；`git fetch origin` 成功。
- 初版据 `curl https://github.com` 返回 `000` 断言「完全阻断」——**那是 www 页面路径被挡，
  不是 git 的 smart HTTP**。两者必须分开判断。
- **`git push` 需要认证，而学校侧没有任何 GitHub 凭据**（无 `credential.helper`、
  无 `~/.git-credentials`、无 `gh`、无令牌环境变量）。报错是
  `could not read Username for 'https://github.com'`。
- 因此学校侧**只能读、不能写**；要交付本地提交只能走 `git bundle`
  （`git bundle create <file> <branch>`，本仓库已验证可生成"complete history"的 bundle）。
- **不要把令牌写进 URL、脚本或提交**；也不要去索要或经手用户的令牌。

## 4. 文件

| 文件 | 说明 |
|---|---|
| `commits.txt` | 提交图、提交详情、与远端的关系 |
| `1040b7b-scontrol-fallback.patch` | `git format-patch -1 1040b7b`，sha256 `29aae391b129773fac5a084be1a34f52711015fae2311c109c36e5630b33c899` |

## 5. 合并时的注意

合并结果必须复核 `hpc/supervise.py` **同时保留**远端的新逻辑与**学校侧的 scontrol 回退**，
不能简单二选一。另外：任何改动 `hpc/` 下 `.py` 的动作都会改变其内容哈希，
而每个已准备 run 的 `config.json` 固定了该目录每个 `.py` 的 sha256——
**在还有 run 需要续跑时，合并前要先确认这些 run 已不再需要按原哈希校验。**
