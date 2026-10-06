# 86061后复用核资源预检：协议与实施缺口审阅

本轮完成独立新协议`handoff/protocols/x20-86061-chord-reuse-resource-v1.md`及历史小基准来源绑定。决定为DO NOT RUN：目前允许推进新驱动与独立审阅器的实施准备，没有新Job预算，没有生产同步或真实dat读取。Mac起始94c0d58a90ce6037f667b8e7bc387572c9935f24、学校82aea66f68dd9f1abc27a8268ffd5e1bfa34f418均clean。

## 从源码确认的实施缺口

现有`x20_85889_chord_resource_v2.authenticated_probe`调用v1.probe，v1.probe内部固定调用旧core.slab_statistics；修改提交参数不能使其转用新核。当前复用核仅slab接口，唯一外部使用者为固定小合成exercise。现有v2审阅器只识别version2，并不验证复用核身份或与86061完整小摘要相等。因此不能直接提交现有v2 sbatch，也不能把合成FunctionType适配拿来作生产入口。

计划另命名显式驱动/Slurm、对应独立审阅器及收件白名单调整，保持所有旧代码字节。新代码必须明确记录复用核和运行依赖，不用801份历史源码已核代替新增代码清单。首次运行时实际六场全SHA仍在Slurm内完成，不声称提交前已刷新。

## 固定新探针与旧基准

只运行新核一次、固定首32/9632组，即1/301片。保持六场全SHA前核、同片统计与重读、六场全SHA后核、326小来源/801原源码/current native/六runtime/原归档前后核。统计消费已SHA的同一不可变bytes与同一打开句柄，不另开文件获取数值；无新map/反馈/ODE/物质。

本轮实际重核86061小包126643B、probe26348B/result37696B/terminal1652B的大小SHA；probe与result.probe完全相同，原环境NumPy2.5.2、LD63/maxexp16384、nearest0。来源pins证据保存上述SHA、旧源六声明及片SHA、原审阅/阶段证据和所读封装源码SHA。没有重跑旧数值审阅或原8588工件全审计，也没有重核真实dat/native/大压缩归档。

新核未来的完整slab对象须与旧probe逐字段、逐长度、逐十进制字符串相等，保留零符号；不加入新容差或挑字段。JSON拒重复键/非有限常量，计数拒bool，环境不一致先拒绝诊断。仍需独立Decimal80矩审阅，防止新旧共同错误。历史比较门不是只核环境，也不是物理验证。

## 有界资源与终态

拟定4CPU/16GiB/单节点/单进程/线程1，Slurm1800秒、USR1提前300秒、生命周期小于1500秒、进程峰值RSS小于6GiB。正常场payload121601261568B，原归档前后607755804B，小来源/源码/历史小摘要另计；不是设备I/O。阶段分开记录读/hash/slab/来源与比较时间、实际payload速率，不能把单片计算时间冒充总作业时间。已知缓存1440MiB加六源192MiB及临时量不是严格RSS上界；测量是新探针目的之一。

总预算不保证最低吞吐、清理成功或必能完成；慢读/信号/资源失败保留，不续时或重复作业。观察器独立目录最多2400秒，每10秒只读调度，终态即存；排队耗尽则未知，不能自动重交。Mac用提交回执expected_job_id及外部观察器原始scontrol回执，交叉核新job实际COMPLETED0:0、childexit0、阶段和result/finished、无failure。旧86061终态只证明旧基准。

## 独立审阅与纠错

学校无工具CLI读取协议全文，30.510秒成功，实际deepseek-v4-flash[1m]。其原稿及独立纠错证据保留。采纳并写明同一已hash缓冲/句柄、JSON精确比较及外部调度观察来源；补充每阶段payload速率的记录和总预算失败语义。

未采纳把约81.1MB/s当必须先保证的持续设备吞吐或把阶段独立字节秒额度当必要条件；现有完整生命周期与固定字节上限已可有界失败。也未把300秒当可保证排空阻塞I/O。原稿称“核与输入未变，差异只说明环境/序列化”错误：本次正是改实现后的等价验证，差异也可能来自新核或封装错误。键集多/少拒绝原协议已有，最终补明解析/零符号规则。SHA只证字节，终态须独立调度来源，不能把包自报true当证明。

本轮只有文档和来源小证据，无数值代码改动，不重复上一阶段83tests，也不把上一阶段测试当新生产驱动已经验证。新协议及报告/讲义155格式核、Git diff检查通过；旧讲义前缀不改，无图。两端pre-chord-reuse-resource-plan-20261006.bundle完整verify，Mac25953849B、学校25850357B。

[POST-RUN CHECK]

Code: PASS（仅本轮协议/小证据），历史小工件及代码SHA闭合；新生产实现尚缺。Logic: PASS（设计），来源/预算/比较/终态范围已明确，实际执行链仍待两端验证。Physics: WARNING，没有新数值运行/趋势/图或真实场结果，不增加物理结论。Decision: DO NOT RUN生产；继续显式封装实施及两端小合成/负路径。

下一项实施时再次查重：`operations/x20_85889_chord_reuse_resource.py/.sbatch`与`handoff/audit_tools/review_x20_85889_chord_reuse_resource.py`。按协议走显式新核调用、测试基准与生产固定pins分离、完整阶段证明、白名单归档和独立review_run；两端E2E及完整PRE-RUN通过后才另行决定一次资源提交，不自动扩大预算。85889/86061预算关闭，完整301片未授权，accepted20、0新物质、baseline/calibration/strictbound=false保持，HHe未完成。
