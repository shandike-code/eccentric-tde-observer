# Phase 7B9cu--7B9dd：固定物质辐射收敛与有限物质试步门

上游：[[phase7b9n_multimode_krylov_pilot|Phase 7B9n 未预条件多模 Krylov 失败门]]  
下游：有界物质步长线搜索；尚未授权 Phase 4 替换、UVOT 或真实线形成。

> `[V]` 在冻结的 $0.125$ 有限物质候选上，受保护 Anderson(1) 候选经两次独立完整
> $9632$ 组映射确认，使连续两个辐射内残差都低于 $10^{-4}$。最后两态正式 H/He
> 反馈的全部预注册稳定量都低于 $10^{-3}$。`[V/O]` 但同一个 $0.125$ 物质响应在两态
> 上都使气体热能离开正值物理域，因此该有限步被拒绝；这既不是动态 NLTE 解，也不能
> 由一次失败推断静态近似不存在。

## 1. 为什么 7B9n 之后仍继续固定物质辐射迭代

7B9n 拒绝的是未预条件的短历史 Krylov 外推，不是固定物质辐射方程本身。后续 Picard
序列保持有限、非负，边界谱也持续收敛，但慢模收缩率接近 1。直接继续数十次映射会消耗
大量时间，因此 7B9cu 只在已有连续 Picard 尾部上构造一次受保护 Anderson(1) 候选，并
冻结以下门：

- 候选和映射态逐块有限、非负；
- 全局原算子残差必须小于 $10^{-4}$；
- 边界谱和 bolometric 变化必须小于 $10^{-3}$；
- 不使用 floor、clip、删除频率块或事后重归一化；
- 预测必须由新的完整原算子映射复核，不能把外推值当成收敛证明。`[A/V]`

## 2. 受保护 Anderson 候选与新原算子复核

![Phase 7B9cu protected Anderson slow-mode candidate](../outputs/phase7b9cu_protected_anderson_tail.png)

图中蓝线是 76 个自然频率块的候选残差结构；灰色点线是最新 Picard 态的全局残差
$1.2755655\times10^{-4}$，黑色虚线是 Anderson 候选预测
$6.0059812\times10^{-5}$。保护系数选择为 $96$，系数一范数为 $191$；候选保持全块
非负，预测边界谱和 bolometric 变化分别为 $4.97877\times10^{-7}$ 和
$1.29250\times10^{-7}$。这些值只授权 fresh map。`[A/V]`

![Phase 7B9cv fresh full-map validation](../outputs/phase7b9cv_candidate_fresh_map.png)

7B9cv 对候选重新执行全部 76 块的正性 Picard 映射。图 (a) 给出真实逐块变化，图 (b)
给出独立汇总：真实全局残差为 $6.0059811515\times10^{-5}$，与预言的相对差约为
$1.76\times10^{-10}$；边界谱和 bolometric 变化分别为
$4.9787663\times10^{-7}$ 和 $1.2924998\times10^{-7}$。运行使用 2 个 worker，峰值进程
RSS 为 $2788.97\,\mathrm{MiB}$。这一步把外推候选升级为一个实际通过的固定物质辐射态。
`[V]`

![Phase 7B9cw consecutive convergence confirmation](../outputs/phase7b9cw_consecutive_confirmation.png)

7B9cw 再从该态执行一次完整映射。第二个连续输入态的真实残差为
$5.9618518917\times10^{-5}$，边界谱和 bolometric 变化分别为
$4.7653358\times10^{-7}$ 和 $1.2581653\times10^{-7}$。因此不是单个偶然候选，而是两个
连续、独立 fresh-map 输入态同时通过 $10^{-4}$ 辐射残差门和 $10^{-3}$ 边界门。`[V]`

## 3. 正式 H/He 反馈为什么可以读取这两个态

正式反馈使用前一收敛态 $X$ 和当前收敛态 $Y$；从 $Y$ 新映射得到的 $Z$ 只用于审计
$Y$ 的残差，不能误作第二个物质反馈端点。7B9cy 还发现旧反馈模板固定了
`mixed_frame_frequency.py` 的早期哈希。独立迁移审计在内存中精确重建旧版本，并验证：

- 当前版本只新增 signed-ALI 扰动接口；
- 正值正式反馈路径没有引用这些接口；
- 旧版和当前版在正值角强度、平均强度和角测度数组上逐位相同；
- 因此只刷新 worker 依赖模板，不修改物理输入或反馈公式。`[V-code-path]`

