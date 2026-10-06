# 对角共享 version4：真实来源前置验收

本轮完成生产来源前置核和完整代码冻结。学校经完整备份、bundle verify/fetch 新 ref/ff-only，从4b02b0865ed45103770a6ecf63638c9696bd0a62同步到68a950fa3b5c6418e4d94f2ba4a1d36ec12c55b3；来源检查前后HEAD精确且clean。Mac起点相同提交且clean。未修改任何tracked Python/sbatch、数值核或旧协议，本轮0 Slurm/真实dat读取下载/map/反馈/ODE/物质步。旧85889/86061/86191预算关闭，全301片仍DO NOT RUN。

## 实际前置与范围

完整外部代码冻结为outputs/review-20260925/20261006-diagonal-production-code-freeze.json，1692份全部tracked py/sbatch，两端逐大小SHA一致，包含六份diagnostics代码；没有使用前阶段1686份fixture清单冒充完整清单。学校生产checkout最终384tests/22.13s通过，无skip，沿用既有全部断言；前阶段Mac384/2.28s和隔离学校384/7.24s仍为不同运行，不回写旧时间。本轮没有数值实现改动，未无故重跑Mac同一合成。

独立来源编排脚本存outputs/review-20260925/20261006-diagonal-production-source-check.py，学校实际执行同字节/tmp/ustc-diagonal-production-source-check-20261006.py。它是外部准备工具，不是生产main；不对生产模块作monkeypatch或修改来源对象。生产项目module身份仍由冻结driver.runtime_identity检查；外部编排器自身不属于1692项目代码清单，脚本另存来源证据。全程audit hook拒绝.dat打开，限120秒/RSS小于1GiB，六场仅stat。

学校实际前后两遍binding/live核326归档小来源、801原源码、原P/F/M链、old/base/r20、两支trial镜像数组dtype/shape/bytes与当前native，六项runtime逐SHA核。phase1367、dt889.419892762322、9632组/32方向/4096层/76块均原值。归档303877902B前后SHA通过，合计607755804B应用层payload；小来源/源码/环境元数据另计，不是设备I/O。六场stat前后相同，未刷新六场完整SHA。

准备耗时43.78715581000142秒、RSS316153856B。native导入后113个已加载项目模块的file/spec origin、普通文件大小SHA均对完整冻结checkout清单通过，前后identity一致；解释器/NumPy实际路径与版本另列，np.geterr仍divide=warn/over=warn/under=ignore/invalid=warn，未seterr修正。113是实际模块数，不是固定常数或全系统库数。该结果闭合了此前仅合成测试不能证明的真实native导入路径前置，仍不是生产Slurm峰值或slab耗时。

学校14份普通JSON共1090322B先生成外部manifest再逐大小SHA收件，Mac收于diagonal-production-sources-school-20261006。Mac重新实际执行binding，耗时10.011950625106692秒，326小源/801源码再次核；仅physical_sources.local_path平台不同，canonical其余字段及顺序严格相同。当前live runtime清单、native打开路径和几何/phase/dt均与固定86061历史result逐项严格相同。四历史JSON固定66216B，未重跑旧真实核或旧完整review。外部Mac binding另存20261006-diagonal-production-binding.json，未来ticket须按contract.document_sha的JSON内容编码计算摘要，不冒充原文件SHA。

## 审阅与保存

两端pre-diagonal-production-sources-20261006.bundle完整verify，Mac26160067B、学校25957894B；增量diagonal-production-sync-20261006.bundle另留。最终code-state核全部1692份代码未变。首附加状态检查因CLI草稿已新建而正确拒绝clean要求；第二次准备脚本文本转义错误导致SyntaxError，均未执行数值或改来源断言。原两版脚本保留，最终只允许那一个明确的未跟踪CLI文档并如实记Mac clean=false；学校仍clean。最终阶段文档提交后再核Mac clean，不将工作期间文档未提交误写数值源码改变。

学校无工具CLI实际deepseek-v4-flash[1m]，29.851353832986206秒，只看reviewer全文、driver main与给定事实。独立修正草稿片payload漏32方向、slice-hash也计payload、Decimal80称精确数学比较、113称硬编码及将来源编排器误混Slurm回执等。原draft与review保留。CLI不替代独立判断，也不算全部依赖/性能审计。

## PRE-RUN / POST-RUN与下一步

PRE-RUN Code PASS、Logic PASS、Physics WARNING，Decision RUN仅限备份同步、来源配置和小测试；无真实场/Slurm授权。POST-RUN：学校来源准备和384测试通过，未出现未处理数值警告/NaN/Inf；配置几何与原物理尺度相同，无新的物理趋势或图。真实field计划payload121601261568B仍没有在本阶段读取，不以stat/旧86191/小合成替代新Slurm内六全SHA前后核。

本轮production_source_preparation_complete=true，但submission_ready/production_resource_verified/controlled_speedup_measured/full_scan_authorized=false。当次外部提交ticket生成、observer衔接与最终启动PRE-RUN尚未执行，未授予新Job预算。下一轮先核本报告、两端最新HEAD/clean、完整备份与1692冻结清单，审阅当次提交记录生成及独立只读observer保存路径；完整PRE-RUN后才独立决定一次首32组资源作业。单节点4CPU16GiB、线程1、Slurm1800秒/程序严格小于1500秒/RSS严格小于6GiB仍只是拟定上限，不重交86191，不自动全301片或扩原3300秒/1小时。当前原始源数据与科学门保持：accepted20、baseline/calibration/strictboundfalse，跨16响应失败/五率通过，HHe未完成。
