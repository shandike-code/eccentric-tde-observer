# 86304 频率模板、Lorentz 变换与频块规划的独立预约组件

本阶段新增 `operations/x20_86304_preparation_stencil.py`，保留旧科学源，尚未接入 motion/context/configuration。完成的是新独立频率组件的小合成验证，不是完整准备或生产验收。

## 实现范围

stencil 保留原 gamma、Doppler 上下界、128 epsilon 裕量、碰撞与外层边界拼接、三份只读返回复制。列表转数组的潜在容量也预约。验证的 finite、diff、正频率与递增 mask 在创建前预约；零速度分支保持独立复制。新增正频率和输出 finite 拒绝，不声称全部非法接受域与旧核相同。

Lorentz 路径保留 D=gamma*(1-beta*mu)、像差 (mu-beta)/(1-mu*beta)、角权重 weight/D**2、原轴向 sum 与角测度误差计算。原两次乘法/分母独立计算没有合并。gamma 的平方、相减、开根、倒数，以及各广播乘除、mask、返回复制均逐项预约。拆开的中间变量可能延长数组存活，不声称与原函数具有相同内存生命周期。

planner 显式调用新 Lorentz 函数，原 `_covering_group_slice` 保留，两次边界查询间检查停止；每块三份边界复制先预约。core 为真 Python int 1..128；角度最多32、速度最多4096、物理组最多9632。planner 限连续边界，避免跨步边界搜索的潜在连续复制；该接口仍以本组件生成的 stencil 为前提，未认证任意外部伪造 dataclass 的完整拓扑或底层对齐接受域。

累计预约只覆盖表内显式数组结果及声明的列表转换容量。Python/ndarray 对象、标量和零维操作、searchsorted/NumPy 私有工作区、序列化不计，不是 allocator 次数、总分配、同时存活量或 RSS 界。检查点不能打断单次 NumPy 调用。本轮没有 Gauss/leggauss 内部实现，没有 exact_trial/control/codec/trust 接线，也没有新增启动访问保护。

## PRE-RUN 与执行

Mac 初始 HEAD 865f15a29ea805af4b1fce03cee413fda65776bc，学校 fbfe81fb7ec4e9714e256ec460b483130db5c254；两端 clean，pre-86304-stencil-20261007.bundle 完整 verify。先查重再新增四文件，freeze01/02/03保留；1760源码最终SHA核同，旧源码不改。freeze02 是数值执行前版本，freeze03 仅加严独立审阅器的 input 数目、shape 真整数和 elapsed bool 检查。

Code：显式容量预约在运算前，固定规模；Logic：原树同平台字节对照，加独立标量与 bisect oracle；Physics：只检验运动学变换和频率覆盖，不是辐射解或物质响应。决定仅 RUN 新测试和新小例，真实准备/生产 DO NOT RUN。

Mac 新7tests 1.16秒，学校新7tests 14.76秒，无数值失败、skip或放宽断言。覆盖零/非零速度原函数字节对照、反stride及输入不变、每个预约点停止注入、预算在首数组前拒、非法域、护卫范围不足、bool core、planner跨步边界拒和生产关闭。非预约检查点有执行计数，未逐一单独故障注入；不冒称每个检查点均已注入。未重跑旧 suites 或旧组合。

新专用样例仅9频组、4方向、3速度(-0.125,0,0.125)，stencil 最大 beta 0.25，core4得到3块；无大辐射场。fixture单独调用一次 rays，再由 planner 调用一次，ledger如实含两次。普通子进程测试timeout60秒、fixture/review各30秒；不是前阶段-I-S/seal/StopGuard/supervise配置组合，未安装本组件RSS上限，未测RSS，不借用原120/150秒与1GiB保护资格。

## 独立审阅与量级

独立 reviewer 只用标准库，不导入 NumPy 或组件；从 struct 原字节核输入、护卫边界和各块边界，Python标量核 Doppler、像差、角权重及测度误差（预先固定绝对2e-14），bisect重建块索引。共150标量、100条具名真整数容量记录、110检查点，累计4633B。标量容差不是完整算法严格舍入界。

两端除 platform/elapsed 外整个fixture结果相同，包括全部数组字节与ledger；此结论只限本样例。Mac内部0.000293792225420475秒、学校0.0010984439868479967秒，不含解释器启动，不能作提速或真实资源预算证据。学校174个fixture源码文件前后SHA相同，5回执10355B外部大小SHA核后独占收件。最终审阅器只在Mac审两端原回执，未部署学校、未重跑数值执行。

8类篡改：提升资格、check bool、ledger bool、容量及总和同时改、块索引bool、数组坏字节并重算SHA、缺输入、elapsed bool，全部拒绝。实施过程中一次读取不存在的旧 receive 脚本路径失败，随后另写新收件脚本；没有因此重跑计算或改门。

## POST-RUN 与后续

新 synthetic_frequency_component_verified=true；configuration_integrated=false。原 motion 配置已验资格只属原路径，本组件未取代其中原stencil/planner。whole_lifecycle_guard_verified/all_scientific_temporaries_metered/complete_native_context_verified/native_loader_metering_integrated/production_resource_stop_guards_integrated/actual_source_manifest_prepared/live_native_recomputed/submission_ready/new_production_authorized/full_scan_authorized 均 false。

下一项先将本组件接另名 motion/context/configuration，补 Gauss/leggauss 逐式容量和停止传递，再处理 exact_trial/control/codec/trust；JSON/ZIP目录及启动环境实际访问保护仍未闭合。保持原表达式，新增小合成，不重跑本7tests/9组样例或旧组合。固定真实入口全部独立验收后另审首次真实来源预算，首片预算另立，全301 DO NOT RUN。

本轮0真实343 staging/NPZ/native刷新、科学归档payload、dat stat/读/下载、Slurm/map/反馈/ODE/物质。accepted20/newmaterial0/strictboundfalse和十倍质量失败保持，HHe未完成。

证据：outputs/review-20260925/20261007-stencil-*；Mac preparation-stencil-local-20261007、学校 preparation-stencil-fixture-20261007、收件 preparation-stencil-school-verified-20261007。完整freeze、原执行回执、school脚本/pins、receive和independent均保留。

学校CLI实际8.5505658746697秒，deepseek-v4-flash[1m]，只审给定短事实，不是源码/性能审计。纠正“将实现”为已实现、“三个组件”为一个模块三条路径、“接口重命名”为另名实现及逐式预约；新频率尚未接motion，不否定已有motion配置。讲义187旧前缀SHA保持，无新图。
