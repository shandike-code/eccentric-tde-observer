# 86304专用首片资源封装与合成验收（2026-10-07）

本阶段另名实现resource、contract、live、receipt、sbatch和独立review_run，新增专用小合成器及两份tests。没有调用真实生产main、刷新真实native、读取/stat/下载真实dat、生成实际提交ticket或新Slurm，也没有map、反馈、ODE或物质更新。全部旧预算关闭，全301片仍DO NOT RUN。

## 接口与验收范围

源job固定86304，执行job另核；固定P→F第7张、F→M第8张与旧85889 M种子。适配结果按json-ascii-compact-insertion-order-v1内容摘要bc2597332898c2a5e3f0f86b64242af32f20f01959191d3fdeee7c3c9e3c0d8a冻结。生产live接口要求独立完整文件清单，再验证当前归档链、完整trial/old/base/r20、学校原exact_trial decode、native镜像及当前runtime打开路径；实际完整清单尚未生成，真实live前置未运行，不能声称这些真实门本轮已通过。17.16MB原physicalold单文件例外保留。

来源接口分别核外部预期native/runtime和前后状态；完整review_run负例中前后同时改错仍拒绝。配置期间audit hook拒dat和子进程，profile禁止初始化/migrate/map/反馈等指定入口；这不是通用安全沙箱。来源显式认证payload是文件清单两次认证加两归档各一次，native打开事件及次数另记，不把该认证payload冒称全部底层读取或设备I/O。具体清单、必要性与读取上限须下一阶段独立冻结后才可实际运行。

驱动显式调用冻结diagonal一次；原scanner/diagonal/square数值代码、binary64表达式和longdouble归并未改。六全SHA前置全部过，首片只读同不可变bytes，原六句柄贯穿统计和同片重读，结束再全SHA。独立首片审阅保留真实9632×32×4096布局与唯一[0,32)范围，不伪shape32、不伪造其余300片、不引用旧86061摘要为当前场基准。复用原纯Decimal首片matrix/重建检查及summarize，输出局部四组合有符号指标；global_h1=null、full_field_statistics_complete=false。

新execute保存信号、超时、RSS和失败目录，全部生产25阶段按顺序核。每阶段记录数值进程累计峰RSS、采样进程树即时RSS，以及已结束子进程原生单位rusage，后两者不相加冒充同时峰值。采样不保证捕获瞬时树峰值；16GiB调度分配仍是作业硬边界。实际代码file/spec origin与外部完整代码清单核。新main要求完整sources/code-freeze，无synthetic或任意kernel/reference绕过参数。

## 两端小合成

最终测试由91项新封装/live接口/完整审阅测试加23项既有86304来源适配测试组成，共114项，无失败、skip或容差放宽。Mac最终8.62秒；学校最终36.90秒；先前114项31.94秒记录保留。首56、后81及114的日志全部保留；首56没有命名前置代码freeze，不回写成已冻结。最终freeze-03为1713份代码，学校夹具另加一份固定binding JSON，共1714份前后核。

专用E2E六.bin各33×2×3，仅首32组统计，一次显式diagonal，同平台独立Decimal80逐单元核五组5×5 signed/absolute共250标量和四组合Linf。驱动正常字段读取37440B；oracle额外从六完整合成文件读取9504B，因此该条E2E合计46944B，不是整套tests总读取量。首版metadata漏算oracle读量，原01/02记录保留，03修正且加入断言；统计核、场、阈值未改。

完整review_run另用虚构900002/提交时标/调度元数据和解析合成铺设矩验证25阶段。铺设只是测试数学构造，不伪称生成了真实分辨率文件或当前场；返回synthetic_evidence=true、production_resource_preflight_complete=false。普通小execute使用虚构900001并真实走21个场阶段、归档收件和review_evidence。两种测试范围分开，均未运行生产main/native/Slurm。

负路径覆盖当前源job/version/field/binding、错seed/chain/频组与trial（23项既有适配测试）、完整清单/NPZ限制/role SHA/运行路径、native镜像/76块、前后同时错误native/runtime、缺square/错误origin、旧执行job/ticket/终态、bool/非有限、片外损坏与源变、一次核/同bytes、信号/RSS/墙钟、缺阶段/重叠/错误读量和部分目录。小包只含白名单JSON/日志，整包及成员大小SHA先核再独占收件；学校小包在Mac独立复现审阅，最终记录见parity-03。合成完整首片摘要跨平台同，不泛化所有次正规量；两端LD仍52/1024和63/16384。

## 独立审阅与后续

学校CLI首轮提供live/driver全文，55.1407秒超时124且没有成功草稿，原失败回执保留。短事实重试12.3273秒，实际deepseek-v4-flash[1m]成功，仅事实讲义，不是全部源码或性能审计。独立纠正其“执行job与统计核分离”为“执行job与源job分开”；接口已实际合成运行，不能笼统说只是文件存在；SHA不能证明全部中间时刻未改动。补充oracle读量纠正，CLI给定时刻的旧测试时长不冒最终时长。讲义175另写，旧前缀保留。

POST-RUN CHECK：两端合成/故障路径已通过，专用样例矩和局部范数比可解释；0.5只对应合成T(x)=0.5x+4。无新真实物理趋势/图。production_driver_implemented=true仅接口实施，production_resource_verified、submission_ready、new_production_authorized、full_field_statistics_complete均false。accepted20/newmaterial0、校准/基线/严格误差资格false、十倍跨支质量响应失败保持。

下一项先审本报告和新live接口，另定实际来源准备的具体清单、逐文件路径/必要性/数量/SHA与总读取上限、时间RSS预算以及配置禁止dat的运行约定；这份约定独立审阅后才能首次真实小源/native前置。再核生产main剩余接口、当前完整代码和来源，按完整PRE-RUN独立决定是否授予一次新首片资源预算。本阶段没有该授权，也不自动全301片或再加8/16map。
