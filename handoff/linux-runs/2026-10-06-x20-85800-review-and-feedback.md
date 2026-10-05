# 85800真实映射通过，转入正式反馈窗口

85800于2026-10-06 00:14:14–01:02:47运行，真实COMPLETED0:0，48分33秒。anode02/Students/qos_stu_cpu_long，32CPU128GiB/16worker；数值4d1a8314e272063bc79021d152dbc4c8fe6b08fb，工作树干净，stderr空。程序墙钟2902.78070209641秒，父RSS1018535936字节，最大worker3587580KiB。两张map分别152.46606149431318秒、181.69649582728744秒；总作业包含大场初始化、构造、比较和多轮来源哈希，不能把48分钟当单张map耗时。

归档complete-1791219763016597794.tar.gz，4334719字节，SHA f9ee7304a2d74783cf587f44f82ae73ebb7cf55fba9f2b0a80ceaa7e71c2f281。不含dat。收件x20-85778-true-85800-received；batch-exit和真实scheduler-terminal另外保存。

review_x20_85800_true.py首次完整E2E通过325工件/795源码/33直接小来源，八个大场只核已审来源身份，152worker回执、trial/native/算子/块频率归属、301片80位统计归并全部核对。Mac没有重读大场或求解物质ODE。先前17项组件测试和31来源预检查不替代这次完整审计。84026原调度终态未知仍保留。

| 量 | full | half |
|---|---:|---:|
| 真实缺陷L2/锚点缺陷L2 | 0.5865597261082087 | 0.784585031125119 |
| 真实缺陷Linf/锚点缺陷Linf | 0.7038852079162022 | 0.8519426039283202 |
| 预测误差L2/锚点缺陷L2 | 1.9244256268866964e-9 | 1.047463639980492e-9 |
| 边界L1/锚点边界L1 | 0.8359378140871792 | 0.4724104051422288 |
| 边界bol/锚点边界bol | 0.09999930188585827 | 0.5499980794328932 |

真实缺陷是T(q)−q，预测误差是T(q)−p；half仿射一致性L2比2.369696803507685e-10是第三个不同指标，不能称half缺陷已降到1e-10。所有原16门通过，full真实输出SHA d7ced0397fa1a446e9e1571c575ec1b06fef4867c6a19b49a72c788eef026d83。结论限于本固定物质背景下的两次真实映射；这次2map、0反馈、0物质，accepted20不变。

POST-RUN：stderr无警告，完整片统计有限且无负平方，152worker退出成功并过内存保护，来源与seed链一致，原16门独立归并相符。预测与真实映射接近，但不提供未知固定点误差界；辐射缺陷下降不能直接推定正式加热或物质响应已稳定。本轮无新作图。

明确下一步：按x20-85800-seed-feedback-v1.md，在新目录以full真实输出启动historical最多16map，第8/16各一对正式反馈。分别比较新16−8、对84026加速前端点、对保存82518A16四组合。原七门/物理域/资源/来源失败停止；漂移失败只完成既定第二窗口，0物质更新，不自动扩预算。

Mac新入口与审阅器相关测试39passed1.04s（含已审归档与实时来源字节篡改的正反例）；shell检查通过。学校CLI实际模型deepseek-v4-flash[1m]。终态草稿误把batch-exit不验证调度当成矛盾，讲义草稿误把half解释为分辨率、把残差直接联系未知解距离、把同物理步稳定性说成跨物理步，已逐项独立纠正并保留原文。讲义第134节按实际代码定义重写。


## 85821实际启动与监督

代码提交16ad4d6fabdec1e9e958d7168ead0828f25792c7；学校干净旧HEAD4d1a831，经完整bundle备份、增量verify/fetch新ref/ff-only同步。学校39tests21.16s，Mac39tests1.04s；shell/diff检查通过。Mac/GitHub已保存数值提交，学校运行中不再同步文档。

2026-10-06 01:16:20提交85821，01:16:21开始RUNNING，anode02/Students/qos_stu_cpu_long、32CPU128GiB/16worker，硬限05:16:21、USR1提前900秒。01:17:00实际RUNNING/preparing/stderr0，尚无declaration、map或反馈结果，不能将计划16map写作已完成。提交和实际调度快照见20261006-x20-85821-submit.json、observation-00.json。

watch PID1190228仅启动凭据，start_new_session、PYTHONPATH及Node PATH已配，输出x20-85800-feedback-watch-85821。首份CLI实际deepseek-v4-flash[1m]、无工具；独立复查确认科学边界正确，但16map字样只是计划。已保留原草稿及审阅。每30分钟heartbeat已切换到85821；失联先检查ControlMaster、暂停并提醒一次，不取消Slurm。

备份Mac pre-85800-final-review-20261006.bundle、pre-85821-launch-note-20261006.bundle；学校pre-85800-feedback-code-20261006.bundle；增量85800-review-feedback-code-20261006.bundle；自动任务旧配置ustc-hhe-pre-85821-20261006.toml。下一轮必须刷新实际状态，终态取无dat归档和另存batch/scheduler回执，新审阅器须绑定85821、85800种子、84026前态、82518保存参照。