第一次重复正式反馈时，旧模板的一个 block 49 出现单次字节异常。独立单 worker 重算与先前
通过的 7B9cz block 49 逐位相同；其余 75 个 previous 块和全部 76 个 final 块也一致。
因此通过的 7B9cz 正式反馈产物可复用，而异常运行没有进入物质更新。`[V-reproduction]`

## 4. 最后两态正式反馈与物质物理域

对任意正式量 $Q$，稳定性使用两态体积一范数相对差

$$
\delta_{\rm Q}
=
\frac{\int |Q_{\rm Y}-Q_{\rm X}|\,{\rm d}V}
{\max\!\left(\int |Q_{\rm X}|\,{\rm d}V,\int |Q_{\rm Y}|\,{\rm d}V\right)}.
$$

三个光致电离率的 $\delta_{\rm Q}$ 为
$4.64745\times10^{-7}$、$8.92490\times10^{-6}$、$3.26800\times10^{-9}$；三个总复合率为
$4.33286\times10^{-9}$、$2.57495\times10^{-9}$、$1.64775\times10^{-14}$。原子、直接和
正式加热的相对差分别为 $1.21833\times10^{-4}$、$1.21833\times10^{-4}$ 和
$1.21835\times10^{-4}$，全部通过 $10^{-3}$ 门。`[V]`

![Phase 7B9dd finite material trial rejection](../outputs/phase7b9dd_material_trial_rejection.png)

图 (a) 展示最终态 H I、He I、He II 光致电离率随质量深度的变化；图 (b) 中两条正式加热
曲线几乎重合，与上述稳定性量一致。右侧不是数值崩溃，而是明确的物理域判定：previous
和 final 两个辐射端点都使 $0.125$ 有限物质响应触发
`specific material energy leaves no positive gas heat`。程序没有裁剪、floor 或写出伪造
目标残差；目标物质态和编码残差文件有意保持不存在。`[V-physical-domain]`

## 5. 当前科学决策

| 问题 | 当前结论 | 证据 |
|---|---|---|
| 固定候选物质态上的辐射内层是否收敛 | 是；两个连续 fresh-map 残差均小于 $10^{-4}$ | `[V]` |
| 最后两态正式 H/He 反馈是否稳定 | 是；全部五类反馈变化均小于 $10^{-3}$ | `[V]` |
| 原 $0.125$ 有限物质步是否可接受 | 否；两端点都离开正气体热能物理域 | `[V]` |
| 一次失败是否证明所有静态解不存在 | 否；它只拒绝该方向和该步长的组合 | `[V/O]` |
| 是否已得到动态 NLTE 周期柱 | 否 | `[O]` |
| 是否可替换 Phase 4 或开始 UVOT | 否 | `[O]` |
| 是否可把连续谱当作 Cloudy 的物理 ionizing seed | 否；尚无接受的耦合物质态和生产大气谱 | `[O]` |

当前下一门应是**预注册的有界物质步长线搜索**：沿同一冻结方向使用事先声明的递减步长，
每个候选先过正气体热能、温度和 H/He simplex 门；只对第一个通过廉价物理域门的候选执行
完整辐射与正式反馈验证。不能根据“哪个步长图最好看”事后挑选，也不能用裁剪挽救失败态。
若所有预注册小步都失败，或有效步长趋于零而物质残差不下降，才形成静态近似失败、需要
进入周期动态 NLTE 柱的更强证据。`[A-next/O]`

## 6. 复现入口

- `outputs/phase7b9cu_protected_anderson_tail_summary.json`：受保护候选和预测门；
- `outputs/phase7b9cv_candidate_fresh_map_summary.json`：第一次独立完整映射；
- `outputs/phase7b9cw_consecutive_confirmation_summary.json`：第二个连续收敛态；
- `outputs/phase7b9cy_feedback_dependency_migration_audit.json`：反馈依赖迁移审计；
- `outputs/phase7b9db_feedback_block_reproduction_audit.json`：block 49 独立复现；
- `outputs/phase7b9dd_material_trial_rejection_summary.json`：正式反馈稳定性和结构化拒绝；
- `scripts/phase7b9dd_material_trial_rejection.py`：最终只读决策入口；
- `tests/test_formal_feedback_pair.py`、`tests/test_phase7b9db_feedback_block_reproduction_audit.py`：
  正式反馈、编码与复现回归测试。

