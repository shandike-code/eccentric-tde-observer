# 86304：trust 与 control 身份路径显式数组预约

日期：2026-10-08。进入时 Mac 9e19bc5d7d7508f58dae1dee5e3db8680cc483ac、学校 fbfe81fb7ec4e9714e256ec460b483130db5c254，均 clean。两端 pre-86304-trust-20261008.bundle 完整 verify；学校生产未同步。

## 实现范围与原定义

新增 operations/x20_86304_preparation_trust.py、exercise、标准库 reviewer 和新 test。静态复核原 common_step21_directions.split_direction/exact_trial、ground_state_material_trial_within_trust_region 及当前 NumPy array_equal 的 equal_nan=False 路径。使用上一阶段已验另名 decode，保留原 control 身份一次 decode、trust current/trial 各一次，总计三次。旧科学源码不改，无生产 monkeypatch/FunctionType。

trust 保留原三限制参数 float 转换、有限性及严格 (0,1) 域。分别按原树计算温度差/abs/除以当前温度、总物质比能差/abs/除以当前比能、氢和氦布居差/abs/max，最后以原 <= 门判定。温度 K、比能 erg/g；两相对变化无量纲，布居为绝对分数变化。第一编码仍是气体热比能对数，不能当温度对数。

exact_control_trial 仅 control，先限定真 float64 ndarray、1..128 cells、phase 为 int64 零维、old 的相位数 1..4096。接受域比原函数窄；元数据错误的拒绝顺序不宣称完全相同。保留 residual finite 和方向 copy、原 relaxation/base/r20/direction 门、base+0*direction 两次数组运算及原列表先求值顺序、trial 四比较、密度/phase/dt、old 和解码后四物理数组门。array_equal 展开为相同 shape 上的 == mask 和 all，保持数值相等含正负零，不冒字节身份门。标量 phase/dt 比较结果各预约 1B；对象开销仍不计。

本次未接四 copy/mirror 或 configuration，native_configuration 无条件拒绝。旧配置仍调用原 exact_trial，不以本组件通过冒配置整合通过。

## 容量与停止边界

每个表内结果创建前 check/reserve，复用 decode 原赋值/setflags 检查点。control 成功路径 260 项、286 检查点。n 为 cells、p 为非负氢 logratio 数，累计 payload 容量为 1864*n+24*p+2 B；十一单元 p=5 为 20626B。三次 decode 占 1599*n+24*p，身份与 trust 其余占 265*n+2。单独 trust 包含两次 decode 和十个差/abs/除法结果，十一单元 164 项、181 检查点、13214B。

预约是累计表达式结果容量，不是 allocator 次数、全部分配、同时 live 或 RSS 界。Python/ndarray/列表/闭包对象、未列标量与零维、NumPy reduction/ufunc/索引私有 workspace、导入及序列化不计。拆变量可延长存活，单次 NumPy 调用不可检查点中断。三次 decode 的分支容量分别实际预约，不省略重复调用。

## 新验证、失败与独立审阅

两端仅各 6 项新 tests，Mac 最终 1.07s，学校 26.65s，无 skip 或门放宽。3/11/29/128 cells 原 control 对照和输入 bytes 不变；3/11/29 各编码分量非零 trust 扰动及 stride 输入对原函数判决；各身份字段篡改、三限制非法域、非有限/溢出下溢异常类别及生产入口拒绝。默认 composition，未认证任意伪造 codec/composition 拓扑，也未给全部非法输入等价证明。

新十一单元 control 对全部 286 检查点注入停止，核对应 ledger 前缀；每非零预约同时测试上限等于累计容量及少 1B。原 Budget 要求 used < limit，等于即拒。首 Mac 5 过 1 失败：测试误把少 1B 都预期拒在当前预约，遇相邻 1B 时实际前一预约已触及严格上限。保留首次测试和日志，按固定严格比较独立累计预期前缀后通过；组件及预算器没有修改。freeze-01 是首次测试版本，freeze-02 是最终版本；各有 1786 份 py/sbatch，最终版本结束全 SHA 同。

新 fixture 是十一单元 control、小扰动 ln(gas thermal energy)+0.03125、大扰动 +1。标准库 reviewer 不导入 NumPy/组件，手列完整 ledger、核真整数总和/检查点/elapsed 类型；另用 math 的标量热系数和电离能公式独立求判决。control 和小扰动通过，大扰动拒绝。独立标量小扰动温度相对变化 0.0317434074991028、比能 0.006583513500384446；大扰动分别 1.7182818284590458、0.3563679045938974；布居不变。这里审阅的是判决与回执，不是内部数组逐字节或每次分配的独立追踪。

11 类回执篡改资格、bool 检查点/elapsed/ledger、容量连总和同改、缺 case、错误判决、整数冒 bool 全拒。两端三 case 除 elapsed 外全部回执字段同；不冒内部数组跨平台逐位同。原 decode 阶段已记录 He 跨平台末位差，本次未重跑旧夹具。

学校 preparation-trust-fixture-20261008 隔离部署 183 源文件，前后 SHA 同，来自旧宽 pack 加 codec 和四新文件；不是本轮封锁内存导入或 actual origin 认证。普通 tests timeout60s、fixture/review 各30s，无 -I-S/seal/StopGuard/supervise/RLIMIT_AS/RSS耗尽，不借旧资源资格。reviewer 两端同版执行；Mac 再独立审两端原回执。六回执 20821B 外部大小/SHA 全核后独占写 preparation-trust-school-verified-20261008。

control 内部 Mac0.00038404110819101334s、学校0.0010840329923667014s，仅微例不含导入，无性能或真实预算资格。完整 freeze/pins/学校脚本/原失败/tests/收件/independent 在 outputs/review-20260925/20261008-trust-*。

## 决定与下一项

synthetic_trust_control_component_verified=true，仅独立组件。configuration_integrated/all_scientific_temporaries_metered/whole_lifecycle_guard_verified/complete_native_context_verified/native_loader_metering_integrated/production_resource_stop_guards_integrated/actual_source_manifest_prepared/live_native_recomputed/submission_ready/new_production_authorized/full_scan_authorized=false。

下一项把已验 exact_control_trial 接另名 trial_and_mirrors/configuration，保留原四 copy 先完成、再四 mirror 顺序；移除被新内部比较预约替代的旧重复计量，不能把原数值相等门换 bytes 门或省三 decode。先静态列原配置布局兼容性，核两端 clean/exactHEAD、完整 bundle 和冻结，只新小合成及逐点停止预算，不重跑本 6 项/十一单元或旧113组合。

原生私有 workspace、JSON/ZIP目录、解释器启动和环境实际访问保护尚未闭合。完整准备独立验收后另审首次真实来源预算，首片另立，全301 DO NOT RUN。此次 0 真实343staging/NPZ/native刷新/科学归档payload/dat stat读下载/Slurm/map反馈ODE物质。accepted20/newmaterial0/strictboundfalse 与十倍跨支质量失败保持；HHe未完成。

学校 claude -p 无工具短事实讲义耗时12.023458041716367s，实际 deepseek-v4-flash[1m]；不是源码或性能审计。草稿“别名”澄清为另名实现，“温度扰动”澄清为第一编码气体热比能对数扰动；测试尺寸与286停止点适用范围单列。原稿与独立纠错保存于同日前缀 cli-draft/cli-review。
