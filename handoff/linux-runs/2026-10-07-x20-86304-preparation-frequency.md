# 86304 频率组件接入配置与分区求积外层预约

本轮完成另名 frequency context/configuration 接线：已验 stencil、Lorentz rays、planner 实际接入柱运动及认证 header loader 配置。新增 split Gauss 外层逐式预约；leggauss 内部未实现计量。完整准备与生产资格仍关闭。

## 源码与范围

新增 operations/x20_86304_preparation_quadrature.py、frequency_context.py、frequency_configuration.py（后两文件均有 x20_86304_preparation_ 前缀），以及新 runner/reviewer/test。旧源码没有修改。新配置相对旧 motion_configuration 仅标题与 context import 改变，来源七角色认证、原 exact_trial、四 copy/mirror、残差原始头门和所有权逻辑保持。

新 context 复用已验 validate_arrays/motion_arrays，保持原 phase、速度、selected 与 identified_live_bytes 表达式；求积改调新 split_weights，stencil/planner 显式接已验新组件并传递同一 ledger/check。identified_live_bytes 仍是旧规划表达式，不是实测同时存活量或 RSS 界。此次新边界数组为本组件生成，未推广到任意伪造 stencil dataclass。

求积只接受真 Python int 偶数 2..32，split 转 float 后须有限且严格在 (-1,1)。这比原接受 np.integer 的接口更窄，不称全部接受域相同。leggauss 调用前预约两返回数组容量，调用后检查停止；左、右仿射树分别保留乘、加、减/加一、乘 0.5 的原顺序，两角权重及两 concatenate 各先预约。原 _readonly 仅 setflags，没有返回复制；本实现同样不复制。32 方向时共13项、2048 B：leggauss 返回容量256 B、10个128 B仿射结果、两个256 B拼接结果。

leggauss 内伴随矩阵、eigvalsh、legval/legder 递推和 LAPACK/NumPy 私有工作区均未计量；不以2048 B冒称 Gauss 全部闭合。表内预约也不含 Python/ndarray 对象、标量/零维、JSON/ZIP目录对象、searchsorted/NumPy/zlib 私有 workspace、pack和回执序列化。拆表达式可能延长中间变量存活；累计预约不是 allocator 次数、总分配、live 或 RSS 界。单次 NumPy 调用不能检查点中断。

## PRE-RUN 与执行

初始 Mac a18448618114a388a73dd2f0b291f49999f3fb5a、学校 fbfe81fb7ec4e9714e256ec460b483130db5c254，两端 clean；pre-86304-frequency-wiring-20261007.bundle 两端完整 verify。学校生产未同步。freeze01=1765用于新tests前；增加独立reviewer及runner回执字段后 freeze02=1766，后核全部SHA同。源码pack200条含空operations namespace，199条交FrozenModules，实际执行159模块；较宽闭包，不称最小依赖集。

Code：新文件语法检查、源码冻结、旧核不变。Logic：同平台原函数全返回字节对照、停止/预算/域测试，另用标准库审回执。Physics：仅合成几何、运动学和频率覆盖，不计算辐射解或物质响应。Decision：只RUN新tests与97组组合，真实准备/生产DO NOT RUN。

两端各7新tests，Mac1.14秒、学校17.41秒，均无失败/skip/门放宽。求积2/6/18/32方向和三个split同原函数全部数组字节/只读flags对照；18方向每个检查点逐点停止注入，首预算不足前拒，bool/np.integer/奇数/越界/非法split拒绝。97组零/非零速度两相位C/F输入的整个context（含嵌套所有数组、stencil、blocks和selected）同平台原函数对照，输入不改；context只在四组件边界作停止注入，不称全部context检查点逐点注入。配置严格文本变更核及native生产关闭过。原motion/stencil及其他旧tests/组合均未重跑。

新组合97频组、一块、两相位128半列、32方向、4096速度点、零control；没有大辐射场。-I -S、可信环境预载、原StopGuard安装、seal、内存项目导入、配置顺序保持。原120秒/1GiB历史峰检查及外supervise150秒/8MiB输出限实际接新入口；启动/环境/pack仍seal前，本轮未用RLIMIT_AS，也未做耗尽试验。Popen/调度/回收和单次底层调用限制不变。

## 独立回执审阅

标准库reviewer不导入adapter或NumPy，从原NPY字节核七源、四镜像、单位柱、零beta、98个主边界与两套主/局部三网格全部字节、六块索引、配置赋值及精确column/motion/quadrature/frequency预约表。角节点权重各自核0..3阶角矩固定绝对2e-14；两端来源/配置/物质/除mu和weight外context/频率网格索引/meter/模块名相同，不称完整context跨平台逐位同，也不推广非零速度跨平台结论。

11类篡改全部拒：提升完整配置资格、声称leggauss全计量、ledger bool、块bool、缺新模块、缺网格、elapsed bool、65537 chunk、frequency或quadrature容量连总和同步改、坏字节重算SHA。审阅不是allocator追踪证明，也不代替原exact_trial/control/codec/trust内部审计。

七源12728 B，四NPZ解压成员69464 B；累计显式容量15069307 B，其中frequency14636259 B、quadrature2048 B、motion75476 B、column56402 B，其余见independent.json。残差只读4096 B另列。Mac内部1.5503960838541389秒/RSS174260224 B，外1.644854124635458秒；学校内部2.348789364012191秒/RSS149028864 B，外2.5767127000144683秒。只小例观察，不作受控提速或真实预算证据。

学校180夹具文件前后SHA相同；6回执317722 B按外部大小SHA全核后独占收件。reviewer执行版本两端相同，独立审阅实际在Mac对两端原回执执行。读取不存在旧build脚本的命令失败保留于会话；创建pack时先发现元数据应为namespace/package并在执行前修正，runner字段名也在执行前按dataclass修正。没有数值失败或重跑组合。

## POST-RUN 与下一项

synthetic_frequency_configuration_verified=true仅本新合成路径。leggauss_internals_metered/whole_lifecycle_guard_verified/all_scientific_temporaries_metered/complete_native_context_verified/native_loader_metering_integrated/production_resource_stop_guards_integrated/actual_source_manifest_prepared/live_native_recomputed/submission_ready/new_production_authorized/full_scan_authorized=false。0真实343staging/NPZ/native刷新、科学归档payload、dat stat读下载、Slurm/map/反馈/ODE/物质。accepted20/newmaterial0、strictboundfalse和十倍跨支质量门失败保持，HHe未完成。

下一项具体完成原leggauss依赖的逐表达式容量与停止传播：先静态核当前NumPy版本源码，区分可显式预约数组与eigvalsh/LAPACK私有workspace，不能只给返回容量或字段改名；另名实现并只新小合成。然后继续exact_trial/control/codec/trust及JSON/ZIP目录、解释器启动/环境预载实际访问保护。先两端clean/exactHEAD/完整bundle/冻结，不重跑本7项/97组或旧组合。固定真实准备入口的完整计量、停止、访问及源码认证须一起独立验收，再另审首次真实来源预算；首片另立，全301片DO NOT RUN。

证据位于 outputs/review-20260925/20261007-frequency-wiring-*，Mac preparation-frequency-local-20261007、学校 preparation-frequency-fixture-20261007、认证收件 preparation-frequency-school-verified-20261007。学校CLI只接短事实，7.18481666687876秒，实际deepseek-v4-flash[1m]；不是源码/性能审计。草稿未见实质事实错误，独立讲义澄清资源门含义、预约边界及完整准备未完成。
