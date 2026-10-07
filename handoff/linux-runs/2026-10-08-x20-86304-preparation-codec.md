# 86304：解码依赖显式数组预约的独立小合成验收

日期：2026-10-08。进入时 Mac 678870e7fd4ffa179b557c1909168749d0dda3e0、学校 fbfe81fb7ec4e9714e256ec460b483130db5c254，两端 clean；学校无生产同步。两端 pre-86304-codec-20261008.bundle 完整 verify。

## 范围与原定义

静态实读 common_step21_directions.exact_trial、GroundStateLogSimplexCodec.decode、_thermal_coefficient_erg_g_k、ground_state_material_trial_within_trust_region，以及 radiation_matter_feedback 的 _population_arrays、_composition_per_gram 和 ground_state_material_specific_energy_erg_g。原 control 身份检查先 decode 一次，trust 再分别 decode current/trial，共三次，不能因 control 数组相同省略。

新增 operations/x20_86304_preparation_codec.py，仅实现另名 decode 及其热系数、布居验证和比能依赖。旧科学源码、memory/configuration 接线不改；无生产 monkeypatch/FunctionType。原 codec 对象和返回 dataclass 保留。接受精确 float64 ndarray、真 Python int 的 1..128 cells；比原 ArrayLike 接口窄。测试覆盖默认 solar composition，不认证任意伪造 composition 或对象拓扑。

第一编码是气体热比能的对数。氢按 log-ratio 正负分支恢复，氦按减去最大 score 后的指数及原行和恢复。能量仍是气体热能加基态电离比能 erg/g，不含辐射能。尤其保留 (1.5*k*T)*(nuclei+electron) 的原乘法树，不换为预计算 coefficient*T。原 decode 严格正布居门、energy 再验有限/非负/simplex 门、温度与能量正性门均保留。原返回内能 copy 加 decode 返回 copy 两次均计。

## 逐式容量与检查范围

新函数每个命名数组结果在创建前 check/reserve；两次布居原地赋值和每次 setflags 前另 check。限定 f64 后 asarray 不复制；reshape、列切片和 column_stack 内部扩维为视图。正分支 selection/负号/exp/加一/除法五个 p 元素数组；负分支 selection/exp/加一/除法四个 q 元素数组，两个独立反 mask 保留。count_nonzero 是新增标量容量计数，不改原数值输出。

| 表内结果族 | 覆盖 |
| --- | --- |
| 输入与物理门 | finite、正性、负性、sum/subtract/abs/tolerance masks，保留短路顺序 |
| H/He 解码 | 热能 exp、empty、分支选择、分支算术、stack、max、shift、exp、sum、除法 |
| 热系数 | 两种粒子数乘法、He 双电离乘二及相加、电子数相加、总粒子数、系数 |
| 比能 | 再算电子数、原 gas 乘法、电离三项及原相加树、total |
| 所有权 | energy 内 copy 和最终四数组 copy，只读设置 |

合法成功路径 77 项、85 检查点。令 n 为 cells、p 为非负氢 log-ratio 数量，预约数组 payload 为 533*n+8*p 字节；这是表达式结果容量求和，不是 allocator 次数、总分配、同时 live 或 RSS 上界。七单元 p=4 为 3763B。命名中间量可能延长存活。Python/ndarray/闭包/列表对象、NumPy 标量与零维结果、reduction/ufunc/advanced-indexing 私有 workspace、导入及序列化不包含；单个 NumPy 调用不能由 check 中断。

## 新验证与证据

运行前 freeze-01 核 1782 个 py/sbatch（旧1778加新4），结束全部 SHA 相同。四新文件为组件、test、exercise、标准库 reviewer。两端仅各6项新 tests：Mac 0.82s，学校14.40s；没有失败、skip、门放宽。cells1/7/19/128，混合/全正/全负氢分支、步进向量和反序单元，对原函数全部返回 dtype/shape/bytes/readonly、输入不改及输出隔离核验。85 检查点逐点停止且 ledger 前缀相符，每非零容量预约点预算少1拒绝；非有限、溢出、下溢到边界与原异常类别相同。不是任意输入全等价证明。

另七单元小例，不读科学文件、不分配辐射场。标准库 reviewer 不导入 NumPy/组件，用固定输入标量公式、struct 原字节核49标量，预定相对3e-14、绝对0；精确手列77项表及总和/检查点真整数。两端最大相对误差均3.0856710715930516e-16。十类篡改资格、bool检查数/elapsed/ledger/shape、容量连总和同改、缺数组、全零坏字节均拒。篡改使用副本，原回执不改。

学校隔离 fixture 182文件前后 SHA 同；由上阶段较宽源码 pack 部署所需文件，不代表此次内存封锁导入认证或最小依赖闭包。测试普通子进程 timeout60s，小例和review各30s；没有 -I-S/seal/StopGuard/supervise/RLIMIT_AS/RSS测量或耗尽实验，不借旧组合资源资格。reviewer 两端同版执行，Mac 收件后另审两原回执。

六工件4172B先取学校外部大小SHA清单，全核后独占写 preparation-codec-school-verified-20261008。学校 preparation-codec-fixture-20261008。两端 H/温度/能量 bytes 同，He 两元素不同、最大绝对差1.1102230246251565e-16；各自同平台原函数及标量门过，不称全跨平台bytes同。内部仅decode Mac0.00017312541604042053s、学校0.000633048010058701s，不含导入/整个tests；不是性能或真实预算证据。

## 剩余接线与决定

本次 synthetic_codec_explicit_arrays_verified=true；exact_trial_integrated/configuration_integrated/all_scientific_temporaries_metered/whole_lifecycle_guard_verified/production_authorized=false。原配置仍走原 exact_trial。

下一项基于此组件实现另名 trust 和 exact_trial(control)，实际调用三次 decode。trust 保留原参数域及温度差/abs/除法、比能差/abs/除法、H与He差/abs、原max比较。身份路径还需 split_direction 的有限mask/copy、各 array_equal 比较mask、base+alpha*direction 两次数组结果、七类身份字段及原phase/old/dt门。随后四copy/mirror接另名配置；不可仅两端check或trial/base相同冒内部完成。只新小合成，先两端clean/完整bundle/冻结，不重跑本6tests/七单元例或旧113组合。

原生私有workspace、JSON/ZIP目录与启动/环境访问保护仍未闭合。真实准备需完整独立验收后另审一次来源预算，首片另立；全301 DO NOT RUN。此次0真实343staging/NPZ/native刷新/科学归档payload/dat stat或读取/Slurm/map反馈ODE物质。accepted20/newmaterial0/strictboundfalse、十倍跨支质量失败保持；HHe未完成。

完整脚本、freeze、pins、学校原回执与收件、independent/parity 见 outputs/review-20260925/20261008-codec-*。学校CLI仅短事实讲义，见同日前缀 cli-draft/cli-review，非完整源码或性能审计。

文档辅助脚本首轮在 normalize_document 返回字符串被误作二元组解包处失败；当时报告和讲义已写。保留原脚本，另名 finish 仅续做格式、前缀与证据检查，无重复追加或数值重跑。CLI实际15.519808083306998s、deepseek-v4-flash[1m]，仅短事实，无实质事实错；同平台/85检查点范围及预约非RSS等澄清另存。
