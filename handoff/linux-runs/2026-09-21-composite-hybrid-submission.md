# 74437：扩大单批任务后的实际起跑

2026-09-21 10:21:41北京时间提交，10:21:42开始在anode16运行。作业74437，QOS为qos_stu_cpu_long，32CPU、申请内存128GiB、时限6小时，调度EndTime为16:21:42。时限不是完成时间预测；代码会在任务完成或科学判据失败时退出。

运行目录：`outputs/hpc/composite-hybrid-20260921`。执行代码`1d8c565fe1d56cca98709e16623b360cbf87cc88`，起跑前Mac、学校、GitHub分支均核对一致、工作树干净。批次合同见同日`composite-hybrid-batch.md`。

启动前Mac 53项测试通过（1.27秒），学校Linux同53项通过（19.41秒），sbatch语法检查通过。测试包含组合状态机、原诊断驱动和独立账本。Markdown检查仍报告6份旧讲义既有格式问题，本轮未改这些历史文件；没有将整库Markdown检查说成全通过。

PRE-RUN：代码接口和控制负路径PASS；输入到原算子再到原正式反馈的逻辑PASS；物理为WARNING——有限局部加速能否改善全场和物质接受仍待此次验证。实际allocation内先验证全部输入SHA、trial完整字段和native物质身份；未经此验证不启动首张map。

10:22:33调度现场为RUNNING，32CPU，处于preparing，已完成/活动map为0，反馈对为0，父stderr为空。这里不是科学通过证据；大输入SHA与准备检查仍在进行。

只读终态watcher PID3056014，30秒一次，最长24小时；输出在`outputs/review-20260921/scheduler-74437/`，日志`watch-74437.log`。它不提交或取消任务。批次已自动衔接，不依赖心跳逐段启动。阶段小工件包由驱动写入运行目录`archives/`。Mac起跑调度快照在`outputs/review-20260921/scheduler-74437-start.txt`。

备份包括两端改前Git bundle、Mac改前自动任务TOML与代码增量bundle。下一次审阅应查看74437的真实状态及阶段证据，不重新准备同名目录、不重复提交；故障先保全，源码已经冻结后不得原位修补该run声明。
