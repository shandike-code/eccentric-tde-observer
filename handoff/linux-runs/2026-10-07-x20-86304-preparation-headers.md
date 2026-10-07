# 86304：有界 NPY 头解析及新 loader 配置接线

本阶段新增直接字节头解析器和另名配置函数，两端新小合成通过。它把已冻结分块 ZIP 解码器实际接入七角色配置、原 exact_trial、四 copy/mirror 和原 context，并接原 StopGuard/supervise。完整原科学临时量计量、解释器启动及环境预载访问保护、固定真实准备入口验收仍未完成。HHe 未完成，不产生真实刷新或生产资格。

## 实现与保持的门

`operations/x20_86304_preparation_headers.py` 不构造整成员 BytesIO，不建立 Python AST。不可变 bytes 上的游标只接受三键字典、短 ASCII 字符串、True/False 和无符号维数元组：头最多16384B、token最多16字符、至多8维、每维最多9位且小于128MiB、标点计数最多64。拒表达式、重复/额外键、负数/bool维数、前导零、对象/结构 dtype 和异常长度。解析器返回布局标志，loader 拒 Fortran；布尔数组另核存储字节只能0/1，每65536元素检查停止。空白扫描每64字节检查。dtype 数字逐字符计算，不建立数字子串。

每个 token 创建前预约 bytes slice 与 ASCII 字符 payload；这不是 Python 字符串对象实际堆尺寸。维数和类型运算的 Python 整数、至多八元素列表、三个键字典均有语法规模上限，但对象开销不在 ledger。`header_payload_copy_bytes=0` 专指头解析不复制 NPY 数组正文；不表示 token 没有复制。真实历史来源能否满足本严格 ZIP/NPY 子集仍未认证。

`operations/x20_86304_preparation_header_configuration.py` 为另名普通函数。旧配置、旧数值源均不修改，无 FunctionType 或生产 monkeypatch。七来源外部大小/SHA、trial/base 全数组、固定 current_material_state、模板 second_material_iterate、warm 纯词法声明及原旧字段保留、phase/duration/几何和所有权门保持。新 residual 在原始头上严格核 `<f8`、[512]、非 Fortran 后才 frombuffer；不能用 ndarray.dtype.str 规范化后的值替代原始描述门。源码对照见 `20261007-headers-composition-source-final.diff`。

## 明确计量范围

以下为本次合成累计显式容量预约，不是同时存活字节、allocator 次数、设备 I/O 或 RSS 上界。

| 表达式 | 预约 B | 范围和检查点 |
| --- | ---: | --- |
| 解码 output bytearray | 69720 | 分配前，复用冻结 decoder |
| 压缩 input slice | 3241 | 分块前，每块最多65536 |
| 返回及暴露 tail 容量 | 76234 | decompress 前；不含私有 zlib workspace |
| 不可变解压成员 bytes | 69720 | 转换前 |
| 头 token bytes 与 ASCII 字符 payload | 1716 | 每 token 创建前 |
| 浮点/复数 finite-mask | 8713 | isfinite 前；不冒 ufunc 内部工作区 |
| trial/base 的 tobytes 比较 | 49200 | 比较前预约全部数组容量 |
| 原四 copy | 7168 | 每次 np.array 前 |
| 原四 mirror | 14336 | 每次 concatenate 前 |
| 合计 | 300048 | 严格小于512MiB，累计不释放 |

四NPZ声明解压成员69720B，七原始合成输入12772B，residual只读正文4096B另列。frombuffer/reshape为视图，但其 Python/NumPy对象不在预约中。ZIP中央/局部目录的名称切片/解码、目录对象、JSON解析与固定/模板对象、原科学调用及结果回执序列化未全计量。source pack 和环境输入也不在上述合成来源计量里。

原科学剩余范围保持具体：validate_arrays 的有限/比较掩码；exact_trial 的 control 构造、乘加、codec 与 trust-region；_full_column 的 mass/rho、拼接、sum、负号、cumsum、加法及镜像；context 的相位差、除法、相邻平均、repeat；Gauss求积、stencil和block planner传递依赖。原调用外及复制边界已有检查点，内部各表达式尚无完整预约/检查点。此列表是待审表达式族，不是完成的科学依赖闭包清单。

