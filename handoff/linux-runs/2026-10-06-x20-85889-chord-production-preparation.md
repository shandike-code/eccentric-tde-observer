# 85889 六场诊断：来源封装与资源预检准备

本轮完成了小来源绑定器、单片资源预检入口及Slurm脚本、独立小矩审阅器、有限终态观察器和无dat小归档器。没有提交作业，没有读取真实dat、执行新map/反馈/ODE或物质步。学校生产仍为9555a78且clean；新代码只在隔离目录测试。原85889预算关闭。

## 来源实际核验

`x20_85889_chord_binding.py`固定绑定原归档清单、源需求审阅、final-review及实际terminal的SHA。对原321个已审小来源加declaration、两份native_trial_audit和两份initialized_identity，共326个不同路径重新读字节、核大小和SHA。全部801份原源码声明逐项用git show9555a78核对。

两支历史、map15/16的304块输入及9632核心组所有权重新核验；六个P/F/M声明必须与各真实历史连续绑定。正式pair16只绑定P/F。所有试态数组按dtype/shape/原始字节比较，并核physical old/base/r20、phase1367和dt889.419892762322。source84026调度未知不改写。

Mac实际E2E和学校实际原目录E2E首次均通过，绑定结果仅本地物理源定位路径不同。学校复用隔离目录作为新审阅文件位置，git show仍读原仓库对象；没有伪造新的源码提交。当前是archived_native_identity_verified=true、live_native_recomputed=false；归档payload的SHA绑定原最终审阅，但本轮未重哈希压缩包；六个大场SHA也未刷新。不能将这些未核层级包含在笼统“生产来源已全过”中。

## 新运行封装及验证

资源v1固定首32组一片、原生产shape；计划一次执行全部五基底Gram、四组合直接矩等统计，再重读同片核SHA。理论声明读量402653184B；这不是本轮实际大场读量。本轮实际资源E2E为33×2×3合成输入，只读首32组，Mac和学校各18432B。全部片统计及片SHA两端相同。合成峰值RSS分别33308672B和29491200B，不是生产资源证明。实际longdouble仍为Mac nmant52/maxexp1024、学校63/16384，NumPy2.5.2、FE_TONEAREST。

新入口独占目录、信号请求停止、600秒/RSS<6GiB guard，保存started/binding/result/finished或failure。Slurm脚本固定4CPU/16GiB/15分钟/单进程，并核环境及实际scontrol分配；USR1提前300秒，硬限限制阻塞底层调用。进程硬杀时不能保证failure写出，只能保留已有文件和调度/日志证据，不冒称所有失败都能完整归档。

只读observer最多1200秒，每10秒查询一次，保存真实终态后退出；不提交/取消作业。小归档器显式白名单、普通文件、独占输出，拒dat/链接/重名，大小和SHA回执不冒充scheduler成功。实际观察器尚未启动，没有本次真实JobId或调度回执。

Mac最终102项测试0.83秒通过（含旧47项）；学校隔离最终91项1.56秒通过（含旧36项统计测试）。早期68/95及学校84成功日志保留；增加实际分配和坏小矩负路径后重测，没有测试失败或数值容差放宽。最后11个学校代码/测试文件与Mac SHA逐项一致。bash语法检查通过。测试覆盖wrong SHA/路径/链/试态位级差、损坏矩、信号/资源停止、运行中片内容变化、重复目录、调度错job/失败/未知，以及归档漏入dat/链接/重名。

## 独立审阅与决定

学校无工具CLI实际deepseek-v4-flash[1m]，19.24秒。原稿保留。独立纠正：326小来源与801源码已实际重读核字节，不仅是登记；32组为一片；计划生产测量未运行；RUNNING分配检查不等于终态；全场统计也不等于物理验证。学习讲义150采用纠正后的版本，旧前缀保持。

新低I/O资源v1不刷新全场SHA，故尚未满足原协议实际六SHA前置要求。决定DO NOT RUN；先为资源预检明确并实现全场SHA前置核验及独立有界字节/墙钟预算，按修订协议重审。不能以资源测试为由绕过原要求，也不能因本次合成/小来源E2E通过直接提交完整301片统计。

下一项是闭合该来源预算差异和当前native/依赖核验，再完成代码冻结、两端备份及verify/fetch/ff-only同步、具体PRE-RUN、提交前观察器部署检查。单片预检和完整统计各自需独立决定，不自动扩预算。没有新的全场Gram、慢模、谱半径、剩余误差、ETA或A/H真解结论。

两端完整pre-85889-chord-production-20261006.bundle均verify。accepted20、0新物质步、baseline_replaced=false、reference_calibration_eligible=false、strict_error_bound=false，HHe最终任务未完成。
