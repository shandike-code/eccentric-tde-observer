# 86304 eigvalsh 原生后端与调用方工作区审计

本轮完成实际链接身份核查和独立工作区查询，未执行特征值求解或 Legendre 求积。Mac 使用 Accelerate libLAPACK 的 ILP64 dsyevd；学校使用 SciPy OpenBLAS 的 scipy_dsyevd_64_。两端查询结果相同，但后端私有分配仍未闭合，配置接线仍待完成。

## 实际环境和源码边界

Mac 初始 HEAD b82596f18fb5eef0d4a3ed179ce0b312912f3c01、学校 fbfe81fb7ec4e9714e256ec460b483130db5c254 均 clean。两端 pre-86304-native-workspace-20261007.bundle 完整 verify。学校生产未同步。Mac otool/nm 与学校 ldd/nm 核对动态依赖及 ILP64 符号；新 probe 经 dladdr 核对实际解析函数所属库。Mac 解析到系统 Accelerate 下 libLAPACK.dylib，学校解析到 numpy.libs/libscipy_openblas64_-61654e39.so。学校构建配置为 OpenBLAS 0.3.34.0.0 USE64BITINT；Mac 为 Accelerate。构建配置不是独立二进制构建证明。

NumPy 两端为2.5.2，声明 git_revision 为48fecee5453aa1d31e6b79dcb3969dc1a6d1a891。读取该提交的[NumPy C++源码](https://raw.githubusercontent.com/numpy/numpy/48fecee5453aa1d31e6b79dcb3969dc1a6d1a891/numpy/linalg/umath_linalg.cpp)，本地保存141311 B，SHA e34c39c15a8a887134aef75e20e6cefc9d0808dfdec2808e77bd125ab66d3ed2。scalar init_evd 先申请矩阵副本和内部特征值共8*n*(n+1)字节，再通过dsyevd查询LWORK/LIWORK，申请8*LWORK加sizeof(fortran_int)*LIWORK。eigh_wrapper随后复制输入、调用求解、复制输出并释放两块缓冲区。eigvalsh使用JOBZ=N、UPLO=L。内部W与上一轮已计的返回数组不是同一缓冲区。

上游源码与安装包声明revision相符不等于可重现构建认证；没有从机器码证明所有分配行为。保存了两端扩展二进制SHA和学校后端二进制SHA，Mac系统库仅解析身份，没有取得系统dyld缓存的完整字节认证。没有审完整Accelerate/OpenBLAS私有实现。不能将参考LAPACK的源码等同于供应商二进制。

## 新查询与独立复核

新增 probe_x20_86304_native_workspace.py，只支持现场核过的Darwin arm64和Linux x86_64、明确ILP64的符号。固定JOBZ=N、UPLO=L，LWORK和LIWORK同时为-1，逐阶1..16查询，分配小型零矩阵与输出缓冲区但不分配推荐工作区，不执行eigvalsh或leggauss。按照[LAPACK接口定义](https://www.netlib.org/lapack/explore-html/d8/d30/group__heevd_ga25b71a69f9921df0a6050aa5883f54f4.html)，此模式返回推荐容量，不进行特征值求解。每例INFO=0、矩阵和W原字节不变。

两端1阶LWORK/LIWORK=1/1；2..16阶为34*n/1。这是当前后端的观察值，不能外推任意版本、高阶、复数或求特征向量的路径。16阶C++第一块2176 B，第二块4360 B，合计6536 B。这个数仅是源码表达式加实际查询推导的两块调用方容量，没有malloc追踪，不是所有内部分配、累计分配、同时live或RSS上界。旧33344 B显式数组表未被修改或追加伪全量字段。query本身可能触发后端内部行为，也不受Python检查点中断。

标准库独立reviewer不导入NumPy或probe，核两回执16行的类型、顺序、固定观察值与容量算术。每端6类篡改均拒：私有工作区资格、bool求解次数、bool阶数、LWORK及容量同步改、缺阶、错误ABI符号。这个reviewer认证回执结构和观察值一致性，不是再次调用后端、环境认证器或完整执行证明。

新probe在执行前已语法检查与源码冻结，freeze初版1771项=旧1770加probe；reviewer是在查询之后新增，最终1772项全部核。学校隔离native-workspace-fixture-20261007只部署probe，执行前后SHA相同；结果大小SHA在Mac独占写入前核过，学校生产仍clean。没有声称学校执行reviewer。原5tests/16阶Legendre夹具及其他旧测试均未重跑，本轮没有pytest运行。查询每端外层30秒，未测RSS、未seal、未接StopGuard或supervise，不能借用其他阶段的120秒/1GiB/150秒资格。

## PRE-RUN、POST-RUN及下一步

PRE-RUN Code PASS：已核实际符号、ILP64参数、源码、语法、clean及完整bundle。Logic WARNING：仅调用方容量与供应商内部行为需分开。Physics WARNING：仅环境查询，不涉及物理模型输出。Decision RUN只本轮查询和标准库审阅。最初一次环境show_config在本轮正式PRE-RUN块之前执行，未做数值求解，此顺序缺口如实记录。show_config提示缺可选pyyaml但输出JSON成功；一次GitHub参考LAPACK网页请求网络失败，随后读取Netlib正式接口，未触发数值重试。

POST-RUN：两查询成功、INFO0、推荐容量为正整数、输入不变，无求解输出或物理趋势可评估。新独立审阅及篡改拒绝完成；源码未变化。结果解释限定为原生接口容量观察，不能据此声称完整计量通过。

下一项直接将已验leggauss接入另名split/context/configuration，保留原运算树并用新小合成独立核；移除旧外层返回容量重复预约。若预约上述原生调用方容量，必须绑定本次环境与查询证据，并在调用前拒不匹配，仍显式排除后端私有分配；不能把6536 B写成后端总内存上限。新组合必须单独验收停止、预算、源认证与实际导入，不复跑旧案例。完整内部计量仍需进一步可验证实现，不能通过改资格字段替代。之后继续exact_trial/control/codec/trust及JSON/ZIP、解释器启动访问保护。

native_backend_identity_observed=true；native_caller_workspace_query_reviewed=true。leggauss_internals_metered、leggauss_configuration_integrated、whole_lifecycle_guard_verified、all_scientific_temporaries_metered、complete_native_context_verified、submission_ready、new_production_authorized、full_scan_authorized仍false。0真实343staging/NPZ/native刷新、科学归档payload、dat stat读下载、Slurm/map/反馈/ODE/物质。accepted20/newmaterial0/strictboundfalse和十倍跨支质量失败保持，HHe未完成。

学校CLI7.508773582987487秒，实际deepseek-v4-flash[1m]，只给定短事实。无实质事实错误；其“外层30秒”解释为timeout上限而非实测耗时，“6536字节”限定为源码及查询推导，不能冒源码/性能完整审计。原稿与复核保存。详见outputs/review-20260925/20261007-native-workspace-*。
