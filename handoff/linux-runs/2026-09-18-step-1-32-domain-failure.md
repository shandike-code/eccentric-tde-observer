# 发现：α=1/32 步长的物质响应离开物理域（暂态，待收敛确认）

## 观测

`small-step-a00390625-20260917`（步长 = 原 0.125 的 1/32，trial 身份已验证）第 1 轮（端点 maps 3,4）的反馈协议给出：

```
classification = [A-preregistered] + [V-physical-domain] + [O]
encoded_residual_path = null      （适配器因此不写编码残差）
material_response_failures = {
  previous: PhysicalDomainError "specific material energy leaves no positive gas heat",
  final   : 同上 }
```

账本给出的失败量：

| 端点 | 失败单元数 | 失败质量份额 | 最差单元 | remaining / old_gas_heat |
|---|---|---|---|---|
| previous（map 3） | 50 | 0.683 | cell 115 | **−5.42** |
| final（map 4） | 49 | 0.675 | cell 115 | **−5.23** |

即：该轮冻结场驱动的净冷却**超过**可用气体热能 5 倍以上，更新后的布居对应的电离能高于目标比能量，正温度解不存在。

## 与其它步长的对照（同样来自各自的记录）

| 步长 | 失败单元数 | 出处 |
|---|---|---|
| 1/2（0.0625） | **0** | ext16 / cont64 全部轮次 |
| 1/4（0.03125） | 32–43 | backtrack-v2 / scale32 / confirm |
| 1/32（0.00390625） | **49–50** | 本轮，第 1 轮 |

**"步长更小更安全"在这一族里不成立**：失败单元数随步长减小而增加。

## 必须一起读的保留（纪律性）

这一轮的两个端点 R ≈ 4e-3，**远未收敛**（阶段 B 门槛 2.5e-4）。物质响应用的是冻结辐射场算出的光致电离/复合/加热率，场未收敛时这些率不可靠。因此：

1. **不能**把这个物理域失败归因于 α=1/32 候选本身；
2. 该轮在判词里只标 provisional，不参与任何判据；
3. 链条继续跑（驱动把它记为 `[V-physical-domain]` 轮次并继续 map），等端点 R ≤ 2.5e-4 后再评估该步长的物质响应是否真的离开物理域。

不过一个量级上的判断可以做：失败幅度是**旧气体热能的 5 倍以上**，而此前观测到的"R 从 4e-3 收敛到 2.5e-4 时率的变化"只有 1–2 倍量级（见 α=1/16 那条链的加热量随 R 的变化）。所以**先验上**，这个失败在收敛后翻转为物理的可能性不大——但这是量级判断，不是结论；结论必须由收敛后的端点给出。

## 工具处置

这类轮次的 `encoded_residual_path` 为 `null`，此前会让 `collect_encoded_ratios`/`small_step_verdict` 直接崩。已修：两个工具现在把这种轮次记为 `no encoded residual recorded`，带上 `classification` 与失败信息，`ratio_to_base` 与 `l2` 置 null，并且**不参与判词**（判词只在有实测比值的轮次里选）。新增两条回归测试（无残差轮次不崩、判词忽略无比值轮次），12 项相关测试通过；提交 6fb814a，已在真实数据上验证输出 `VERDICT: pending | no round has both endpoints at or below 2.5e-4`。
