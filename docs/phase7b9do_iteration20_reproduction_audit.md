# Phase 7B9do：iteration 20 异常的全图复现审计

上游：[[phase7b9cu_dd_fixed_radiation_and_material_gate|Phase 7B9cu--7B9dd 固定物质辐射与物理域门]]  
相关候选：[[phase7b9de_half_trial_material|Phase 7B9de 第一次二分物质回溯候选]]

> `[V]` 本审计只读取 7B9di、7B9dj、7B9dk、7B9dl 的小型 JSON 摘要与 7B9dk
> 保留的 76 份块报告，没有读取任何完整 `.dat` 状态。原 7B9di iteration 20 是被拒绝的
> 异常映射；两次只在内存中进行的 block 34 重算彼此逐字节一致；随后 7B9dk 从相同输入
> 独立重跑全部 76 块，得到通过 progression 门的新状态。`[O]` 该证据解释了异常的定位
> 与可复现性，但没有解释 block 34 首次落盘异常的底层系统原因。

## 1. 审计量与判据

全局原算子残差沿用冻结定义

$$
R_{n}
=
\frac{
\max\left|\mathcal{M}(I_{n})-I_{n}\right|
}{
\max\left(
\max\left|\mathcal{M}(I_{n})\right|,
\max\left|I_{n}\right|
\right)
},
$$

收缩比为

$$
q_{n}=\frac{R_{n}}{R_{n-1}}.
$$

progression 要求 $q_{n}<1.01$，正式辐射收敛仍要求 $R_{n}<10^{-4}$；边界谱和边界 bolometric
变化的门均为 $10^{-3}$。本审计没有重新定义任何门，也没有因为异常点而重归一化残差。
`[V]`

## 2. 诊断图

![Phase 7B9do iteration 20 reproduction evidence](../outputs/phase7b9do_iteration20_reproduction_audit.png)

### 面板 (a)：异常点与有效残差历史

蓝线是 7B9dl 接受的可复现历史。红叉是原 7B9di iteration 20：
$R_{20}=1.3567073\times10^{-2}$、$q_{20}=7.631389$，因此不能进入有效历史。绿色点是从同一
iteration 19 输出重新计算全部 76 块得到的 7B9dk 结果：
$R_{20}=1.6842474\times10^{-3}$、$q_{20}=0.947378$。7B9dl 继续到 iteration 23 后，残差
降至 $1.4343675\times10^{-3}$，仍高于 $10^{-4}$；所以图中下降趋势不是收敛证明。`[V/O]`

### 面板 (b)：76 块逐块哈希比较

横轴列出全部 76 个频率块。每一份保留报告都同时记录被拒绝输出的旧块 SHA-256 与 fresh
full-map 的新块 SHA-256。75 块逐字节相同，只有 block 34 不同；76 块的 ownership 连续
覆盖全部 9632 个频率组，没有缺块或重叠。这个结论由脚本扫描全部报告得到，并非硬编码
到图中。`[V]`

### 面板 (c)：只在内存中的定位证据

两次独立 block 34 重算的内存字节完全一致，都不等于首次失败落盘块；它们又与 7B9dk
全图重算中的 fresh block 34 完全一致。两次定位运行都记录
`output_persisted=false` 和 `input_modified=false`。因此它们只提供定位证据，没有创建或
修改任何可进入物理历史的状态。`[V]`

### 面板 (d)：fresh full-map 的门归一化量

柱高是“指标除以对应门槛”。fresh full-map 的残差是残差门的 $16.8425$ 倍，故尚未收敛；
同时 $q/1.01=0.937998$，边界谱变化为 $5.1618238\times10^{-4}$，边界 bolometric 变化为
$5.1415330\times10^{-4}$，三项 progression/边界门均通过。完整 ownership、非负性和资源门
也通过。`[V]`

## 3. 为什么这不是单块修补

block 34 的两次内存重算只说明首次持久化块不能由相同输入与冻结算子重现。正式恢复步骤
没有把这个块单独写回旧输出，而是从原 iteration 20 输入重新运行全部 76 块，保留每块
报告，再对 fresh 全态重新计算全局残差、收缩比、边界量、正性、ownership 与资源门。
7B9dk 明确记录 `single_block_repair_used=false`；7B9dj 明确记录
`single_block_repair_authorized=false`。`[V]`

因此，“只有 block 34 的哈希不同”是全图复现之后得到的诊断事实，不是事后把一个坏块
替换进旧状态的授权。原异常状态继续保留为 rejected evidence，并在 7B9dl 中明确标记为
`may_enter_valid_history=false`。`[V]`

## 4. 当前结论边界

- `[V]` 原 iteration 20 被正确拒绝；fresh 76-block reproduction 通过 progression、边界、
  positivity、ownership 和资源门，可作为后续固定物质 Picard 历史的 iteration 20。
- `[V]` 7B9dl 使用 fresh reproduction 继续三次映射，残差单调下降且 $q<1$。
- `[V]` 7B9dl 以 `maximum_maps_exhausted` 结束，尚未达到 $10^{-4}$；物质反馈未获授权，
  dynamic NLTE 也没有被接受。
- `[O]` 首次 block 34 持久化为何与两次内存重算及 fresh 全图重算不同，仍是未闭合的底层
  原因；当前证据没有授权据此修改算子、门槛或任意检查点。

## 5. 复现

    .venv/bin/python scripts/phase7b9do_iteration20_reproduction_audit.py
    .venv/bin/python -m pytest -q tests/test_phase7b9do_iteration20_reproduction_audit.py

机器可读产物为 `outputs/phase7b9do_iteration20_reproduction_audit.json`；诊断图为
`outputs/phase7b9do_iteration20_reproduction_audit.png`。JSON 保存五个小型上游摘要的
SHA-256、76 份块报告的逐文件身份与规范化 manifest 哈希，并显式记录
`full_state_bytes_read=false` 和 `dat_files_opened=0`。`[V]`
