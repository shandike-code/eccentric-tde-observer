# 夜间运行状态（2026-09-16 00:20 起）

给夜间及明早接手用。**本文件只描述安排，不改变任何物理阈值。**

## 资源授权现状（实测，不是推断）

| 项 | 实测值 |
|---|---|
| 我账号允许的 QOS | **仅 `qos_stu_default`**（7 个分区关联全部如此） |
| `qos_stu_large` | **存在但未授权**：实测 `sbatch --qos=qos_stu_large` →
  `error: Invalid qos specification`。该 QoS 规格为 `MaxWall=12:00:00`、`cpu=48` |
| `qos_stu_default` 限额 | `MaxWall=04:00:00`，**`MaxTRESPerUser = cpu=4, mem=16G`**，`MaxJobsPerUser=4` |
| 节点 | 128 核 / 512 GB，但**每人上限是 4 核 + 16 GB**，节点资源不等于个人配额 |

**结论：worker 数被内存门卡死在 2。** `pipeline.require_allocation` 要求
`mem ≥ workers × 6144 + 2048`：2 workers = 14,336 MiB ≈ 14 GB（刚好卡进 16 GB）；
**4 workers 需 26 GB，直接撞 QoS 内存上限**。所以「4 核」对应的仍是 **2 workers**，
不是 4 个 worker。用户将于 2026-09-16 申请 `qos_stu_large`；获批前无任何提升并行空间。

## 正在跑什么

| 项 | 值 |
|---|---|
| 科学 run | **`outputs/hpc/hhe-r025-cont64`** |
| 预算 | **`maximum_maps = 64`**，每 4 张一轮正式反馈 + 逐层账本（⇒ 最多 16 轮） |
| 资源 | **2 workers**、`--cpus-per-task=4`、`--mem=16G`、`qos_stu_default` |
| 种子 | 前一个 run `hhe-r025-cont` 的最终态；其 2 张 map 记录结转在
  `carried_from_previous_run.json`（map1 `1.930156e-04`、map2 `1.915347e-04`） |
| 物质候选 | 固定 0.0625（`trial_material.npz` 沿袭，未重传 Mac 检查点） |
| 声明 | `diagnostic_declaration.json`：git `dd5f3f1f`、6 个诊断源、
  参数 `{maps_per_job:1, feedback_every:4, workers:2, maximum_maps:64, threshold:2.5e-4}` |
| 驱动 | `diagnostics/interval_supervise.py --max-jobs 96`，分离（`PPID=1`） |
| 首个作业 | `63707` `tde-interval` on `anode17` |

## 预计时长

单张 map 实测 628–3587 s（节点间 5.7 倍），单轮反馈 1159–2290 s。

| 情形 | 64 张 + 16 轮反馈 |
|---|---|
| 快节点（~11 min/张） | ≈ 12 h + ≈ 6.7 h ≈ **19 h** |
| 慢节点（~60 min/张） | ≈ **70 h 以上** |

**所以这一夜会被占满，但整轮 64 张可能要跨到明天之后。** 若在慢节点上会明显超出预算时长——
监督器按 4 h 墙钟逐作业接续，不会超时被杀（每作业只做 1 张 map + 至多 1 轮反馈）。

## 停止条件（按优先级）

故障 > 已接受 > 待恢复反馈 > 正常运行 > 预算结束。
**任一环节全部物理门通过即 `one_material_trial_accepted` 立刻停**；
故障即停；到 64 张即停。**不自动扩额、不改物理阈值。**

## 夜间产出（无论何时结束）

1. 每张 map 与每轮反馈的实测数据（残差、边界量、账本、墙钟、RSS）。
2. 中文报告：`handoff/linux-runs/` 下新文件，含具体能量账本与失败门。
3. 新科学反馈的小工件包（供 Mac 复核；排除 `.dat` 与重复旧工件）。
4. 无推送凭据时导出新 bundle。

## 纪律（不变）

负热能或加热不达标**如实报告**，不把代码测试通过当成物理门通过；
不裁剪、不 floor、不改物理 dt、不改能量定义；预算耗尽写成「预算耗尽」，不写成收敛失败。
