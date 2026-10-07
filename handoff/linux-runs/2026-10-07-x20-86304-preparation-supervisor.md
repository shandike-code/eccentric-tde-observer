# 86304 准备子进程停止封装的小合成验收

本阶段实现独立资源组件，完整 native 准备仍未完成。没有真实 NPZ/native 刷新、真实 dat 的 stat/读取/下载、归档科学 payload、Slurm、map、反馈、ODE 或新物质步。accepted20、新物质0、校准与严格误差界 false、十倍质量响应失败保持。

## 实现与保证范围

新增 operations/x20_86304_preparation_supervisor.py。supervise 使用独占目录，先保存 intent，再以独立进程组启动可信 argv；从 Popen 之前计时，包含输出排空，默认外层150秒，stdout/stderr合计最多8MiB。截止、父TERM/INT/USR1、输出超限或异常触发进程组SIGKILL；保留有界日志前缀及 outcome，不重试。限额参数只能收紧，bool/非有限/扩限拒绝。新 native_configuration 无条件拒绝。

原 StopGuard 的120秒与1GiB历史峰值RSS门由可信子程序安装。本接口不能保证任意 argv 内已安装 guard；不提供文件访问保护。操作系统调度、Popen 阻塞及 SIGKILL 后回收不承诺严格延迟上界；逃离进程组的敌对子进程亦非本组件保护范围。生产封装必须固定经认证的入口、禁止派生进程并接入内外停止器。目前 production_resource_stop_guards_integrated=false，不把通用组件等同生产接线。

## 实测与独立审阅

Mac18项新测试0.70秒，学校18项2.68秒，无 skip 或断言放宽。另名 exercise 实际执行8类标准库微型子进程：正常、RSS1B拒绝、0.1秒时间信号、USR1、忽略信号后父0.5秒强杀、部分失败、父USR1、输出洪泛。正常案例使用默认150秒外限和原120秒/1GiB门，其余故障外限3秒或0.5秒；没有实跑150秒或为测试分配1GiB。

正常 Mac 内部0.0192805831秒/RSS17383424B，外层0.030376秒；学校内部0.0402334290秒/RSS18874368B，外层0.063728秒，仅标准库小例。忽略信号案例外层分别0.504887/0.503561秒，真实返回码负9并保存 kill_sent。输出故障用257B上限核实际保存前缀，不能把日志字节当科学输入IO或进程RSS。

学校5个隔离文件前后SHA同。首次收件36文件23559B先原始暂存，随后另取学校大小SHA清单；全部匹配后才写第二个独占认证收件目录，并在Mac独立审阅。不要将首次暂存说成已事先外部SHA认证。学校最终文件含旧审阅器；最终Mac审阅器改动未部署学校，实际执行组件和测试未改。

首次独立跨平台审阅拒绝：Mac SIGUSR1=30 被误用于 Linux parent_signal:10。原失败脚本和记录保留；最终审阅器要求外部 expected_platform，Linux按10、Mac按30核。没有重跑子进程，没有改停止行为。独立审阅不导入 supervisor，核完整8case、返回码/资格、大小SHA/日志前缀/内部门错误；4篡改资格、bool返回码、假kill、缺case均拒。

freeze01为1731，加入 exercise/reviewer 后 freeze02/03为1733；03包含平台审阅修正，Mac所有源码结束SHA同。两端完整 pre-86304-stop-wrapper-20261007.bundle verify。没有重跑旧context25、memory21、boundary15、inputs50、resource114或已审真实实验。

## 原配置剩余字段与运算

静态读取 hpc/pipeline.py 的 configure_native：读取 fixed、替换 current_material_state 的 trial claim，调用 phase7b9d._configure_worker，取得 template，再调用原_context。原 _configure_worker 仅经 _template_protocol 替换 initial_radiation_state.path 与 second_material_iterate，并全局替换 phase7b7i._load_protocol；后续 _second_full_material 才执行四次copy和四次镜像。当前 memory/context 两组件已分别核这些数值子路径，但尚未组成完整配置对象。

下一项须另名普通函数显式返回 fixed/template/context/material；绑定经认证 trial 的 current_material_state/second_material_iterate、原 old/master 来源、initial_radiation_state 纯词法路径，以及 template配置的phase/几何/频率所有权。复用原 exact_trial 和已验 copy/concatenate、原_full_column与stencil/block表达式，不调用旧 warm-seed resolve，不新增生产lambda/FunctionType/monkeypatch。原 numerical worker 的 map协议还含 input_state_sha256、diagnostic_fixed_iteration_count、spatial_scheme、source_map_only；不得把只配置的对象冒充已经运行该worker。

继续接固定准备入口与停止组件，并闭合 ZIP内部buffer、科学临时量的计量预约范围和环境启动访问保护。当前这些尚未实现；真实配置若限定学校Linux须独立审阅。真实343 staging、NPZ/native刷新与归档payload仍关闭。全部准备验收后才另审首次真实来源预算，首片预算另立，全301 DO NOT RUN。

## 证据位置

小审计 handoff/evidence/20261007-86304-preparation-supervisor-review.json；全部原始文件 outputs/review-20260925/20261007-supervisor-*。学校 preparation-supervisor-fixture-20261007；Mac preparation-supervisor-local-20261007、初次暂存 preparation-supervisor-school-20261007、认证收件 preparation-supervisor-school-verified-20261007。

CLI13.8350375001秒，实际 deepseek-v4-flash[1m]，仅给定事实讲义，不是源码或性能审计。草稿“两端共18”纠正为两端各18；“面向任意argv”只表示接口接受命令，不能推广为不可信程序保证。原稿与独立纠正保留。
