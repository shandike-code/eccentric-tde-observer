# 86304 Legendre 求积显式数组与停止组件

本轮新增另名 `operations/x20_86304_preparation_leggauss.py`，展开原 leggauss 的 Python 层数组表达式。两端新小合成验证通过；eigvalsh 的原生矩阵副本、LAPACK/NumPy 私有工作区仍未计量，本组件尚未接入 frequency 配置。完整准备未完成。

## 源码审查与实施范围

先静态读取两端当前 NumPy 2.5.2 的 legendre.py、polyutils.py、linalg/_linalg.py，另核 version.py，四份文件 SHA 完全相同，清单在 outputs/review-20260925/20261007-leggauss-numpy-source-{local,school}.json。leggauss 调用链为 legcompanion/as_series、eigvalsh、三次 legval、一次 legder，再 Newton 修正、权重和对称化。eigvalsh Python 包装选择 eigvalsh_lo gufunc，返回后 astype(copy=False)；不能由 Python 返回数组大小推断 C/LAPACK 内部容量。本轮未读取原生 C/Fortran 实现或证明其工作区上界。

仅接受真 Python int 1..16，要求默认整数8字节。系数固定为末项一、其他零：as_series 的 trim 不切片，common_type 为 double，因此新路径显式执行对应 double copy；不实现任意多项式、复数或高阶通用接口。legval 中 array(copy=None)、reshape 与切片在此输入域只生成视图；整数系数转 double 另预约。legder 保留整数 copy、astype、原系数递推及原 inplace 顺序，省去一维 axis=0 的 moveaxis 视图对象，不宣称逐句源码完全相同。

伴随矩阵的 arange、乘二、加一、sqrt、倒数、两次副对角乘积、最后列四个结果均创建前预约。Clenshaw 每步分别预约左乘、左减、右乘、右缩放、右加，首次左侧是长度一数组，后续长度为阶数；最后乘加亦分开。导数 copy/cast/empty、Newton 商、两个 abs、权重乘积/倒数/对称化、节点对称化同样创建前预约。inplace 写入前检查停止，eigvalsh 返回后检查，递推各次标量写入也检查。原权重规范化为原算法的一部分，不是新增物理修补。

16阶共251项累计33344 B、334检查点；1阶24项232 B/32检查点，2阶41项672 B/54检查点。3..16阶容量为128乘阶数平方加32乘阶数加64字节。每项具名表由独立标准库 reviewer 重新生成并严格核类型、顺序、大小、总和和检查点计数。

预约范围是显式 ndarray 结果 payload；不含 Python/ndarray/闭包对象、Python列表、NumPy标量或零维内部结果、ufunc内部缓冲、eigvalsh原生矩阵副本及LAPACK工作区、序列化。拆变量可能延长存活。预约不是allocator调用数、实际总分配、live或RSS界，单个底层调用不能被检查点中断。源码认证在本次外部夹具完成，函数自身并不认证任意安装环境。旧 quadrature/frequency 配置和全部旧科学源未改。

## PRE-RUN 和新验证

初始 Mac 77d6ccb4847c3185692c129f7ae2b522ee0b6ff1、学校 fbfe81fb7ec4e9714e256ec460b483130db5c254 均 clean；两端 pre-86304-leggauss-20261007.bundle 完整 verify。学校生产未同步。freeze01为1769份，在新tests前冻结；新reviewer随后以学校四文件外部pins在执行前固定，freeze02最终1770份全部后核相同。

Code PASS：语法、源码、备份和版本核。Logic PASS：固定表达式顺序、同平台原函数对照、逐点停止与容量拒绝。Physics WARNING：仅标准区间求积组件，不认证物理来源或HHe。Decision RUN仅新五项tests及16个微型阶数夹具。

两端各5项新tests：Mac0.17秒、学校4.86秒，无测试失败、skip或断言放宽。全部1..16阶节点和权重dtype/shape/bytes/writeable同平台原函数相同；1/2/16阶每一个检查点停止及每一项预约不足均拒绝并核前缀；bool/NumPy整数/浮点/越界等域拒绝及跨调用输出隔离通过。没有重跑旧tests或97/65等配置组合。

独立 reviewer 不导入组件或NumPy，用struct解析原字节、SHA核，然后逐阶核节点严格递增且在(-1,1)、权重正，以及0..2n-1阶解析矩。固定绝对2e-14门，Mac最大误差1.9290125052862095e-15、学校1.2212453270876722e-15；这是有限浮点一致性检查，不是严格舍入误差界。10类篡改拒绝：私有workspace资格、生产资格、缺阶数、bool阶数/检查点/容量/elapsed/shape、容量连总和同步改、坏权重重算SHA。

额外跨平台全部cases逐字节断言失败，原脚本和差异清单保留。节点最大差1.1102230246251565e-16、权重1.4710455076283324e-15；两端容量表和检查点完全相同。各平台原函数字节对照与事先固定解析矩门已分别通过，没有修改组件、reviewer或容差，没有重跑数值夹具。不能把此结果写成两端全部数组逐位相同。

本次普通子进程tests上限60秒、exercise/reviewer各30秒；没有-I/-S/seal、StopGuard/supervise、RSS测量或耗尽试验，不借用旧配置的120秒/1GiB/150秒资格。内部16阶数组样例合计耗时Mac0.0018007908947765827秒、学校0.005558126023970544秒，不含解释器导入，不能作生产性能或提速结论。

学校4份夹具源码和4份NumPy源码前后核相同；5份回执98172 B按外部大小SHA全核后独占收件 preparation-leggauss-school-verified-20261007。学校同版reviewer也运行，Mac再次独立审两端原回执。首次辅助目录glob查询不存在backup路径失败，无修改；正式bundle路径随后从旧日志确认。源数据始终未访问。

## POST-RUN 与后续边界

synthetic_leggauss_explicit_arrays_verified=true，仅上述有限域；leggauss_internals_metered=false（私有工作区尚缺），leggauss_configuration_integrated=false。旧synthetic_frequency_configuration_verified=true只属于旧接线，不自动继承新组件。whole_lifecycle_guard_verified/all_scientific_temporaries_metered/complete_native_context_verified/native_loader_metering_integrated/production_resource_stop_guards_integrated/actual_source_manifest_prepared/live_native_recomputed/submission_ready/new_production_authorized/full_scan_authorized均false。

下一项先审原生eigvalsh实际后端与工作区可验证边界，不能把本表扩大为全量；将本已验组件接另名split/context/configuration并仅做新小合成，不重跑本5项/16阶或旧组合。然后继续exact_trial/control/codec/trust、JSON/ZIP目录及解释器启动/环境预载实际访问保护。仍须两端clean/完整bundle/源码冻结。固定真实准备入口完整计量、停止、访问与源码认证一起独立验收后，另审首次真实来源预算；首片预算另立，全301片DO NOT RUN。

0真实343staging/NPZ/native刷新、科学归档payload、dat stat读下载、Slurm/map/反馈/ODE/物质。accepted20/newmaterial0/strictboundfalse和十倍跨支质量门失败保持，HHe未完成。证据在 outputs/review-20260925/20261007-leggauss-*，学校 preparation-leggauss-fixture-20261007。

学校CLI只读给定短事实，14.764115208294243秒，实际deepseek-v4-flash[1m]。草稿将预约误写成界总分配/live/RSS，已独立纠正；不作为源码或性能审计。文档生成首次在追加讲义后因脚本目录不含项目import路径而失败；随后只执行未完成的格式核验/证据保存，旧前缀SHA与唯一189段核过，没有重复追加或数值执行。
