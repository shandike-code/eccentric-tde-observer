# 86061后：相同表达式复用核的两端合成验证

独立单片复用核已实现，两端同平台新旧数值对照通过。它只提供`slab_statistics(fields, check)`，没有生产I/O、Slurm入口或新的生产性能测量。原85889及86061预算仍关闭，完整301片统计未授权。

## 实现和算术范围

新文件`operations/x20_85889_chord_scan_reuse.py`导入冻结原核的`dot`、`decimal_text`、端点及系数常量；旧`operations/x20_85889_chord_scan.py`的SHA9349c255b35c515fd37e7903a120ebed753e9c517c9381b402d4184d450a1643不变。独立审阅器也未修改。新核保留所有原矩阵、绝对乘积和、极值、Linf、重建误差和形成恒等式输出，未修改物理或数值门。

缓存键是有序binary64减法树。支内差先以binary64形成，缺陷差再以binary64相减，之后原样提升longdouble。缓存向量只读，调用者数组不写入；调用期间输入必须保持不变。每次函数调用重新创建缓存，结束后释放，不跨片沿用。矩阵乘积只缓存两个已检查和格式化的标量，不保存乘积数组、不用大Gram重建小差。

重建摘要缓存键包含直接向量表达式、完整系数tuple和基底表达式tuple；第一次仍执行原零初始化和系数顺序、逐点差门及原dot，随后仅复用完全相同路径。不同系数不能命中旧摘要。形成恒等式仍逐组合检查。六源强度和原来就只算一次，本次将同一bound与其最大值从组合循环外提。所有缓存命中仍调用check；还在入口、重建和出口增加协作停止检查。停止时间不要求与旧核完全相同，也不能中断单个正在阻塞的底层调用。

本轮实际计数测试确认旧核95次dot、新核72次，其中57个有序矩阵乘积和15个重建平方。未实施scratch缓冲或专用平方归约，未改变dot中的乘法、非零因子乘积变零拒绝、signed/abs两次完整数组归约。调用数减少23次不代表耗时减少24.2%，没有本轮生产提速结论。

## 内存边界

第一版缓存全部15个binary64差数组和15个longdouble向量，生命周期为一片。学校当前longdouble存储16字节；对4194304元素的生产片，这两类数组payload分别为480MiB与960MiB，另有六源192MiB、源尺度、bound、重建和乘积/掩码等临时量。实际RSS还受数组布局、分配器和Python环境影响；这些算术不是RSS预测。当前小样例不能证明新核在生产小于6GiB，未来独立资源预检须实际测量。生命周期进一步收缩属于后续优化，不冒称本轮已实现。

## 两端验证

Mac83tests、学校隔离83tests通过（43新核、36旧核、4静态审计），本次数值覆盖版本为Mac0.45秒、学校4.03秒。首次Mac79项后补一般随机浮点宽动态/重建舍入三例和binary64缺陷差溢出一例，日志均保留，没有测试失败或断言放宽。测试包括C/F/反向stride、1/31/32/33/129组、signed zero、强抵消、宽动态、近上溢/最小非零差、全部数值摘要、binary64位模式、原输入字节和writeable标志不变、跨调用缓存隔离。

独立逐单元Decimal80 oracle核五个矩阵全部25项的signed/absolute值；此oracle使用可精确表示的小有理样例，随机宽动态样例另外用同平台旧核对照。负路径包含NaN/Inf/负源、dtype/shape/空、FF错误系数不能复用PP映射差摘要、伪大重建误差被独立审阅器拒绝、缓存命中停止以及入口时间/RSS拒绝。Mac最小binary64差平方仍拒绝，学校保存非零；不能把这两种平台行为说成所有极小值跨平台一致。

最后只将随机浮点测试函数名称改为general_float，避免把有限binary64误称为非二进制有理数；测试内容和生产候选核未变。最终Mac83项0.40秒、学校83项4.80秒；学校保留初版文件，最终测试副本`test_x20_85889_chord_scan_reuse_final.py`的SHA与Mac最终测试相同。初版79/83及全部E2E证据保留。

新`handoff/audit_tools/exercise_x20_86061_reuse.py`只接受输出目录，固定生成129×2×3的合成六场，不接受生产场路径。为测试原I/O与新片核的组合，它用FunctionType复制原scan代码对象与独立globals，仅绑定新的slab函数；旧模块与生产入口不改。这是小合成适配，不是已交付生产扫描器。

解析映射为$T(x)=0.5x+4$，有5片/2块。原scan和合成适配各实际读取111456B合成.bin，合计每端222912B；没有真实dat。两者所有片数值摘要相同，JSON往返由原不导入扫描器的Decimal80审阅器核过，四组合范数比/方向投影均0.5。学校五份JSON下载后逐个SHA核，Mac再次独立审阅学校结果；本小样例两端数值片与全局结果也相同。

两端均NumPy2.5.2、FE_TONEAREST代码0。Maclongdouble nmant52/maxexp1024，学校63/16384；不比较未定义padding字节。小合成进程峰值RSS分别33062912B、31457280B，不是生产峰值或性能测量。学校仅`outputs/review-20260925/chord-reuse-implementation-fixture-20261006`隔离目录，八份源码/测试/审阅器SHA与Mac一致；生产82aea66f68dd9f1abc27a8268ffd5e1bfa34f418仍clean。

## 判定

学校无工具CLI首次带源码请求在110.898秒超时（返回124），日志保留；SSH和checkout正常。第二次精简事实讲义14.803秒成功，实际deepseek-v4-flash[1m]，其“按存储推算的shape”改为给定shape下的缓存数组payload。第二次只承担讲义草稿，不记作完整CLI源码审计；Codex另完成原/新接口逐式读审与独立数值证据核查。讲义154旧前缀逐字节保留，新报告/新段格式及diff核；无图。两端pre-86061-reuse-implementation-20261006.bundle完整verify。

[POST-RUN CHECK]

Code: PASS。两端所有测试和小合成E2E通过，无非预期警告或NaN/Inf输出；极小数与溢出在预期负路径拒绝，失败未掩盖。Logic: PASS。新旧同平台数值对照、独立小矩oracle与Decimal审阅链完整；原I/O组合只在固定合成适配中验证。Physics: WARNING。没有新真实场统计、生产RSS/墙钟、收敛趋势或物理验证；无新图。

下一步先独立审阅并制定一次有界生产资源预检协议，明确六场前后完整SHA、当前native/依赖与归档绑定、分阶段计时、字节/墙钟/RSS、信号/失败与真实调度终态、小归档和独立审阅要求。不能复用86061预算或自动提交完整301片，不扩大原3300秒/Slurm1小时完整统计预算。当前production_resource_verified=false、full_scan_authorized=false。

本轮0真实dat读取/下载、0新Slurm/map/feedback/ODE/material。accepted20、baseline_replaced=false、reference_calibration_eligible=false、strict_error_bound=false保持；原两支窗口响应过、跨16响应失败、跨16五率通过均不变。HHe任务未完成。
