# 86191 后仅重建平方候选：两端小合成验收

本阶段完成 `operations/x20_85889_chord_scan_square.py`，只将15个不同重建误差的 `dot(delta,delta)[0]` 换成专用辅助函数。该函数仍形成 `delta*delta`，保持原errstate、三比较/两按位and的非零乘积变零拒绝、同形状布局全数组longdouble求和。57个矩阵内积仍调用原dot。原scanner、reuse及独立Decimal80审阅器字节未改；AST测试核候选主体除这一调用替换外与reuse相同。

## 验证与实际范围

本轮PRE-RUN检查源码输入/类型/布局/缓存、固定表达式及原拒绝门，允许小合成验证；物理项WARNING，因为它不计算新的转移、反馈或物质响应。没有真实dat读取、下载或新Slurm；学校生产保持 `4b02b0865ed45103770a6ecf63638c9696bd0a62` clean，未同步候选。Mac起点 `3503168aa8479c30f94abf303d0ad36ac79dea27` clean。

- 首轮Mac144项通过，0.68秒；补充归约溢出warn/raise/ignore、平方Decimal oracle及完整序列化结构后最终149项通过，0.64秒。学校隔离相同149项通过，4.93秒；70新候选、43既有reuse、36原核，无skip或测试失败。
- 小shape的C/F/反stride、原binary64树位模式、完整slab摘要和字符串零符号、独立Decimal80所有矩阵及辅助平方、抵消/宽动态/近溢出/极小/非有限、输入不写/readonly/no跨调用缓存、错误系数/伪大误差、缓存命中停止及时间/RSS路径均核。
- 归约非有限仍在decimal序列化被拒绝，原乘法溢出和非零乘积变零继续拒绝；继承全局求和over策略。警告类别及异常类别相同，不保证警告次数相同：旧两个sum可能警告两次，候选一次。这是去除未消费计算的可说明差别。
- 实测调用57次dot与15次平方辅助，共129次sum，原reuse144次。这只证明成功路径调用数，不是速度、RSS或组件耗时收益。

`handoff/audit_tools/exercise_x20_86191_square.py` 固定129×2×3合成样例，映射为半倍输入加4，显式分别调用reuse和square的slab函数，不用FunctionType或生产monkeypatch。5片、2块完整数值摘要同原scan；原独立Decimal80审阅结果相同，四组合范数比及方向投影均0.5。伪造大重建误差被拒绝。

这个练习由原scan提供小文件生命周期证据，候选仅消费另外一次读取的同一组不可变bytes/frombuffer只读输入，并复用原scan证据外壳做统计审阅；JSON明确标记 `synthetic_explicit_slab_wiring` 和 `file_evidence_from_original_scan`。这不是候选生产scan驱动的E2E。原scan读111456B，加共享小buffer读37152B，每端该条E2E合计148608B合成.bin；并非整套tests总I/O。新候选无文件I/O、CLI或sbatch入口。

Mac小E2E峰值32751616B、学校31064064B；NumPy均2.5.2、FE_TONEAREST代码0，Mac longdouble nmant52/maxexp1024、学校63/16384。最小binary64差平方Mac仍拒绝，学校仍非零，不比较longdouble padding、不强制所有极小量跨平台相同。八代码实际SHA相同；学校五小JSON先核大小SHA收件，Mac再次独立review通过，该合成例子的所有slab跨平台相同。学校代码SHA是运行后核验，不冒称首次执行前已经核验。

## 保存和独立审阅

两端完整 `pre-86191-square-implementation-20261006.bundle` 已verify，Mac26054443B、学校25971302B。学校仅使用 `outputs/review-20260925/square-fixture-20261006`，未改生产依赖。Mac小E2E为 `square-e2e-20261006`，学校小收件为 `square-school-e2e-20261006`。八文件清单 `20261006-square-code.json`、学校回执 `20261006-square-school-receipt.json`、两端测试日志与 `20261006-square-parity.json` 保存于 `outputs/review-20260925`。小审计、CLI原稿及独立纠错在 `handoff/evidence/20261006-square-*.json`。

POST-RUN：预期异常均拒绝，无意外警告/NaNInf接受或摘要差异；解析仿射小样例符合0.5关系。无新图，无真实物理趋势可解释。CLI只读候选全文与实际摘要，不能冒称生产性能审计；讲义160只追加新段，原前缀保留。

## 决定

仅有限小合成数值等价验收通过。未测生产资源或受控提速；85889/86061/86191预算均关闭，没有新Job预算，完整301片DO NOT RUN。下一项先另立15个矩阵对角signed/abs结果共享的独立验证约定，再决定是否另命名实现；本轮没有实现该变体，scratch/out=仍暂缓。后续生产必须另立有界资源协议、冻结、两端备份/来源核及完整PRE-RUN，不自动重交86191或扩原3300秒/Slurm1小时预算。

accepted20、0新物质步、baseline/calibration/strictbound false，跨16响应失败/五率通过保持；HHe最终任务仍未完成。
