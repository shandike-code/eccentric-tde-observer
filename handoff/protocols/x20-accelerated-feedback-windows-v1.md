# 冻结 x20：加速初值与保留历史的配对反馈窗口

2026-09-30。先验：81679 两张真实映射已完成独立小工件审计；full 的 L2 缺陷比 0.7646030652102698，half 仿射差的 L2/Linf 比 2.1243e-9/2.2942e-9，均过原门。该结论不包含 H/He 反馈或严格误差界。

## 固定输入与预算

`accelerated` 从81679 full 的**真实输出** `full/state_1.dat` 起跑（SHA a9aaf15de922d5f6e98588c26faab8e6ec95a0c4ef35813aaecdecd3225e332f）；`historical` 从80554 historical map24 的保留输出起跑（SHA c558b84cd3d00ca45855afed9d47303b6452723eebfce2623eb1eb555241266e）。它们是有关联的两种数值初值，不能称统计独立样本或独立物理历史。

两支严格同一个 x20：trial 文件与 encoded_state、base_encoded_state、finite_direction、base_residual、relaxation、native 镜像逐项验证。physical old、phase1367、dt=889.419892762322 s、原 r20 不变。先写 trial 再初始化，禁止回落至固定0.0625旧候选。

新目录 `outputs/hpc/x20-accelerated-feedback-windows-20260930`；已有目录拒绝覆盖。cpu_long/Students、32CPU、128GiB、16workers、6h硬上限，USR1提前900s。每支最多16张原map；顺序 accelerated8 → historical8 → accelerated16 → historical16，总计最多32张map、4个正式反馈对、零物质步。中断保存部分map与小归档；本驱动不自动恢复已存在目录，必须先审计停止点再制定有界恢复。大态仅留学校，不传Mac、不进Git。

## 数学量与判定

每个检查点先要求连续两态的原辐射门1e-4，再用原零位移反馈协议重算previous/final两个端点。原七门、物质响应正热能与合法布居、NaN/Inf检查、频率归属、代码/数据哈希和内存护栏不变。程序、资源、物理域或原反馈质量失败立即停止后续工作。

用完整512维物质残差向量先作差，再分别计算 L2、质量加权及最差单元范数。每条分支比较16对8的所有四个端点组合；两条分支比较同龄端点的所有四个组合。所有比较同时保留：差向量范数/原 r20 范数 <0.001，差向量范数/冻结80195布居响应信号 <0.1。信号尺度直接复用已审80554声明，禁止换分母、加floor或用标量范数相减冒充向量差。

第8张跨初值只测量；窗口或跨初值漂移未过不截断另一支同龄检查点，预算内收齐完整配对实验。该失败仍记为失败，不能被继续执行改写。最终资格要求四个原反馈对均通过、两支16−8窗口通过、16时跨初值完整向量差与四组率/加热原门全通过。`reference_calibration_eligible=true`只代表可以提交独立审查的有限窗口资格；不能自动替换r20、接受第21步或宣告辐射误差为零。

`from_prior_feedback`仅用于沿历史定位：accelerated的参考是80554 late pair16，**不是加速seed本身的反馈**；historical参考是80554 historical pair24。两支新增map数相同不意味着累计迭代龄相同。

## 输出及审阅

每轮保留独立protocol、端点清单、feedback/response NPZ、baseline_summary与decision，写入不可覆盖的小归档。终态保留每支窗口、跨支比较、map和pair实际计数、资源峰值与预算。平台CLI只读监督，无编辑/提交/取消权限；Codex独立核验后才能制定后续。accepted_outer_steps=20、new_material_steps=0、baseline_replaced=false、strict_error_bound=false始终成立。

本次检验回答“加速后的低辐射缺陷是否也改善正式物质响应的有限窗口再现性”。即使通过，仍须解决耦合残差、全柱条件、全盘状态覆盖及I_nu输出验证，不能据此给整盘光谱交付时刻。
