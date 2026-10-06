# 复用资源预检：生产审阅入口与当前来源验收

本轮补齐生产审阅入口测试，并发现、修复三项独立验收缺口。起始Mac提交3574dcbc4755a3243b8cd2648f9e338ab1464431、学校82aea66f68dd9f1abc27a8268ffd5e1bfa34f418均clean。以下记录来源准备和审阅器测试；没有新Slurm或真实dat读取，尚无复用核生产资源结果。85889/86061预算仍关闭。

## 已发现问题和修复范围

新`tests/test_x20_85889_chord_reuse_production_review.py`实际调用完整`review_run`，使用固定SHA的86061历史小JSON，数值摘要原样保留，构造明确虚构的900002调度/时间/28阶段元数据。它不是新生产main或实际Slurm运行，也不提供新资源测量。入口可以审核一组自洽字节，但实际调度来源必须由外部真实查询承担，不能从测试回执或SHA推出。

首次11通过、3失败：前后live记录若同时改成错误groups、runtime SHA或native打开路径，旧独立审阅器仍接受。生产live_check本身有检查；缺口在独立审阅器只核前后相等和部分标志。首次仅增加新审阅器8行：四网格计数要求真实整数9632/32/4096/76；runtime完整清单与打开路径逐项对照固定SHA历史result.live_before；physical_validation和strict_error_bound必须为false。历史来源、旧核、复用核、driver/sbatch、v1/v2及旧Decimal审阅器字节不改。

原失败日志`20261006-chord-reuse-production-tests-01.log`保留。修复后146通过0.85秒；补bool计数、bool依赖大小及错误物理提升负路径后最终149通过：Mac0.91秒、学校隔离5.44秒，无跳过。此时17个新增生产入口tests与既有132项共同执行，包含来源路径/外部绑定、native标志/变化/phase/dt、归档、历史/代码读量、缺阶段及以上新拒绝。学校隔离fixture54文件全部大小SHA相同；压缩包138370B、SHA7e383d8a96ce4c9521f23c88418e05d47205f0d4867c831a9f8eb3d4e5a72e2b。完整代码freeze1676个tracked py/sbatch，较前阶段只改一个新审阅器、增加一个tests文件。

## 当前真实来源核验

学校独立准备脚本全程audit hook拒绝任何.dat打开，限120秒、RSS<1GiB。binding/live各前后一次：326小来源、801原源码、两支完整trial镜像dtype/shape/bytes、物理旧层/base/r20、P/F/M及304块所有权通过。当前六项runtime逐SHA复核，native配置确认phase1367、dt889.419892762322和9632组/32方向/4096层/76块。没有执行map、反馈或ODE。

原归档303877902B前后各哈希一次，总607755804B，SHA保持f20c313bc92af5730a16d7a9c604793873719bd710b53d0fc763813349cd120c；不是重新执行旧8588工件完整数值审阅。学校实际墙钟30.259764028989593秒、进程RSS313552896B，来源前后一致；首次import环境元数据单列，不从相等门删除其他科学字段。六真实dat只stat，前后dev/inode/size/mtime_ns/ctime_ns一致，没有新全SHA读取。

学校9个小JSON逐大小SHA下载，Mac重新执行binding实际核326小源/801原源码，10.131717832759023秒，除物理文件local_path外与学校绑定完全相同；学校前后live、stat及固定历史runtime/geometry也独立比较通过。Mac没有运行native或读取真实dat。来源记录位于`chord-reuse-production-sources-school-20261006`，完整原件保留学校`chord-reuse-production-sources-20261006`。

两端完整pre-chord-reuse-production-acceptance-20261006.bundle均verify。备份、源码清单、小来源回执、原失败及成功日志、独立CLI原稿/纠错均保留，不覆盖旧阶段。

## 决策边界

上述测试只证明独立审阅入口与当前来源准备。新main的真实28阶段、六全场前后SHA、复用首片完整摘要、生产墙钟/RSS及实际新job终态尚未运行；production_resource_verified=false、speedup_measured=false。六全SHA必须在新Slurm内全部通过后才可统计首32组。任何后续一次资源提交必须另存同步后的完整PRE-RUN与唯一提交回执；本报告不自动授予预算，也不恢复86061或85889。

拟议一次预检仍只统计[0,32)，不扩大为301片；4CPU16GiB单节点线程1，Slurm1800秒、程序1500秒、RSS<6GiB。field payload121601261568B与归档607755804B是逻辑读量，不是设备I/O；当前native小准备RSS不是生产首片峰值。历史26.2067秒不能承诺提速或全场ETA。失败保留，不重交、换片或扩时。

[POST-RUN CHECK]

Code: PASS，原三项验收缺口已显式复现并修复；两端149项通过，无非预期NaN/Inf或数值断言放宽。Logic: PASS（当前来源与小JSON审阅入口），实际生产新job仍待独立决策。Physics: WARNING，没有新增物理趋势、全场Gram或图；测试中的历史数值不能算新生产数值。accepted20、0新物质、baseline/calibration/strictbound=false，原窗口响应通过、跨16响应失败/跨16五率通过保持。HHe未完成。

CLI审阅器全文/driver主入口审阅54.73373591620475秒，实际deepseek-v4-flash[1m]。独立纠正固定history SHA已核、0/32已通过完整比较绑定、环境元数据范围及测试组成等误述；采纳显式排除85889，增加一项一致旧job伪装测试，最终18新增+132既有=150，Mac1.00秒、学校隔离5.41秒。原稿与逐项纠错保存，讲义157追加；旧前缀462094B SHA274ef4e9eef7df54a60fd9045bf07dfa9e8d9e2f0c4861d53b980c83d6a60c23逐字节未变。最终测试与冻结清单见小证据索引。