## 新合成与独立核验

新专用入口 `run_x20_86304_preparation_headers_fixture.py` 固定129频组、两块、两相位128半列、零control。沿用原合成源工厂，但不是重跑旧9632/76块配置专用合成。未分配大辐射场。-I -S、可信环境显式预载、StopGuard安装、seal、FrozenModules内存导入、新配置执行。默认StopGuard120秒/1GiB历史峰检查和supervise150秒/8MiB实际接线；不是耗尽测试或全生命周期访问保护。pack在seal前读取，解释器/共享库/环境预载仍可信范围。原Popen/内核调度/回收延迟限制保留。本轮未接RLIMIT_AS，未重复旧地址空间试验。

静态pack193条含空operations namespace，192条交FrozenModules，实际155项目模块；是沿旧较宽闭包加入新模块，不声称最小闭包。源码bytes、实际loader/file/spec核，学校逻辑root重定位。学校本次只使用Linux post-preload seal，不重新认证旧25路径测试，也不提升Mac所有路径拒绝资格。

两端各18新tests，最终Mac0.008s、学校3.08s，无失败、skip或放宽断言。Mac首17/0.002s、后18/0.008s，学校前18/4.07s及首轮日志均保存。后续源码审查去掉dtype数字子串并恢复原始residual描述门，按新源码分别复验新组合；未重跑旧inflate19、configuration21及旧专用组合、context25等。

独立标准库 reviewer 不导入新loader/adapter/native，从回执中原始NPY字节重建试态/base、四镜像、单位层宽柱、零beta、全部master边界和两块所有权，核fixed/template赋值；ledger每项真整数和总和、decoder计数/chunk上限另核。7种篡改：生产资格、头复制声明、ledger总数、boolphase、65537返回、缺原模块、镜像SHA均拒。回执审阅本身不能证明每个内部真实分配都被记账。

两端配置、来源、物质、除mu/weight外context及155模块名一致。mu/weight各自从字节核指纹，再独立0到3阶角矩固定绝对2e-14通过，不声称完整context逐位同或非零速度等价。

最终Mac内部1.0942865828983486s、历史峰RSS174768128B、外部1.1622912921011448s；学校内部11.354049754008884s、146669568B、外部11.56348552100826s。仅新小例；历史前两轮时钟保留，不作性能趋势或提速比较。

## 保存和决定

开始Mac4951ed2f5fae26ac3a229c0053e7f88fa33dcbf8、学校fbfe81fb7ec4e9714e256ec460b483130db5c254，均clean；两端完整pre-86304-headers-20261007.bundle已verify。freeze01=1744、02/03/04=1747；最终全部Mac源码前后SHA同，旧源码同。学校每轮173夹具文件前后同；最终6小回执303636B按外部大小/SHA核后独占收件。学校生产checkout没有同步。

完整原始证据为 outputs/review-20260925/20261007-headers-*；最终Mac preparation-headers-local-20261007-03、学校 preparation-headers-fixture-20261007-03、认证收件 preparation-headers-school-verified-20261007-03。所有前轮和原日志保留。没有真实343staging、NPZ/native刷新、科学归档payload、dat stat/读/下载、Slurm/map反馈ODE物质。

[POST-RUN CHECK]

Code: PASS。新18测试、两端实际接线、独立字节/原运算结果核与7负例通过，无stderr。
Logic: WARNING。计量明确仅表内容量；科学内部、JSON/ZIP目录/对象和启动访问范围未闭合。
Physics: PASS（仅合成身份范围）。没有新物理结果；accepted20/newmaterial0、十倍质量失败和strictboundfalse保持。
Decision: DO NOT RUN真实准备与生产。下一项在这条新接线基础上补原科学逐表达式范围/检查点及剩余JSON/ZIP目录容量，再实现解释器启动/环境预载的实际访问保护；Linux范围须独立审阅。完整准备验收后才另审首次真实来源预算；首片预算另立，全301 DO NOT RUN。
