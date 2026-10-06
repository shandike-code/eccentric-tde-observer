# 86191 后矩阵对角共享候选：两端有限合成验收

本阶段另建 `operations/x20_85889_chord_scan_diagonal.py`，通过冻结协议要求的小合成验证。只在gram缓存未命中且有序表达式键相同时，将原square辅助的一次平方和填入signed和absolute；42个其余有序dot与15个重建平方保持。没有生产入口或新作业预算。

Mac起点ff4acfd231e5bf1111cf42039a93744c649c9ecd clean；学校4b02b0865ed45103770a6ecf63638c9696bd0a62 clean，最终仍相同，未生产同步。两端候选名及学校隔离目录查重后，完整pre-86191-diagonal-implementation-20261006.bundle已verify，Mac26105662B、学校25957894B。

## 源码与执行语义

原scanner/reuse/square、原Decimal审阅器和旧协议的SHA保持。候选直接导入冻结square.reconstruction_square，保留delta乘自身、原errstate、3比较2and非零乘积变零拒绝、完整longdouble归约。两次self.vector仍依次执行，第二次取数前停止可拒绝；两次decimal_text也保留。数值相同但键不同仍dot，反向有序键不合并，失败不写products缓存，缓存命中仍check，输入字节及flag不改，无跨调用缓存。

源码差异实读及测试确认：除标题和helper由定义转为原模块导入外，主体AST只改gram；gram源字符串严格等于已声明分支替换。不能把AST相同说成全部源码逐字相同。实际计数42dot、15矩阵平方辅助、15重建平方辅助，共72乘积/114sum，对square129少15个abs数组和归约；不是少15乘积，不是耗时、RSS或全场可行性证据。

## 两端验证与失败记录

最终Mac245项0.76秒、学校245项5.03秒通过：96新候选、70square、43reuse、36原核。首次Mac239项0.78秒，命名SHA清单冻结后239项0.74秒；学校首239项5.30秒。随后增加五布局的真实sum输入捕获测试和精确gram源码差异测试，最终两端245项。无数值测试失败、skip或阈值放宽；所有旧日志保留。首Mac239测试前未保存本阶段命名SHA清单，不冒称已做；其后Mac冻结复验及两次学校执行均有前后11代码SHA核。

覆盖C/F/转置/反stride/偏移view、多shape、只读、零号、宽动态、极小及近溢出、完整slab字符串/结构/顺序和binary64差树位模式。独立Decimal80逐单元核五矩阵全部25项signed/absolute及辅助平方。错误系数、伪大重建误差、非有限/负源/dtype/shape、缓存失败/停止和时间/RSS/合作信号检查均保留。测试钩子只捕捉实际sum输入，不改归约；实际product、abs(product)与共享辅助product的dtype/shape/strides/连续性/对齐及元素字符串在五种被测布局同。

layout-warning.json每端记录135项：5布局、9输入类型、3种warn/raise/ignore策略。该JSON的布局是按原表达式重建的中间数组，真正sum输入由上述测试另行捕获，二者不混称。原dot两返回项与共享两项的结果或拒绝类别相同；求和溢出warn下原2次RuntimeWarning、共享1次，两者序列化均拒绝非有限量。call/log回调副作用未认证，不比longdouble padding。

两端NumPy2.5.2/FE_TONEAREST代码0；Mac longdouble nmant52/maxexp1024、学校63/16384。最小binary64差平方Mac仍拒绝，学校保持非零；有限实数平方没有signed抵消，不能套一般dot的abs单独溢出论证。有限乘积之和仍可溢出。

首学校收件脚本错误地要求跨平台整份review对象相等而失败，原脚本和失败JSON保留。实际唯一差异为maximum_reduction_tolerance：Mac2.7284841053187847137451171875000000000000E-12、学校1.3322676295501878485083580017089843744768E-15，原审阅器分别按各自声明的epsilon和片元素数计算。没有改核或容差；最终学校完整review在Mac逐字段原样复现，两个平台除该预期精度元数据外其余review字段严格相同，全部slab字符串含零号严格相同。这是本样例结论，不推广所有极小量。

## 显式小合成与证据

新exercise_x20_86191_diagonal.py固定129×2×3、T(x)=0.5x+4，显式调用square和diagonal的slab；5片2块完整摘要均同原scan，原独立Decimal80审阅四组合范数比/方向投影均0.5。原scan提供合成.bin三遍文件证据111456B，再读共享不可变bytes37152B，每端这条E2E148608B；不是整套tests总读量。候选JSON明确synthetic_explicit_slab_wiring和file_evidence_from_original_scan，不能称生产驱动E2E。新接线无FunctionType/生产monkeypatch；既有reuse测试的旧适配原样保留。

Mac小E2E峰值RSS33423360B、学校最终32636928B，只属于小夹具，不是生产预测。学校隔离diagonal-fixture-20261006及-02，Mac本地diagonal-e2e-20261006，学校收件diagonal-school-e2e-20261006及-02均在outputs/review-20260925下。先读学校manifest再收白名单6JSON和4日志/代码清单，逐大小SHA核，Mac独立review。完整代码清单、前后核、receipt、parity和tests日志以小证据20261006-diagonal-implementation-review.json索引为准。

学校无工具CLI17.846442秒成功，实际deepseek-v4-flash[1m]；只给gram分支与验证事实，不是完整依赖源码或性能审计。独立纠正其“性能结论缺浮点实测”为缺生产受控性能实测，“旧301片已关闭”为原三个Job预算关闭且完整301片未授权，以及把已测极小差异泛归未验证面。原稿与纠错保存，讲义162追加且旧前缀不改，无图。

## PRE-RUN / POST-RUN 与决定

PRE-RUN：Code/Logic PASS，Physics WARNING；两端clean/exactHEAD/查重/完整备份，逐式核同键资格与双vector顺序，RUN仅小合成。POST-RUN：正常摘要有限、预期非有限拒绝，警告次数差异明记；解析仿射样例回收0.5，无新物理量或图可外推。

本轮0真实dat读取/下载、新Slurm/map/反馈/ODE/物质；accepted20、原r20/80195、物理dt/能量不变，跨16响应失败/五率通过保留。new_diagonal_implemented及numeric_equivalence_tested为true，仅有限合成范围；production_resource_verified、controlled_speedup_measured、full_scan_authorized、baseline/calibration/strictbound均false。

下一项先制定并独立审阅新的有界生产资源协议：显式接入该候选、冻结全部依赖、同源六场前后SHA和不可变bytes、完整来源/native链、生命周期与终态、小包独立审阅。协议阶段无自动预算；不能重交86191、重复旧真实审阅或扩原3300秒/Slurm1小时全扫。scratch/out=等暂缓，完整301片DO NOT RUN，HHe未完成。
