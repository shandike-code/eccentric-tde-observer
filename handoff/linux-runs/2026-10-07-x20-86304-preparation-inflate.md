# 86304：分块解压组件与 Linux 地址空间限制小合成

本阶段新增 `operations/x20_86304_preparation_inflate.py`，两端小合成通过。它替换候选解码路径中的 ZipExtFile 为显式 raw-DEFLATE 分块调用，但尚未接入已验配置组合。Linux 地址空间限制也只是独立组件。完整科学临时量计量、解释器启动/环境访问保护和固定真实准备入口仍未完成，不授予真实来源刷新或生产资格。

## 来源与执行范围

开始时 Mac 为 `77b7b2b8d54d0c52548ea2565a7ddcab8741bd70`、学校为 `fbfe81fb7ec4e9714e256ec460b483130db5c254`，均 clean。两端 `pre-86304-inflate-20261007.bundle` 完整 verify。学校生产 checkout 未同步，五文件只部署隔离 fixture，前后 SHA 相同。Mac freeze01 为 1740 源，新增 exercise/reviewer 后 freeze02 为 1742，结束全部 SHA 同。没有修改旧科学源。

只新增小 NPZ/NPY 字节和小子进程；没有真实 NPZ/native 刷新、343 来源 staging、科学归档 payload、真实 dat stat/读取/下载、Slurm、map、反馈、ODE 或物质演化。旧配置21及专用合成、context25/memory21/boundary15/inputs50/resource114/supervisor18及8cases均未重跑。

## 新解码器的实际范围

接受单盘无注释 ZIP 的窄子集：stored 或 raw-DEFLATE，ASCII 普通成员、无路径、无重复、无数据描述符、无中央 ZIP64、无额外尾部；允许 NumPy seekable writer 的局部 ZIP64 双大小。真实来源格式兼容性没有被认证。压缩源严格小于32MiB，单源声明解压严格小于128MiB，累计显式 payload 容量预约严格小于512MiB；参数只能收紧。

先完整核中央/局部目录和每成员范围，再预分配固定长度输出。每次原生解压调用前预约输入片、返回上限和暴露尾部容量，单次输入及返回均不超过65536B；实际循环检查停止、长度越界、无进展、EOF、CRC 与尾随流。每个完整成员先核 NPY 头，全部完成后才建立只读 frombuffer 数组并核有限性。没有改原浮点运算或生产 monkeypatch。

| 表达式或阶段 | 本新 ledger 是否覆盖 | 检查点及边界 |
| --- | --- | --- |
| `bytearray(size)` | 调用前预约 size | 目录已核，单源解压总声明上限 |
| `raw[start:stop]` | 切片前预约实际片长 | 循环入口停止检查，片长至多65536 |
| `decoder.decompress(pending, allowance)` | 调用前预约 allowance 加两倍 pending 长度 | 返回长度/声明大小/unused_data/停滞核；不假称能抢占原生调用 |
| `bytes(output)` | 复制前预约 size | 完整长度/EOF/CRC 已过 |
| `np.isfinite(a)` | 调用前预约元素数个 bool payload | 数组循环入口停止检查 |
| zlib 私有 native workspace、分配器开销 | 未逐项计量 | 本 ledger 不提供总分配或 RSS 上界 |
| ZIP/NPY 名称、头、AST、字典、BytesIO 潜在复制 | 未完整预约 | 单源/成员/NPY 头结构上限存在，不能冒充完整容量审计 |
| 原 exact_trial 的 direction、乘法/加法、codec.decode、trust-region | 未接此 ledger | 旧实现不改，不能由只读视图推出无临时量 |
| 原四次 copy 与四次 mirror | 旧 ArrayLoader 有各自预约；本新组件未接线 | 不把旧账和新账自动合并 |
| `_full_column` 的 mass/rho、拼接、sum、两次负号、cumsum、加法、edge/四镜像及 abs | 未接此 ledger | 输出 shape 已有旧验证，未推导所有 native 临时工作区 |
| `_context_arrays` 的 roll、差、dt乘c、除法、abs/argmax、相邻face加法/乘0.5、repeat、active-edge copy | 未接此 ledger | 原 context 只在整段前后有合作检查 |
| Gauss 求积、stencil、block planner 及其传递调用 | 未完成逐表达式分配审计 | 原 identified_live_bytes 仍仅规划表达式值 |

