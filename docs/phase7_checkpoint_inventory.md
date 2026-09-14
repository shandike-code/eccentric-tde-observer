# Phase 7 辐射检查点只读清单

## 1. 这份清单回答什么

Phase 7 的完整辐射态很大，保留多个检查点是为了支持中断恢复、独立残差复算、加速方法
回退和连续两态验收。Phase 7 的物质外层尚未收敛时，旧文件名仍可能被协议、结果账本或诊断脚本
直接引用，不能只根据修改时间决定删除。[V/O]

本清单递归读取 `outputs/checkpoints` 下所有普通文件的目录项、逻辑大小、磁盘块数和修改
时间；只有完整辐射态路径会进一步在下列文本域中扫描引用：[V]

- `outputs/*.json`；
- `docs/**/*.md`；
- `scripts/**/*.py`。

没有读取或哈希任何检查点文件内容，也没有修改、移动或删除任何检查点。

## 2. 存储类别与依赖分类

递归存储类别为：

- `full-state-dat`：`.dat` 且逻辑大小严格等于当前协议完整辐射态大小；
- `block-chunk-state`：较小的 `.dat` 块，或 `.npz` 分块状态；
- `json-report`：manifest、worker report 或诊断账本；
- `other`：其余普通文件。

每类同时报告 apparent size 和 allocated size。前者是文件声明的逻辑字节数；后者由
`st_blocks * 512` 得到，反映文件系统实际计入的磁盘块，不读取文件内容。[V]

只有 `full-state-dat` 使用以下依赖分类：

- `active`：当前 Phase 7B9dd 决策链保留的 `previous_converged`、`final_converged` 或
  `residual_audit_output`；该标签不表示仍有进程运行；
- `referenced`：不属于活动三态，但至少被一个声明扫描域内的文本文件直接点名；
- `unreferenced-candidate`：没有可解析直接文本引用的完整态；
- `unknown`：只有无法归属的重复 basename 引用，依赖状态不明。

这些是 [A-classification] 的依赖整理标签，不是保留期限或删除许可。特别是
`unreferenced-candidate` 仍可能被动态构造路径、尚未落盘的运行状态或人工复算流程依赖。

## 3. 当前快照与顶层统计差额

机器可读结果位于 `outputs/phase7_checkpoint_inventory.json`。每个完整 `.dat` 条目包含：

- apparent size、allocated size 和修改时间；
- 直接引用文件数、总出现次数和引用者列表；
- Phase 7B9dd 的保护角色及快照时运行角色；
- 四分类结果。

先前的 112.875 GiB 只来自当时 12 个顶层完整 `.dat`，并不是整个 checkpoint tree。
当前重新盘点得到 13 个顶层完整态、10 个嵌套完整态；历史数字只用于解释统计口径，不能
替代当前扫描。[V]

其中最主要的差额来自嵌套完整态：每个约 9.40625 GiB，多个 `state_a.dat`、
`state_b.dat` 和残差工作缓冲区合计 94.0625 GiB。当前 23 个完整态共 216.34375 GiB，
469 个 block/chunk 共 1.65852 GiB，9082 个 JSON/report 共 0.02680 GiB；递归 apparent
size 为 218.0291 GiB，`st_blocks * 512` 占用为 218.0552 GiB。[V]

机器可读报告按四个存储类别分别给出文件数、apparent size 和 allocated size，并另外报告
目录元数据占用。当前保护角色从
`outputs/phase7b9dd_preregistered_material_trial_rejection.json` 和
`outputs/phase7b9cw_consecutive_confirmation_summary.json` 读取。三个角色分别是正式反馈的
previous/final 辐射端点与只用于审计 final 残差的 mapped output；当前运行角色为空，因此
清单不靠文件名猜测状态，也不暗示仍有计算进程。[V]

## 4. 不能从这份清单推出什么

直接引用数量不等于真实依赖强度：旧报告中的一次历史引用和当前运行协议中的一次引用具有
不同意义。递归后部分工作缓冲区共享 `state_a.dat` 或 `state_b.dat` 文件名，因此只有完整
相对路径能无歧义归属；重复 basename-only 引用被标为 ambiguous，而不是强行分配。
本阶段没有解析 Python 动态字符串，也没有验证各检查点内容哈希。[O]

因此当前清单明确不写“可安全删除”。最终清理必须满足：[O]

1. Phase 7 收敛完成；
2. 对最终保留链重新做内容哈希审计；
3. 重新做直接和动态依赖审计；
4. 给出具体候选文件及可恢复性说明；
5. 获得用户明确批准。

## 5. 复现

    python scripts/phase7_checkpoint_inventory.py
    uv run pytest -q tests/test_phase7_checkpoint_inventory.py

阶段关系见
[[eccentric_tde_observer/docs/phase7b_periodic_column|Phase 7B 周期柱]]和
[[eccentric_tde_observer/docs/phase5b4a_cross_platform_audit|Phase 5B4a]]。
[[eccentric_tde_observer/docs/phase7b9dt_two_state_slow_mode_locator|Phase 7B9dt 两态慢模定位]]
