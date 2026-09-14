# Phase 7B9de：第一次二分物质回溯候选

上游：[[phase7b9cu_dd_fixed_radiation_and_material_gate|Phase 7B9cu--7B9dd 固定物质辐射与物理域门]]  
下游：该候选的固定物质全频辐射内收敛；本阶段尚未运行。

> `[V]` 原 $0.125$ 物质候选的正式响应离开正气体热能物理域后，本阶段沿同一冻结编码
> 方向做第一次标准二分，构造绝对松弛 $0.0625$ 的唯一候选。候选通过温度、物质比能、
> H/He simplex 和原信赖域门。`[O]` 这只是廉价物质几何门；辐射和正式反馈尚未计算，
> 因而候选没有被接受为非线性步。

## 1. 为什么是二分而不是另选一个“更好看”的步长

7B9dd 拒绝的是冻结方向与 $0.125$ 步长的组合，并没有证明该方向在任意有限小步都失败。
7B9de 在查看新候选结果以前冻结

$$
\eta_{\rm new}
=
\frac{1}{2}\eta_{\rm failed}
=
0.0625,
$$

并定义

$$
\boldsymbol{x}_{\rm trial}
=
\boldsymbol{x}_{0}
+
\eta_{\rm new}\boldsymbol{p},
$$

其中 $\boldsymbol{x}_{0}$ 和 $\boldsymbol{p}$ 分别是 7B9i 已冻结的编码基态与准 Newton
方向。没有重新拟合方向，也没有扫描多个步长后挑选结果。`[A-preregistered]`

## 2. simplex 舍入门更正

第一次执行时，所有物理数组都有限、正值且信赖域通过，但 He 三分量的二进制浮点求和与
1 相差 $2.22\times10^{-16}$。要求三次布居的浮点和逐位等于 1 并不是物理守恒门；三个
数相加包含两次 binary64 加法。更正后的预注册协议使用

$$
\left|\sum_{s}f_{s}-1\right|
<
4\epsilon_{\rm mach},
$$

作为只覆盖浮点加法舍入的闭合界。实际最大误差只有一个机器 epsilon。候选数组没有被
重归一化，也没有使用 clip 或 floor。`[V-roundoff]`

## 3. 候选结果

![Phase 7B9de first dyadic material backtrack](../outputs/phase7b9de_half_trial_material.png)

图 (a) 比较基态与 $0.0625$ 候选温度，最大相对温度变化为 $0.216307$，最大物质比能变化
为 $0.0631827$；都低于原冻结的 $0.5$ 和 $0.25$ 信赖域门。图 (b) 放大展示 H II
布居差，最大 H/He 布居分数变化为 $1.02511\times10^{-6}$。图 (c) 明确记录本阶段没有
计算辐射或正式反馈。`[V]`

全部候选门通过：温度和物质比能严格为正，布居非负，H/He simplex 在机器舍入界内闭合，
编码态逐位满足冻结线性定义。候选文件哈希为
`21bdccd89a96a402a2352408ccab5c80b11bc4244d572fe3cb76ff5a0678d64c`。`[V]`

## 4. 当前授权边界

- 已授权：为该唯一候选建立固定物质、9632 组全频辐射内收敛协议；
- 未授权：把候选视为已接受的物质步；
- 未授权：Phase 4 替换、UVOT、动态 NLTE 或真实线形成；
- 只有新的连续辐射收敛态、正式 H/He 反馈和三种物质残差范数全部通过，才可接受该步。
  `[V/O]`

当前磁盘空余不足以安全新增两个约 $9.40625\,\mathrm{GiB}$ 的完整辐射工作态。只读
Phase 7B9df 预检确认两个历史候选共 $18.8125\,\mathrm{GiB}$、均不属于当前 7B9dd
保护链，但仍有历史引用。用户随后明确批准只复用这两个检查点。Phase 7B9dg 逐文件重算
SHA-256，分别得到 `e6020542...911f` 和 `1409b102...949b`，与各自冻结协议完全一致；
机器可读授权保留了旧哈希、全部直接引用和“覆盖后旧字节只能通过重算恢复”的事实。
当前三个 7B9dd 收敛/审计态被单独列为禁止修改。`[V-hash/A-resource]`

授权本身不等于已经覆盖：`outputs/phase7b9dg_preregistered_storage_reuse.json` 还要求未来
固定物质辐射协议先冻结自身哈希，并且只能把这两个精确路径作为 ping-pong 缓冲区。
在该协议落盘并通过测试以前，没有历史检查点被修改。`[V/O]`

## 5. 复现

    python scripts/phase7b9de_preregister_half_trial_material.py
    python scripts/phase7b9de_build_half_trial_material.py \
      --expected-protocol-sha256 <printed-sha256>
    uv run pytest -q tests/test_phase7b9de_half_trial_material.py

机器可读产物为 `outputs/phase7b9de_preregistered_half_trial_material.json`、
`outputs/phase7b9de_half_trial_material_summary.json` 和
`outputs/phase7b9de_half_trial_material_state.npz`。