该表明确覆盖与未覆盖的表达式族，不是科学依赖闭包全部表达式的完成清单。新字段 `explicit_payload_capacity_reserved_bytes` 表示本条累计容量预约，重复调用不释放额度；不是实际 allocator 次数、设备 I/O、同时 live 字节或 RSS。

## Linux 独立限制

`install_address_space_limit` 仅 Linux，最大1GiB，并取既有有限 soft/hard 的更小值，不能放宽已有上限。设置及读回 RLIMIT_AS 约束未来虚拟地址空间增长，含 C 库映射/分配可能请求的地址空间；不是 RSS 计量，也不是文件访问保护。组件的 Python 导入发生在安装前，尚无 exec 前安装接线，不能说解释器启动已受保护。Mac 没有执行这个 Linux 成功路径。

学校一个独立标准库子进程设置48MiB即50331648B后，16384B bytearray 成功，67108864B 匿名 mmap 请求以 errno12 被拒。没有实际分配64MiB物理页或测试1GiB/RSS耗尽，也没有在该限额下执行 NumPy/native 配置；这不认证未来真实配置可在1GiB地址空间中完成。

## 验证与独立审阅

两端各19新 tests：Mac0.010秒、学校0.025秒，无失败/skip/断言放宽。核 stored/deflate、多次高压缩输出、SHA、CRC、大小、截断/尾随流、停止、预算拒绝、成员名/重复、Fortran/object/非有限及生产入口关闭。预算测试用宽异常捕获，另核 ledger 没有成功预约条目；它没有单独认证异常类型。标准库 zipfile 只在测试 oracle 中出现。

新专用 fixture 从标准库独立构造257×32个 binary64：第 i 项为 i mod 17。数组65792B，NPY成员65920B；stored源66036B、deflate源523B。各两次解码调用，预约分别403745B/207214B。两端完整 results 相同；Mac内部0.0522221662秒、学校0.0779920720秒，仅小例，没有记录本次 RSS。fixture 构造与 oracle 不计入 decoder 的 ledger。

独立 reviewer 不导入解码器，从标准库 struct 重建数组全部字节，核两种压缩方法、事件及资格范围；五种篡改（生产资格、缺case、数组SHA、bool调用数、65537B返回上限）均拒。它不声称凭回执证明 zlib 内部每个分配。学校四小回执4106B先按返回的外部大小SHA核，再独占写入 Mac 收件目录；学校原件保留。

## POST-RUN 与接续

代码及小样例层面通过，没有科学趋势或守恒计算可在此评估。accepted20、新物质步0、十倍跨支质量失败及所有生产资格 false 保持。新解码组件的成功不能补写旧配置组合已全面计量。

下一项接续实现：补头解析/BytesIO 等可预约路径，完成原科学运算逐表达式容量范围和检查点，实际组合新 loader、固定入口、StopGuard/supervise；再实施解释器启动及环境预载的实际访问保护，学校 Linux 平台范围单独审阅。不得只凭 RLIMIT_AS、origin 或 -I -S 宣称访问闭合。完整准备验收前仍无真实来源刷新资格；首片预算另立，全301片 DO NOT RUN。

证据索引：`outputs/review-20260925/20261007-inflate-*`；Mac `preparation-inflate-local-20261007`，学校 `preparation-inflate-fixture-20261007`，Mac收件 `preparation-inflate-school-verified-20261007`。小审计和讲义草稿/独立纠错在 `handoff/evidence/20261007-86304-preparation-inflate-*`。
