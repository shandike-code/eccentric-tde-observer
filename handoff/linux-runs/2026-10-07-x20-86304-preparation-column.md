# 86304 原柱几何显式数组结果预约：独立组件

本阶段仅实现原 `_full_column` 的另名组件。未接入已验的 header_configuration，也未完成科学传递调用闭包。真实准备入口仍不可运行。

## 实现与运算范围

新 `operations/x20_86304_preparation_column.py` 保持质量除密度、镜像层宽、原轴 sum、两次独立负号、原轴 cumsum、加法与拼接的数值顺序。边界中面仍用原 2e-15 门。四物质数组按原轴镜像，没有裁剪、归一化或物理参数变化。旧 phase 脚本和全部旧源码不改。

设相位数为 P，半列固定 128 单元，binary64 元素 8 B。逐次 reserve 前调用停止检查；严格累计上限沿用 PayloadLedger 的小于 512 MiB 门。

| 显式数组表达式 | payload 容量 |
| --- | ---: |
| 质量 / 密度 | 128 P × 8 B |
| 全层宽拼接 | 256 P × 8 B |
| 半厚度 sum 结果 | P × 8 B |
| 两次负号，各自 | P × 8 B |
| cumsum 结果、平移加法结果，各自 | 256 P × 8 B |
| 边界拼接 | 257 P × 8 B |
| 中面 abs 结果 | P × 8 B |
| 四镜像，各自 | 2 × 对应输入 nbytes |
| 输入 finite/下界及分数上界掩码 | 每个对应元素 1 B |
| 五输出 finite 掩码 | 每个对应元素 1 B |

验证输入限定精确 ndarray / float64 / 2..2048 相位，正密度、正温度、正面质量，分数在 [0,1]；没有增加分数归一化。输出另检查有限性，以拒绝原中面 NaN 比较可能漏过的溢出。这是额外拒绝门，不能宣称新旧所有非法输入接受域完全相同。正常域原数值运算和中面阈值未变。

容量仅覆盖表内数组结果。NumPy 标量、ndarray/Python 对象、ufunc/reduction 私有工作区、分配器和序列化均不包含；不是实际 allocator 次数、总分配、同时 live 容量或 RSS 上界。停止检查不保证打断正在执行的一个 NumPy 调用。分解命名临时量后在使用结束显式 del，不据此宣称实际内存回收时间或性能改善。

## 新验证

两端完整 pre-86304-column-20261007.bundle verify 成功；Mac 6e5eb177e9874a00b812216d2e8d8e7abaf66501、学校 fbfe81fb7ec4e9714e256ec460b483130db5c254 开始时 clean。学校不生产同步。1751 源码冻结清单运行前后 SHA 相同。

仅新增 8 tests：Mac unittest 0.005 s，学校隔离 pytest 4.01 s。覆盖 C/F/反向视图、原函数同平台逐字节对照与输入不改、独立非均匀 dyadic 层宽累加、全部 30 预约点前停止注入、严格预算拒绝、非法值/shape/dtype、溢出拒绝和生产入口关闭。测试从冻结源码提取单个原函数作对照，不导入原模块或科学来源；这不是生产动态函数替换，也不是单凭源码 AST 已证明完整浮点等价。

新专用三相位、128 半列样例的 6147 输出标量由独立标准库 struct 全字节核对；没有导入新组件或 NumPy。30 项 ledger 的名称、顺序、真整数容量与总和独立重建，总计 84475 B。其中输入掩码 7552 B、数值表达式及镜像结果 70776 B、输出掩码 6147 B。这是该夹具的累计显式预约。

两端 arrays、ledger、checkpoints 和资格字段相同，排除平台名与耗时。Mac 组件内部 0.00018370803445577621 s，学校 0.0009583650098647922 s；不含解释器启动，未记录 RSS，不作提速、耗尽或完整配置资源验收。

学校 7 个夹具源码前后 SHA 同；6 个回执共 100444 B，先取外部大小 SHA 清单，再逐个核字节后独占收件。Mac 独立重新审阅学校回执，不是 Mac 重执行 Linux。6 篡改（资格、bool 检查点、bool ledger、容量、缺数组、坏字节）拒绝。首次坏字节测试误将原本的 00 写成 00，没有实际改变输入；原失败脚本和说明保存，改成 ff 后拒绝，审阅器没有改变。

## 证据和下一项

完整工件在 outputs/review-20260925/20261007-column-*；学校 fixture 为 preparation-column-fixture-20261007，认证收件为 preparation-column-school-verified-20261007。freeze-01、school-pins、school-receipt、independent、原失败记录及两端 tests 日志保留。独立回执验证仍不能证明内部每次分配均已覆盖。

本轮没有运行旧 headers18/129 组合或其他旧测试；0 真实 NPZ/native 刷新、343 staging、科学归档 payload、dat stat/读/下载、Slurm、map/反馈/ODE/物质计算。accepted20/newmaterial0、strictboundfalse 和十倍跨支质量失败不变。

下一项应将此组件接入另名 context/配置路径，同时逐式补相位差/除法/平均/repeat，再审核 Gauss/stencil/planner 与 exact_trial/codec/trust 的传递闭包。当前 validate_arrays 其他路径、JSON/ZIP 目录、解释器启动/环境预载实际访问保护也尚未闭合。不可把本局部组件当完整准备资格；所有真实来源刷新及全 301 片仍 DO NOT RUN。

学校 CLI 首次 5.3062514159828424 s 只返回工具调用标记，无可用讲义，未执行这些标记。第二次 3.3895237911492586 s 返回短事实草稿，实际模型 deepseek-v4-flash[1m]；独立核对并补充新输出有限拒绝门的范围，不冒源码或性能审计。两份原稿及 cli-review 保留；讲义 185 仅追加，旧前缀大小 SHA 另存。
