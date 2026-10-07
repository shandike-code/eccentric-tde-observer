# 86304 柱几何接线与运动数组预约

本阶段只新增另名准备路径。已验 `full_column` 现接入 `x20_86304_preparation_motion.context_from_arrays`，再接另名 `motion_configuration`。旧科学源、旧配置与数值门不改。真实来源准备、完整科学计量和启动保护仍未完成。

## 范围与实现

新验证器在有限/正值/分数域 mask、频率差分及递增 mask 创建前预约。配置与 context 各执行一次验证，ledger 如实包含两次；柱组件自己的验证另计。运动部分保留原 roll、边界减法、dt 乘光速后除法、abs/argmax、相邻相加再乘 0.5、16 次 repeat 顺序。位移 cm 除以 dt*c 的 cm 得到无量纲 beta。输出非有限额外拒绝，不能宣称全部非法输入接受域与旧核相同。

argmax 完整连续输入容量是潜在复制预约，未测其实际复制。Gauss 仅预留两个返回数组容量；内部 leggauss、stencil、planner、exact_trial/control/codec/trust 临时量尚未闭合。JSON、ZIP 目录对象、Python/ndarray 对象、NumPy/zlib 私有 workspace、环境 pack 和序列化仍不全部计量。累计预约不是 allocator 次数、实际总分配、同时存活量或 RSS 上界；检查点不能中断单次底层 NumPy 调用。identified_live_bytes 仍是原规划表达式，不是本次分配观测。

配置相对 header 配置仅改文档标题、context 导入及 ledger 参数传递，七角色大小/SHA、原 exact_trial、四 copy/mirror、原 residual 头门、来源绑定和频率所有权保持。没有生产 monkeypatch/FunctionType，native_configuration 无条件拒绝。

## PRE-RUN 与验证

两端 clean/exact HEAD：Mac 273fd76a2f19d65187f5f52d14caf00336a19de1；学校 fbfe81fb7ec4e9714e256ec460b483130db5c254。两端 pre-86304-motion-20261007.bundle 完整 verify。1756 源码冻结后仅运行新测试及新 65 频组组合，不重跑旧套件和旧夹具。Code/Logic 通过，Physics 仅允许小合成，真实来源及生产 DO NOT RUN。

两端各 6 新 tests：Mac 0.010 秒，学校 16.23 秒。三相位非零速度样例层宽 1/2/4，独立标量原表达式字节核选中相位、face/parent/repeat；C/F 同平台原 context 对照、每预约点停止、严格预算、非法域和生产关闭通过。首 Mac 6 项中一项失败：oracle 代数化简给中面 -0.0，原减法为 +0.0；恢复原减法顺序后通过，组件与门未改，首源码/日志保留。首轮 shell 未在测试失败处停止，因此新组合在首轮失败后也执行成功；不追写为先通过 tests 才执行组合。之后修的是 oracle 与 reviewer，未重复组合。没有单独的非零速度跨平台全输出比对声明。

新组合为两相位 128 半列、65 频组单块、零 control，不分配大辐射场。-I -S、可信环境预载、StopGuard 安装、seal、冻结内存导入后配置。120 秒/1 GiB 历史峰检查与外层 150 秒/8 MiB 接此新入口；未实施解释器启动/预载的全生命周期保护，未安装 RLIMIT_AS。本通用监督器仍有 Popen、调度、回收延迟限制。

pack 196 项含空 namespace，195 交 FrozenModules，实际执行 156 项目模块；较宽闭包不是最小闭包。源码 bytes/loader/file/spec 核过，学校逻辑 root 是隔离 fixture 路径。学校 176 文件前后 SHA 同。最终 reviewer 修正后仅在 Mac 审两端原回执，未部署学校、未重跑执行。

标准库 reviewer 不导入 adapter/NumPy，从原 NPY 字节核四镜像、柱边界、零 beta、66 频率边界、单块、配置赋值、逐项 column/motion ledger。四阶角矩（0 至 3）固定绝对 2e-14。两端除 mu/weight、平台/时钟/RSS/origin 根等外，配置、来源、物质、其他 context、meter 及模块名相同。不能称全 context 逐位同。

reviewer 首次复制时把柱边界 stop129 误改65，随后遗漏删除已不执行旧 context 的必需模块条件；两版源码保留。另一次调用误传学校生产 root，origin 门正确拒绝，改为外部收件 manifest 的实际隔离 root 后过。执行源码、来源与门未放宽。8 篡改资格、ledger bool、motion/column 容量（同时修总和）、缺模块、phase bool、beta SHA、65537 chunk 全拒。

## 量级与 POST-RUN

七合成源 12682 B，四 NPZ 解压成员 69208 B，显式累计容量 429614 B，其中 motion 75028 B、column 56402 B；其余解压/头 token/finite/比较/copy/mirror 项完整在 independent JSON。残差只读视图 4096 B 另列。6 学校小回执 305820 B 经外部大小 SHA 核后独占收件。

Mac 子进程 0.8932330422103405 秒、历史峰 RSS 182812672 B，外层 0.9611257910728455 秒；学校子进程 2.479518434003694 秒、145096704 B，外层 2.8245979249768425 秒。仅小合成，不是耗尽测试、提速证据或真实入口可行性保证。

0 真实343 staging/NPZ/native 刷新、科学归档 payload、dat stat/读/下载、Slurm/map/反馈/ODE/物质。header_configuration_column_integrated 与 synthetic_motion_configuration_verified 仅本路径为 true；whole_lifecycle_guard_verified/all_scientific_temporaries_metered/complete_native_context_verified/native_loader_metering_integrated/production_resource_stop_guards_integrated/actual_source_manifest_prepared/live_native_recomputed/submission_ready/new_production_authorized/full_scan_authorized 全 false。accepted20/newmaterial0/strictboundfalse 及十倍质量失败保持，HHe 未完成。

下一项具体处理 Gauss/stencil/planner 及 exact_trial/control/codec/trust 的逐表达式容量与停止闭包，保留原数值顺序，另名小合成，不重复本 6 项或 65 组合。JSON/ZIP 目录及解释器启动/预载访问保护仍须实现，不能仅 origin/-I-S/RLIMIT_AS 冒闭合。全部准备独立验收后另审首次真实来源预算，首片另立，全301 DO NOT RUN。

证据位于 outputs/review-20260925/20261007-motion-*，两端回执目录 preparation-motion-local-20261007、preparation-motion-school-verified-20261007；源码 freeze04 与 validation/independent/receive、原失败源码及日志保留。

学校 CLI 7.646659750025719 秒，实际 deepseek-v4-flash[1m]，仅给定短事实讲义，不是源码或性能审计。独立复核无实质事实错误；将“8 处”明确为 8 类回执篡改，计数零项按本轮范围解读。讲义186旧前缀大小 SHA 核不改，新文 normalize/diff 通过，无图。
