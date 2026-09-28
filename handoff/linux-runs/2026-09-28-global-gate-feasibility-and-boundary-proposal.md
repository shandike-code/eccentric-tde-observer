# 79878全域收益、剩余两门与半步锚点可行性

79878于2026-09-28 22:04:47–22:35:43在anode19完成，32CPU128GiB，COMPLETED0:0，用时30分56秒。只运行full/half各一张map（139.84/132.50秒），0反馈，0新物质接受，按原协议停在stopped_at_full_half_validation。不是崩溃，未续剩余预算。

Mac独立核327文件、740源码声明、152worker过程回执、两组原参考和逐位trial身份、全部9632频率统计。worker峰3589496KiB，父峰2187067392字节，stderr空；未发现非有限/负强度或越资源。图已目视。没有在Mac重算大数组或算子。

| 指标 | full | half |
|---|---:|---:|
| L2 / 当前q缺陷 | 0.4103386514 | 0.6875779784 |
| L2 / 原79151 x缺陷 | 0.3954252357 | 0.6625885307 |
| Linf / 原x缺陷 | 0.9029503609 | 0.7966990755 |
| 边界L1 | 1.24622677e-8 | 2.38922396e-8 |
| bolometric | 1.07423770e-8 | 2.08082144e-8 |

半步仿射误差/当前raw L2为1.35767e-9。21门19过，仅original_full_boundary_bolometric及original_half_boundary_bolometric失败；原x门为9.84046190e-9。相对当前q，所有11门均过。不能用绝对值很小或当前参考通过取消旧参考失败。

实际主导残差仍有24/25，邻块34出现较大最大缺陷；完整映射使跨区耦合显露。局部L2收益已转化为实测全域收益，这比79747只固定halo的证据更强，但没有正式反馈，不能宣称加热/物质收缩改善。

更关键的设计遗漏是：当前q自身的边界差已经高于原x门约3.14倍，仍用q作为half锚点，又要求full和half都不劣于原x。固定两既有方向的仿射模型下，三角不等式要求|D(q)|≤theta(2S_half+S_full)。盒内通量上界给出右侧最多483313.81，实际为505458.99，缺22145.18；当前真实half的带符号仿射误差仅0.000607。该误差不是所有候选的统一上界，故严格结论仅为本仿射预测模型内不可行，不是完整算子或大气无解。上一轮预注册时没有检查这一必要条件，是数值实验设计遗漏。拒绝记录仍正确保留。

下一步不是重复79878或放宽原阈值，而是单独声明从原x构造候选与half的两方向约束诊断。复用x/q/u及真实后继的六个大场，逐位核34–47与20–33两个不重叠输入支持区；完整Gram矩阵最小化预测残差平方，并要求预测边界差为零。只求一组系数，在第二遍全数组扫描中核有限非负、L2/Linf和边界。此为构造数值初值，不能称物理能量闭合或真实映射。

新作业80005：默认4CPU16GiB，30分钟上限，输入核验与最多两遍扫描，0真实map、0正式反馈、0生产候选dat。源码537e255，Mac33passed，Linux32passed1skipped（Mac接收目录缺失），编译/bash通过。新协议handoff/protocols/boundary-constrained-proposal-v1.md，目录outputs/hpc/step21-boundary-constrained-proposal-20260928。先独立审查预测，才另行声明真实full/half；79878不能原位恢复。

小归档complete-1790606141718302588.tar.gz：3888074字节，SHA45eacab0a9fe7af4033f8080c5952c3155db32f1798f80883500158265e4652f。Mac接收目录outputs/review-20260925/population-defect-global-79878-received；独立审计review_population_defect_global.py，可行性模块defect_boundary_feasibility.py，数值证据在handoff/evidence同日前缀population-defect-global-review和population-defect-boundary-feasibility。

两端pre-defect-global-result-20260928.bundle，Mac automation-before-defect-global-result-20260928.toml，均在outputs/review-20260925。大数组留学校，旧src/scripts/hpc和物理参数未改。未知仍是新组合的真实全域算子收益与正式物质反馈，不给整盘强度完成ETA。
